"""Download a Fansly video from its HLS or DASH stream.

Used only for Fansly items whose best delivery is a stream (see
``ofscraper.sites.fansly.video.uses_stream``); the direct MP4 still goes
through the normal downloader. An HLS stream's segments are fetched several
at a time into a folder next to the .part, then ffmpeg joins them into one MP4
without re-encoding (#292). DASH, and any HLS playlist that parallel fetching
doesn't handle, is copied by ffmpeg on its own, one segment after another.
The finishing steps (move, collision handling, file time, database, hash,
after-download script) are the same as the normal downloader's.
"""

import asyncio
import contextlib
import pathlib
import shutil
import subprocess
import threading
from functools import partial

from humanfriendly import format_size

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.actions.utils.general as common
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.commands.scraper.actions.utils.log as common_logs
import ofscraper.commands.scraper.actions.utils.paths as common_paths
import ofscraper.utils.dates as dates
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.download.managers.downloadmanager import (
    DownloadManager,
)
from ofscraper.db.operations_.media import mark_media_as_downloaded
from ofscraper.managers.sessionmanager.sessionmanager import HEADERS
from ofscraper.sites.fansly import auth as fansly_auth
from ofscraper.sites.fansly import headers as fansly_headers
from ofscraper.sites.fansly import video as fansly_video
from ofscraper.utils.cache.profile import set_profile_cache
from ofscraper.utils.system.ffmpeg import get_ffmpeg, get_ffprobe
from ofscraper.utils.system.ffprobe import get_media_duration, verify_media_integrity
from ofscraper.commands.scraper.actions.download.utils.chunk import (
    get_chunk_size,
    get_chunk_timeout,
)
from ofscraper.commands.scraper.actions.download.utils.retries import download_retry

# Backstop for the whole ffmpeg run, in seconds: at least the floor, or this
# many seconds per second of video. A connection that stops sending is caught
# sooner by ffmpeg's -rw_timeout (the chunk timeout).
STREAM_TIMEOUT_FLOOR = 3600
STREAM_TIMEOUT_PER_SECOND = 10


def stream_timeout(duration) -> float:
    try:
        duration = float(duration or 0)
    except (TypeError, ValueError):
        duration = 0
    return max(STREAM_TIMEOUT_FLOOR, duration * STREAM_TIMEOUT_PER_SECOND)


class StreamTimeout(Exception):
    pass


class SegmentError(Exception):
    """A stream file that couldn't be fetched; the whole download fails."""


def segment_limit() -> int:
    """Files of one HLS stream fetched at once; 0 leaves it all to ffmpeg."""
    try:
        return max(0, int(of_env.getattr("FANSLY_STREAM_SEGMENTS")))
    except (TypeError, ValueError):
        return 0


async def _off_loop(fn, *args):
    """``fn(*args)`` in the default thread pool. A cancel waits for the call
    to finish before it goes on, so a file is never closed under a write."""
    job = asyncio.get_running_loop().run_in_executor(None, fn, *args)
    try:
        return await asyncio.shield(job)
    except asyncio.CancelledError:
        await asyncio.wait([job])
        raise


def _free_space(path) -> int:
    return shutil.disk_usage(path).free


# room kept free on top of the stream's size when joining it
JOIN_SPACE_MARGIN = 64 * 1024 * 1024


class NotEnoughSpace(Exception):
    pass


def segment_folder(temp) -> pathlib.Path:
    """The folder next to the .part that holds a stream's files until they're joined."""
    temp = pathlib.Path(temp)
    return temp.with_name(temp.name + ".segments")


class _Ffmpeg:
    """The ffmpeg process of one download, so a cancelled download can stop it."""

    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.stopped = False

    def start(self, cmd, cwd=None):
        with self.lock:
            if self.stopped:
                raise StreamTimeout("download cancelled before ffmpeg started")
            self.proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            return self.proc

    def stop(self):
        with self.lock:
            self.stopped = True
            if self.proc and self.proc.poll() is None:
                self.proc.kill()


def _run_process(proc, cmd, timeout, cwd=None):
    """Run ffmpeg to the end, or kill it after ``timeout`` seconds."""
    p = proc.start(cmd, cwd=cwd)
    try:
        _, stderr = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        p.communicate()
        raise StreamTimeout(f"ffmpeg ran longer than {timeout:.0f}s and was stopped")
    return p.returncode, stderr


def _packet_times(ffprobe, path, stream):
    """Packet times (seconds) of one stream, read without decoding."""
    out = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", stream,
         "-show_entries", "packet=dts_time", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    times = []
    for value in out.split():
        try:
            times.append(float(value.strip(",")))
        except ValueError:
            pass  # N/A
    return times


class FanslyStreamDownloadManager(DownloadManager):
    async def stream_download(self, c, ele, username, model_id):
        await common_globals.sem.acquire()
        try:
            return await self._stream_download(c, ele, username, model_id)
        finally:
            common_globals.sem.release()

    async def _stream_download(self, c, ele, username, model_id):
        medialog = common_logs.get_medialog(ele)
        best = fansly_video.select_best(fansly_video.raw_media(ele))
        if not best or not best.is_stream:
            raise fansly_video.StreamError("no HLS or DASH stream to download")
        common_globals.log.debug(
            f"{medialog} Downloading with the Fansly stream downloader: "
            f"{best.kind} {best.width}x{best.height}"
        )
        self._downloadspace()

        try:
            url, audio_url = await self._stream_urls(c, best)
        except fansly_video.StreamError as e:
            if ele.url and fansly_video.has_direct(fansly_video.raw_media(ele)):
                # None: run.py downloads the direct file instead (ele.url
                # is the stream itself when there is no direct file)
                common_globals.log.info(f"{medialog} {e}; downloading the direct file instead")
                return None
            if isinstance(e, fansly_video.ProtectedStream):
                common_globals.log.info(f"{medialog} protected, not downloaded")
                return "forced_skipped", 0
            if isinstance(e, fansly_video.MissingAudio):
                # fail rather than save a silent video that is never fetched again
                raise
            common_globals.log.warning(f"{medialog} {e}")
            return "skipped", 0

        placeholderObj = await placeholder.Placeholders(ele, "mp4").init()
        common_logs.path_to_file_logger(placeholderObj, ele)
        tempholderObj = await placeholder.tempFilePlaceholder(
            ele, f"{ele.filename or ele.id}_{ele.id}_{ele.post_id}.part"
        ).init()
        temp = pathlib.Path(tempholderObj.tempfilepath)
        temp.unlink(missing_ok=True)

        # BaseException: a cancelled run (Ctrl+C) also removes the .part
        try:
            await self._copy_stream(
                c, best, url, audio_url, temp, stream_timeout(ele.duration), medialog
            )
            await self._check_complete(temp, ele)
            total = temp.stat().st_size

            if await self._check_forced_skip(ele, total) == 0:
                temp.unlink(missing_ok=True)
                if self._skipped_by_script(ele):
                    # as main_download: counted as skipped, saved only
                    # for a permanent skip (#351)
                    return await self._script_skip_result(ele, username, model_id)
                if ele.mediatype.capitalize() != "Forced_skipped":
                    await self._force_download(ele, username, model_id)
                return ele.mediatype.capitalize(), 0

            await self._total_change_helper(total)
            await self._integrity_check(temp, ele)
            return await self._finish(temp, placeholderObj, ele, username, model_id, total)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise

    async def _copy_stream(self, c, best, url, audio_url, temp, timeout, medialog):
        """Copy the stream into ``temp``: HLS segments fetched in parallel and
        joined by ffmpeg, or, for DASH and any playlist the parallel
        downloader doesn't handle, ffmpeg on its own."""
        playlists = None
        if best.kind == fansly_video.HLS and segment_limit() > 0:
            playlists = await self._local_playlists(c, url, audio_url, best.cookies, medialog)
        if playlists is None:
            return await self._run_ffmpeg(url, temp, best.cookies, audio_url, timeout)
        common_globals.log.debug(
            f"{medialog} Fetching {sum(len(p.files) for p in playlists if p)} stream "
            f"files, {segment_limit()} at a time"
        )
        await self._parallel_copy(c, playlists, temp, best.cookies, timeout)

    async def _local_playlists(self, c, url, audio_url, cookies, medialog):
        """(video, audio or None) LocalPlaylists, or None to leave it to ffmpeg.

        A playlist that can't be fetched fails the file, as it would in ffmpeg."""
        try:
            video = fansly_video.local_playlist(
                await self._fetch_text(c, url, cookies), url, "v"
            )
            audio = None
            if audio_url:
                audio = fansly_video.local_playlist(
                    await self._fetch_text(c, audio_url, cookies), audio_url, "a"
                )
            return video, audio
        except fansly_video.UnexpectedPlaylist as e:
            common_globals.log.info(f"{medialog} {e}; ffmpeg fetches the stream instead")
            return None

    async def _parallel_copy(self, c, playlists, temp, cookies, timeout):
        """Fetch every file of the playlists into a folder next to ``temp``,
        then join them with ffmpeg. The folder is removed however this ends."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout  # one limit for the fetch and the join
        folder = segment_folder(temp)
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
        try:
            video, audio = playlists
            jobs = video.files + (audio.files if audio else [])
            try:
                await asyncio.wait_for(
                    self._fetch_segments(c, jobs, folder, cookies), timeout
                )
            except asyncio.TimeoutError:
                raise StreamTimeout(
                    f"the stream's segments took longer than {timeout:.0f}s and were stopped"
                )
            self._check_join_space(folder, temp)
            (folder / "video.m3u8").write_text(video.text, encoding="utf-8")
            if audio:
                (folder / "audio.m3u8").write_text(audio.text, encoding="utf-8")
            # ffmpeg runs in the folder and gets the playlists by bare name:
            # its HLS reader resolves segment names against the playlist's
            # path as a URL, where a "#" in a folder name starts a fragment
            cmd = fansly_video.local_join_command(
                get_ffmpeg(), "video.m3u8", pathlib.Path(temp).absolute(),
                "audio.m3u8" if audio else None,
            )
            await self._run_cmd(
                cmd, temp, max(1.0, deadline - loop.time()),
                "join the stream's segments", cwd=folder,
            )
        finally:
            shutil.rmtree(folder, ignore_errors=True)

    def _check_join_space(self, folder, temp):
        """Fail with a clear message when the .part's drive can't hold the
        joined copy (about the segments' size) next to the segments."""
        size = sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
        need = size + max(JOIN_SPACE_MARGIN, size // 20)
        free = _free_space(pathlib.Path(temp).parent)
        if free < need:
            raise NotEnoughSpace(
                f"not enough disk space to join the stream: needs about "
                f"{format_size(need)}, {format_size(free)} free"
            )

    async def _fetch_segments(self, c, jobs, folder, cookies):
        """Fetch (url, name) jobs into ``folder``, at most ``segment_limit()``
        at once. The first file that fails all its retries stops the rest."""
        pending = iter(jobs)

        async def worker():
            for url, name in pending:
                await self._fetch_segment(c, url, folder / name, cookies)

        workers = [
            asyncio.ensure_future(worker())
            for _ in range(min(segment_limit(), len(jobs)))
        ]
        try:
            await asyncio.gather(*workers)
        except BaseException:
            # let every worker finish (and close its file) before the folder goes
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            raise

    async def _fetch_segment(self, c, url, path, cookies):
        """One file of the stream, with the download retries. Errors name the
        file, never its URL (it may carry a signature)."""
        try:
            async for _ in download_retry():
                with _:
                    await self._fetch_segment_once(c, url, path, cookies)
        except (KeyboardInterrupt, asyncio.CancelledError):
            raise
        except Exception as e:
            why = e if isinstance(e, SegmentError) else type(e).__name__
            raise SegmentError(
                f"stream file {path.name} failed after its retries: {why}"
            ) from e

    async def _fetch_segment_once(self, c, url, path, cookies):
        # HEADERS only, as for the playlists (see _fetch_text)
        async with c.requests_async(
            url=url,
            cookies=cookies or None,
            actions=[HEADERS],
            total_timeout=None,
            read_timeout=get_chunk_timeout(),
        ) as r:
            if not r.ok:
                raise SegmentError(f"status {r.status}")
            expected = r.headers.get("content-length")
            written = 0
            # writes run in a thread, as aiofiles does for the normal
            # downloader, but the file is closed here, only once no write is
            # still running, so the folder can always be removed after a cancel
            with open(path, "wb") as f:
                async for chunk in r.iter_chunked(get_chunk_size()):
                    await _off_loop(f.write, chunk)
                    written += len(chunk)
        if not written or (expected and int(expected) != written):
            raise SegmentError(f"got {written} of {expected or 'some'} bytes")

    async def _stream_urls(self, c, best):
        """(video url, separate audio url or None) to give ffmpeg."""
        manifest = await self._fetch_text(c, fansly_video.check_url(best.url), best.cookies)
        if best.kind == fansly_video.HLS:
            url, audio_url = fansly_video.best_rendition(manifest, best.url)
            return (fansly_video.check_url(url),
                    fansly_video.check_url(audio_url) if audio_url else None)
        if fansly_video.dash_is_protected(manifest):
            raise fansly_video.ProtectedStream("DASH stream is protected (DRM)")
        return best.url, None

    async def _fetch_text(self, c, url, cookies):
        # HEADERS only: the CloudFront cookies must not be replaced by the
        # session's own (none for Fansly), and CDN requests are never signed
        try:
            async with c.requests_async(
                url=url, cookies=cookies or None, actions=[HEADERS]
            ) as r:
                if not r.ok:
                    raise fansly_video.StreamError(
                        f"stream manifest request failed with status {r.status}"
                    )
                return await r.text_()
        except fansly_video.StreamError:
            raise
        except Exception as e:
            # the session raises for statuses other than 404 (a 403 once the
            # cookies expire, a 5xx); the direct file may still work
            raise fansly_video.StreamError(
                f"stream manifest request failed: {type(e).__name__}"
            ) from e

    async def _check_complete(self, temp, ele):
        """Fail a copy that ffmpeg finished with a segment missing.

        ffmpeg skips a segment it can't read and still exits 0, so the packet
        times of the copy are checked for holes (see ``video.timeline``).
        """
        ffprobe = get_ffprobe()
        if not ffprobe:
            common_globals.log.warning(
                f"{common_logs.get_medialog(ele)} ffprobe not found; "
                "the stream copy can't be checked for skipped segments"
            )
            return
        loop = asyncio.get_event_loop()
        video_times, audio_times = [
            await loop.run_in_executor(
                common_globals.thread, partial(_packet_times, ffprobe, temp, stream)
            )
            for stream in ("v:0", "a:0")
        ]
        reason = fansly_video.incomplete_reason(
            video_times,
            audio_times,
            fansly_video.expected_duration(fansly_video.raw_media(ele)),
        )
        if reason:
            raise Exception(f"Fansly stream copy is incomplete: {reason}")

    async def _run_ffmpeg(self, url, temp, cookies, audio_url=None, timeout=None):
        cmd = fansly_video.ffmpeg_command(
            get_ffmpeg(),
            url,
            temp,
            fansly_headers.cdn_headers(fansly_auth.read_auth()),
            cookies,
            audio_url=audio_url,
            rw_timeout=get_chunk_timeout(),
        )
        await self._run_cmd(cmd, temp, timeout, "copy the stream")

    async def _run_cmd(self, cmd, temp, timeout, what, cwd=None):
        # subprocess in a worker thread: the app may run a selector event
        # loop on Windows, which can't start asyncio subprocesses
        proc = _Ffmpeg()
        job = common_globals.thread.submit(_run_process, proc, cmd, timeout, cwd)
        try:
            returncode, stderr = await asyncio.wrap_future(job)
        except BaseException:
            # cancelled (Ctrl+C): stop ffmpeg and wait for it to let go of the .part
            proc.stop()
            with contextlib.suppress(BaseException):
                job.result(timeout=30)
            raise
        if returncode != 0 or not temp.exists() or not temp.stat().st_size:
            err = (stderr or b"").decode("utf-8", "replace").strip()[-500:]
            raise Exception(f"ffmpeg could not {what}: {err or 'no output'}")

    async def _integrity_check(self, temp, ele):
        if not settings.get_settings().verify_all_integrity:
            return
        expected = ele.duration
        loop = asyncio.get_event_loop()
        if expected:
            ok = await loop.run_in_executor(
                common_globals.thread, partial(verify_media_integrity, temp, expected)
            )
        else:
            ok = (
                await loop.run_in_executor(
                    common_globals.thread, partial(get_media_duration, temp)
                )
            ) is not None
        if not ok:
            temp.unlink(missing_ok=True)
            raise Exception("Fansly stream download failed the integrity check")

    async def _finish(self, temp, placeholderObj, ele, username, model_id, total):
        loop = asyncio.get_event_loop()
        # can end up under another name if a different file already has this one (#48)
        path_to_file = await loop.run_in_executor(
            common_globals.thread,
            partial(common_paths.moveHelper, temp, placeholderObj.trunicated_filepath, ele),
        )
        common_paths.addGlobalDir(path_to_file.parent)
        if ele.postdate:
            await loop.run_in_executor(
                common_globals.thread,
                partial(
                    common_paths.set_time,
                    path_to_file,
                    dates.convert_local_time(ele.postdate),
                ),
            )
        if ele.id:
            await mark_media_as_downloaded(
                ele,
                filepath=path_to_file,
                model_id=model_id,
                username=username,
                downloaded=True,
                hashdata=await common.get_hash(path_to_file),
                size=path_to_file.stat().st_size,
            )
        await set_profile_cache(ele, common_globals.thread)
        ele.add_filepath(path_to_file)
        ele.add_size(total)
        await self._after_download_script(path_to_file)
        return ele.mediatype, total
