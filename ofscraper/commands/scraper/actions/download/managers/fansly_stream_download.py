"""Download a Fansly video from its HLS or DASH stream.

Used only for Fansly items whose best delivery is a stream (see
``ofscraper.sites.fansly.video.uses_stream``); the direct MP4 still goes
through the normal downloader. ffmpeg copies the stream into one MP4 without
re-encoding. The finishing steps (move, collision handling, file time,
database, hash, after-download script) are the same as the normal downloader's.
"""

import asyncio
import contextlib
import pathlib
import subprocess
import threading
from functools import partial

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.actions.utils.general as common
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.commands.scraper.actions.utils.log as common_logs
import ofscraper.commands.scraper.actions.utils.paths as common_paths
import ofscraper.utils.dates as dates
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
from ofscraper.commands.scraper.actions.download.utils.chunk import get_chunk_timeout

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


class _Ffmpeg:
    """The ffmpeg process of one download, so a cancelled download can stop it."""

    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.stopped = False

    def start(self, cmd):
        with self.lock:
            if self.stopped:
                raise StreamTimeout("download cancelled before ffmpeg started")
            self.proc = subprocess.Popen(
                cmd,
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


def _run_process(proc, cmd, timeout):
    """Run ffmpeg to the end, or kill it after ``timeout`` seconds."""
    p = proc.start(cmd)
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
            await self._run_ffmpeg(
                url, temp, best.cookies, audio_url, stream_timeout(ele.duration)
            )
            await self._check_complete(temp, ele)
            total = temp.stat().st_size

            if await self._check_forced_skip(ele, total) == 0:
                temp.unlink(missing_ok=True)
                if ele.mediatype.capitalize() != "Forced_skipped":
                    await self._force_download(ele, username, model_id)
                return ele.mediatype.capitalize(), 0

            await self._total_change_helper(total)
            await self._integrity_check(temp, ele)
            return await self._finish(temp, placeholderObj, ele, username, model_id, total)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise

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
        # subprocess in a worker thread: the app may run a selector event
        # loop on Windows, which can't start asyncio subprocesses
        proc = _Ffmpeg()
        job = common_globals.thread.submit(_run_process, proc, cmd, timeout)
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
            raise Exception(f"ffmpeg could not copy the stream: {err or 'no output'}")

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
