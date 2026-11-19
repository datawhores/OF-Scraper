"""Download a Fansly video from its HLS or DASH stream.

Used only for Fansly items whose best delivery is a stream (see
``ofscraper.sites.fansly.video.uses_stream``); the direct MP4 still goes
through the normal downloader. An HLS stream's segments are fetched several
at a time into a folder next to the .part, then ffmpeg joins them into one MP4
without re-encoding (#292). Common static DASH streams use the same resumable
fetcher; unsupported playlists are copied by ffmpeg on its own.
The finishing steps (move, collision handling, file time, database, hash,
after-download script) are the same as the normal downloader's.
"""

import asyncio
import contextlib
import ctypes
import json
import os
import pathlib
import shutil
import subprocess
import threading
from functools import partial
from urllib.parse import urlsplit, urlunsplit

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
from ofscraper.commands.scraper.actions.download.utils.refresh import (
    refresh_media_link,
)
from ofscraper.commands.scraper.actions.download.utils import silent
from ofscraper.managers.sessionmanager.sessionmanager import (
    HEADERS,
    is_provided_exception_number,
)
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
    return temp.with_name("." + temp.name + ".segments")


def _hide_folder(folder):
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        attributes = kernel32.GetFileAttributesW(str(folder))
        if attributes == -1 or not kernel32.SetFileAttributesW(str(folder), attributes | 2):
            raise ctypes.WinError()
    except Exception as e:
        common_globals.log.debug(f"Could not hide stream segments folder: {type(e).__name__}")


def _refused(e) -> bool:
    """True when the CDN refused the request (401 or 403) somewhere in the chain."""
    seen = set()
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        if is_provided_exception_number(e, 401, 403):
            return True
        e = e.__cause__ or e.__context__
    return False


def _prepare_segments(folder, playlists):
    # Keep playlist boundaries, local names and timing as well as unsigned URLs.
    manifest = [
        {"text": p.text, "files": [
            [urlunsplit(urlsplit(url)._replace(query="", fragment="")), name]
            for url, name in p.files
        ]} if p else None
        for p in playlists
    ]
    saved = None
    try:
        saved = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if not settings.get_settings().auto_resume or saved != manifest:
        if folder.exists():
            shutil.rmtree(folder)
    folder.mkdir(parents=True, exist_ok=True)
    _hide_folder(folder)
    for path in folder.glob("*.tmp"):
        path.unlink()
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _concat_track(folder, pieces, name):
    path = folder / (name + ".tmp")
    with path.open("wb") as out:
        for piece in pieces:
            with (folder / piece).open("rb") as source:
                shutil.copyfileobj(source, out)
    path.replace(folder / name)


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


def _read_times(out, played=False):
    """The times in ffprobe's ``time,flags`` lines. ``played``: leave out
    packets the file marks as not played (the ``D`` flag)."""
    times = []
    for line in out.splitlines():
        parts = line.strip().strip(",").split(",")
        if played and len(parts) > 1 and "D" in parts[-1]:
            continue
        try:
            times.append(float(parts[0]))
        except ValueError:
            pass  # N/A, or an empty line
    return times


def _packet_times(ffprobe, path, stream, played=False):
    """Packet times (seconds) of one stream, read without decoding.

    ``played``: only the packets that are played. An MP4 keeps packets it
    marks as not played (an AAC encoder's lead-in, what an edit list cuts);
    counted, they make a stream look longer than it plays."""
    out = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", stream,
         "-show_entries", "packet=dts_time,flags", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return _read_times(out, played)


def _first_shown(ffprobe, path, stream):
    """When the stream's first frame or sample is shown (seconds), or None.

    Not its first packet's decode time: with B-frames that is earlier than
    the first shown frame, by an amount that depends on the encoder's
    settings, so it can't be compared between two encodings of one upload.
    Packets the file marks as not played don't count, and a file cut without
    re-encoding can start with any number of them, so every packet is read.
    A cut can also fall inside a packet: that packet's time is before the
    file's start (below zero), and it is played from the start."""
    out = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", stream,
         "-show_entries", "packet=pts_time,flags", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    times = _read_times(out, played=True)
    return max(0.0, min(times)) if times else None


def _has_packets(ffprobe, path, stream) -> bool:
    """True when ``path`` has at least one packet of ``stream``; reads only the first."""
    out = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", stream,
         "-read_intervals", "%+#1", "-show_entries", "packet=stream_index",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return out.returncode == 0 and bool(out.stdout.strip())


def _codec(ffprobe, path, stream):
    out = subprocess.run(
        [str(ffprobe), "-v", "error", "-select_streams", stream,
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return out.stdout.strip().split("\n")[0].strip(",") if out.returncode == 0 else ""


def _frame(times) -> float:
    """The usual step between packets (one frame), in seconds."""
    ts = sorted(times)
    steps = [b - a for a, b in zip(ts, ts[1:]) if b > a]
    steps.sort()
    return steps[len(steps) // 2] if steps else 0.0


def _audio_stream(ffprobe, path):
    """True when ffprobe reads ``path`` and it has an audio stream, False when
    it reads it and it has none, None when it can't read it (an error page, a
    cut-off file): then nothing is known about the sound."""
    out = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    kinds = {line.strip().strip(",") for line in out.stdout.split()}
    if out.returncode != 0 or not kinds:
        return None
    return "audio" in kinds


# the sound taken from the direct file: AAC, copied as it is (``-c copy``);
# anything else falls back to the silent copy rather than re-encoding
COPYABLE_AUDIO = {"aac"}
# how many frames the direct file's video may differ in length from the
# stream's before its sound is taken as out of step
SOUND_FRAMES = 2


class FanslyStreamDownloadManager(DownloadManager):
    async def stream_download(self, c, ele, username, model_id):
        await self.ctx.sem.acquire()
        try:
            return await self._stream_download(c, ele, username, model_id)
        finally:
            self.ctx.sem.release()

    async def _stream_download(self, c, ele, username, model_id):
        medialog = common_logs.get_medialog(ele)
        # the direct file can give the sound a refused audio track can't
        self.ele = ele
        self.audio_refused = None
        best = fansly_video.select_best(fansly_video.raw_media(ele))
        if not best or not best.is_stream:
            raise fansly_video.StreamError("no HLS or DASH stream to download")
        self.ctx.log.debug(
            f"{medialog} Downloading with the Fansly stream downloader: "
            f"{best.kind} {best.width}x{best.height}"
        )
        tempholderObj = await placeholder.tempFilePlaceholder(
            ele, f"{ele.filename or ele.id}_{ele.id}_{ele.post_id}.part"
        ).init()
        temp = pathlib.Path(tempholderObj.tempfilepath)
        if not settings.get_settings().auto_resume:
            shutil.rmtree(segment_folder(temp), ignore_errors=True)
        self._downloadspace()

        try:
            try:
                url, audio_url = await self._stream_urls(c, best)
            except fansly_video.StreamError as e:
                # Fansly sometimes signs the links for another address (#683):
                # ask for them again, once, before giving up on the stream
                if not is_provided_exception_number(e.__cause__, 403):
                    raise
                if not await refresh_media_link(ele):
                    raise
                best = fansly_video.select_best(fansly_video.raw_media(ele))
                if not best or not best.is_stream:
                    raise
                url, audio_url = await self._stream_urls(c, best)
        except fansly_video.StreamError as e:
            if (
                ele.url
                and fansly_video.has_direct(fansly_video.raw_media(ele))
                # replacing a silent copy: the smaller direct file is no better
                and not getattr(ele, "replace_silent", None)
            ):
                # None: run.py downloads the direct file instead (ele.url
                # is the stream itself when there is no direct file)
                self.ctx.log.info(f"{medialog} {e}; downloading the direct file instead")
                shutil.rmtree(segment_folder(temp), ignore_errors=True)
                return None
            if isinstance(e, fansly_video.ProtectedStream):
                self.ctx.log.info(f"{medialog} protected, not downloaded")
                shutil.rmtree(segment_folder(temp), ignore_errors=True)
                return "forced_skipped", 0
            if isinstance(e, fansly_video.MissingAudio):
                # fail rather than save a silent video that is never fetched again
                raise
            self.ctx.log.warning(f"{medialog} {e}")
            shutil.rmtree(segment_folder(temp), ignore_errors=True)
            return "skipped", 0

        placeholderObj = await placeholder.Placeholders(ele, "mp4").init()
        common_logs.path_to_file_logger(placeholderObj, ele, self.ctx.log, self.ctx.attempt)
        temp.unlink(missing_ok=True)
        # a copy with the direct file's sound that a killed run left behind
        temp.with_name(temp.name + ".sound").unlink(missing_ok=True)

        # BaseException: a cancelled run (Ctrl+C) also removes the .part
        try:
            await self._copy_stream(
                c, best, url, audio_url, temp, stream_timeout(ele.duration), medialog
            )
            await self._check_complete(temp, ele)
            total = temp.stat().st_size

            if await self._check_forced_skip(ele, total) == 0:
                temp.unlink(missing_ok=True)
                if getattr(ele, "replace_silent", None):
                    # the silent copy stays saved as it is: its row keeps its
                    # file, and silent.recheck counts the check as used
                    ele.not_kept = (
                        "the copy with sound was skipped by the size limits "
                        "or skip_download_script"
                    )
                    return "forced_skipped", 0
                if self._skipped_by_script(ele):
                    # as main_download: counted as skipped, saved only
                    # for a permanent skip (#351)
                    return await self._script_skip_result(ele, username, model_id)
                if ele.mediatype.capitalize() != "Forced_skipped":
                    await self._force_download(ele, username, model_id)
                return ele.mediatype.capitalize(), 0

            await self._total_change_helper(total)
            await self._integrity_check(temp, ele)
            await self._replace_silent(temp, ele)
            return await self._finish(temp, placeholderObj, ele, username, model_id, total)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise

    async def _copy_stream(self, c, best, url, audio_url, temp, timeout, medialog):
        """Copy resumable files and join locally, or leave unusual streams to ffmpeg."""
        playlists = None
        if best.kind == fansly_video.HLS and segment_limit() > 0:
            playlists = await self._local_playlists(c, url, audio_url, best.cookies, medialog)
        elif best.kind == fansly_video.DASH and segment_limit() > 0:
            try:
                playlists = fansly_video.local_dash(await self._fetch_text(c, url, best.cookies), url)
            except fansly_video.UnexpectedPlaylist as e:
                self.ctx.log.info(f"{medialog} {e}; ffmpeg fetches the stream instead")
        if playlists is None:
            # Rare live/LL/nested HLS, non-AES-128/session keys, and protected,
            # live or multi-period DASH still need ffmpeg alone and cannot resume.
            shutil.rmtree(segment_folder(temp), ignore_errors=True)
            return await self._run_ffmpeg(url, temp, best.cookies, audio_url, timeout)
        self.ctx.log.debug(
            f"{medialog} Fetching {sum(len(p.files) for p in playlists if p)} stream "
            f"files, {segment_limit()} at a time"
        )
        await self._parallel_copy(c, playlists, temp, best.cookies, timeout, medialog)

    def _audio_was_refused(self, medialog, what):
        # the warning waits: the direct file may still give the sound
        self.audio_refused = what
        self.ctx.log.info(f"{medialog} the CDN refused {what}")

    def _warn_silent(self, medialog):
        self.ctx.log.warning(
            f"{medialog} the CDN refused {self.audio_refused}; saving the video without sound"
        )

    async def _local_playlists(self, c, url, audio_url, cookies, medialog):
        """(video, audio or None) LocalPlaylists, or None to leave it to ffmpeg.

        A playlist that can't be fetched fails the file, as it would in ffmpeg."""
        try:
            shared = {}
            video = fansly_video.local_playlist(
                await self._fetch_text(c, url, cookies), url, "v", shared
            )
            audio = None
            if audio_url:
                try:
                    text = await self._fetch_text(c, audio_url, cookies)
                except fansly_video.StreamError as e:
                    if not _refused(e):
                        raise
                    self._audio_was_refused(medialog, "its audio playlist")
                else:
                    audio = fansly_video.local_playlist(text, audio_url, "a", shared)
            return video, audio
        except fansly_video.UnexpectedPlaylist as e:
            self.ctx.log.info(f"{medialog} {e}; ffmpeg fetches the stream instead")
            return None

    async def _parallel_copy(self, c, playlists, temp, cookies, timeout, medialog=""):
        """Fetch every file of the playlists into a folder next to ``temp``,
        then join them with ffmpeg. Keep completed files if the copy fails.

        The video's files come first. If the CDN then refuses the separate
        audio track, the sound is taken from the direct file; failing that,
        the video is saved without sound and a warning says why."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout  # one limit for the fetch and the join
        folder = segment_folder(temp)
        complete = False
        try:
            _prepare_segments(folder, playlists)
            video, audio = playlists
            try:
                await asyncio.wait_for(
                    self._fetch_segments(c, video.files, folder, cookies), timeout
                )
                if audio:
                    try:
                        await asyncio.wait_for(
                            self._fetch_segments(c, audio.files, folder, cookies),
                            max(0.01, deadline - loop.time()),
                        )
                    except SegmentError as e:
                        if not _refused(e):
                            raise
                        self._audio_was_refused(medialog, "its audio track")
                        audio = None
            except asyncio.TimeoutError:
                raise StreamTimeout(
                    f"the stream's segments took longer than {timeout:.0f}s and were stopped"
                )
            if isinstance(video, fansly_video.LocalDashTrack):
                self._check_join_space(folder, temp, dash=True)
            else:
                self._check_join_space(folder, temp)
            if isinstance(video, fansly_video.LocalDashTrack):
                # Concatenate each fMP4 track off the event loop. These derived
                # files are rebuilt on resume; only fetched pieces are reused.
                for track, name in ((video, "video.mp4"), (audio, "audio.mp4")):
                    if track:
                        try:
                            await asyncio.wait_for(
                                _off_loop(_concat_track, folder, track.pieces, name),
                                max(0.01, deadline - loop.time()),
                            )
                        except asyncio.TimeoutError:
                            raise StreamTimeout("DASH track concatenation exceeded the stream time limit")
                cmd = fansly_video.local_join_command(
                    get_ffmpeg(), "video.mp4", pathlib.Path(temp).absolute(),
                    "audio.mp4" if audio else None, dash=True,
                )
            else:
                (folder / "video.m3u8").write_text(video.text, encoding="utf-8")
                if audio:
                    (folder / "audio.m3u8").write_text(audio.text, encoding="utf-8")
                # Bare names avoid URL fragment interpretation of '#' in paths.
                cmd = fansly_video.local_join_command(
                    get_ffmpeg(), "video.m3u8", pathlib.Path(temp).absolute(),
                    "audio.m3u8" if audio else None,
                )
            await self._run_cmd(
                cmd, temp, max(1.0, deadline - loop.time()),
                "join the stream's segments", cwd=folder,
            )
            if not audio and await self._needs_sound(temp):
                await self._sound_from_direct(
                    c, folder, temp, cmd[cmd.index("-i") + 1],
                    isinstance(video, fansly_video.LocalDashTrack), deadline, medialog,
                )
            complete = True
        finally:
            if isinstance(playlists[0], fansly_video.LocalDashTrack):
                for name in ("video.mp4", "audio.mp4"):
                    (folder / name).unlink(missing_ok=True)
            if complete or not settings.get_settings().auto_resume:
                shutil.rmtree(folder, ignore_errors=True)

    async def _probe(self, fn, *args):
        return await asyncio.get_running_loop().run_in_executor(
            self.ctx.thread, partial(fn, *args)
        )

    async def _needs_sound(self, temp):
        """True when the joined copy should have sound it lacks: its separate
        audio track was refused, or its playlist says the video segments
        carry sound and they don't."""
        if getattr(self, "audio_refused", None):
            return True
        if not getattr(self, "audio_inside", False):
            return False
        ffprobe = get_ffprobe()
        return bool(ffprobe) and not await self._probe(_has_packets, ffprobe, temp, "a:0")

    async def _sound_from_direct(self, c, folder, temp, video_input, dash, deadline, medialog):
        """Add the direct file's sound to the joined stream video.

        The stream is chosen for its larger video; the direct MP4 of the same
        upload usually carries the sound the stream's audio track lacks. The
        result replaces ``temp`` only if it passes the checks. Anything else,
        a failure of any kind included (ffmpeg's time limit, an ffprobe
        error, a locked file, a full disk), keeps ``temp`` as the silent copy,
        with a warning for a refused track."""
        joined = temp.with_name(temp.name + ".sound")
        try:
            problem = await self._add_direct_sound(
                c, folder, temp, joined, video_input, dash, deadline, medialog
            )
        except Exception as e:
            problem = f"taking the sound from the direct file failed: {e}"
        finally:
            with contextlib.suppress(OSError):
                joined.unlink(missing_ok=True)
        if problem:
            self.ctx.log.info(f"{medialog} {problem}")
            if getattr(self, "audio_refused", None):
                self._warn_silent(medialog)

    async def _add_direct_sound(self, c, folder, temp, joined, video_input, dash, deadline,
                                medialog):
        """``_sound_from_direct``'s steps. Returns why the sound wasn't added,
        or None when it was (or the video has no sound to add)."""
        ele = getattr(self, "ele", None)
        raw = fansly_video.raw_media(ele) if ele is not None else None
        ffprobe = get_ffprobe()
        loop = asyncio.get_running_loop()
        if not (ele.url if ele is not None else None) or not fansly_video.has_direct(raw):
            return "there is no direct file to take the sound from"
        if not ffprobe:
            return "ffprobe is not found to check the direct file's sound"
        direct = folder / "direct.mp4"
        try:
            await self._fetch_direct(c, ele, direct, deadline)
        except (SegmentError, asyncio.TimeoutError) as e:
            return f"the direct file could not be fetched for its sound: {e}"
        sound = await self._probe(_audio_stream, ffprobe, direct)
        if sound is None:
            # an error page or a cut-off file says nothing about the sound
            return "the direct file could not be read to check its sound"
        if not sound:
            # evidence the video has no sound at all: nothing was lost
            self.ctx.log.info(
                f"{medialog} the direct file has no sound either; saving the video as it is"
            )
            self.audio_refused = None
            self.audio_inside = False
            return None
        codec = await self._probe(_codec, ffprobe, direct, "a:0")
        if codec not in COPYABLE_AUDIO:
            return f"the direct file's sound is {codec or 'of an unknown kind'}, not AAC"
        self._check_sound_space(temp, direct)
        video_at, sound_at = [
            await self._probe(_first_shown, ffprobe, direct, stream)
            for stream in ("v:0", "a:0")
        ]
        frame = _frame(await self._probe(_packet_times, ffprobe, direct, "v:0", True))
        if video_at is None or sound_at is None or not frame:
            return "the direct file could not be measured"
        # ffmpeg starts each input at its own first packet. The direct file's
        # sound keeps its place from that file's start; the stream's video is
        # given the place the direct file's video has. Most saved Fansly
        # videos show their first frame two frames after the sound starts
        # (frames stored ahead, no edit list). A later start than that is not
        # carried over: nothing shows that the stream's video has it too.
        late = video_at - sound_at
        if late > SOUND_FRAMES * frame + 0.001:
            return (
                f"the direct file's video starts {late:.3f}s after its sound, more "
                f"than {SOUND_FRAMES} frames, so the sound could be out of step "
                "with the stream's video"
            )
        cmd = fansly_video.local_join_command(
            get_ffmpeg(), video_input, joined.absolute(), dash=dash,
            audio_file=direct.name, video_delay=max(0.0, late),
        )
        await self._run_cmd(
            cmd, joined, max(1.0, deadline - loop.time()),
            "add the direct file's sound", cwd=folder,
        )
        problem = await self._sound_mismatch(ffprobe, direct, joined, ele)
        if problem:
            return problem
        joined.replace(temp)
        self.ctx.log.info(
            f"{medialog} took the sound from the direct file"
            + (f" (the CDN refused {self.audio_refused})" if self.audio_refused else "")
        )
        self.audio_refused = None
        return None

    def _check_sound_space(self, temp, direct):
        """Fail when the drive can't hold the copy with sound next to ``temp``."""
        need = temp.stat().st_size + direct.stat().st_size + JOIN_SPACE_MARGIN
        free = _free_space(pathlib.Path(temp).parent)
        if free < need:
            raise NotEnoughSpace(
                f"not enough disk space to add the sound: needs about "
                f"{format_size(need)}, {format_size(free)} free"
            )

    async def _fetch_direct(self, c, ele, path, deadline):
        """The direct file into ``path``, kept for resume. A signed link the
        CDN refuses gets a new one, once."""
        loop = asyncio.get_running_loop()
        for ask in range(2):
            if path.is_file():
                return
            try:
                # a signed URL: no CloudFront cookies
                await asyncio.wait_for(
                    self._fetch_segment(c, fansly_video.check_url(ele.url), path, None),
                    max(0.01, deadline - loop.time()),
                )
                return
            except fansly_video.StreamError as e:
                raise SegmentError(str(e)) from e
            except SegmentError as e:
                if ask or not _refused(e):
                    raise
                # within the download's time limit, as the fetch is
                if not await asyncio.wait_for(
                    refresh_media_link(ele), max(0.01, deadline - loop.time())
                ):
                    raise

    async def _sound_mismatch(self, ffprobe, direct, joined, ele):
        """Why the joined copy can't be kept, or None.

        Both files come from one upload, so their videos should line up. The
        sound must keep the start it had against the direct file's video (the
        join delays the stream's video for that), within one frame. The
        starts compared are when each
        stream is first shown (``_first_shown``). A trimmed or re-timed
        rendition would put the sound out of step by the difference in
        length."""
        direct_video, direct_audio, joined_video, joined_audio = [
            await self._probe(_packet_times, ffprobe, path, stream, True)
            for path, stream in (
                (direct, "v:0"), (direct, "a:0"), (joined, "v:0"), (joined, "a:0")
            )
        ]
        if not (direct_video and direct_audio and joined_video and joined_audio):
            return "the joined copy could not be measured"
        frame = max(_frame(direct_video), _frame(joined_video))
        margin = SOUND_FRAMES * frame + 0.001
        shown = [
            await self._probe(_first_shown, ffprobe, path, stream)
            for path, stream in (
                (direct, "v:0"), (direct, "a:0"), (joined, "v:0"), (joined, "a:0")
            )
        ]
        if any(at is None for at in shown):
            return "the joined copy could not be measured"
        direct_offset = shown[1] - shown[0]
        joined_offset = shown[3] - shown[2]
        if abs(joined_offset - direct_offset) > frame + 0.001:
            return (
                f"the direct file's sound starts {direct_offset:+.3f}s from its video, "
                f"but {joined_offset:+.3f}s from the stream's, so it would be out of step"
            )
        stream_length = fansly_video.timeline(joined_video)[0]
        direct_length = fansly_video.timeline(direct_video)[0]
        if not stream_length or not direct_length:
            return "the joined copy could not be measured"
        if abs(stream_length - direct_length) > margin:
            return (
                f"the direct file's video ({direct_length:.2f}s) and the stream's "
                f"({stream_length:.2f}s) differ in length, so the sound would be out of step"
            )
        sound_length = fansly_video.timeline(joined_audio)[0]
        # where each ends, not how long each is: the video may start after
        # the sound (the delay the join gave it)
        video_end = shown[2] + stream_length
        sound_end = shown[3] + sound_length
        if sound_end > video_end + margin:
            return "the direct file's sound is longer than the stream's video"
        short = max(fansly_video.SHORT_MIN, fansly_video.SHORT_SHARE * stream_length)
        if sound_end < video_end - short:
            return (
                f"the direct file's sound covers {sound_length:.1f}s of the "
                f"{stream_length:.1f}s video"
            )
        reason = fansly_video.incomplete_reason(
            joined_video, joined_audio,
            fansly_video.expected_duration(fansly_video.raw_media(ele)),
        )
        return f"the copy with the direct file's sound is incomplete: {reason}" if reason else None

    def _check_join_space(self, folder, temp, dash=False):
        """Fail with a clear message when the .part's drive can't hold the
        joined copy (about the segments' size) next to the segments."""
        size = sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
        need = size * (2 if dash else 1) + max(JOIN_SPACE_MARGIN, size // 20)
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
                if not (folder / name).is_file():
                    await self._fetch_segment(c, url, folder / name, cookies)

        workers = [
            asyncio.ensure_future(worker())
            for _ in range(min(segment_limit(), len(jobs)))
        ]
        try:
            await asyncio.gather(*workers)
        except BaseException:
            # let every worker finish and close its file before cleanup
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
                    temp = path.with_name(path.name + ".tmp")
                    await self._fetch_segment_once(c, url, temp, cookies)
                    temp.replace(path)
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
            url, audio_url, self.audio_inside = fansly_video.best_rendition_info(
                manifest, best.url
            )
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
            self.ctx.log.warning(
                f"{common_logs.get_medialog(ele)} ffprobe not found; "
                "the stream copy can't be checked for skipped segments"
            )
            return
        loop = asyncio.get_event_loop()
        video_times, audio_times = [
            await loop.run_in_executor(
                self.ctx.thread, partial(_packet_times, ffprobe, temp, stream)
            )
            for stream in ("v:0", "a:0")
        ]
        if getattr(self, "audio_inside", False) and not audio_times:
            # the playlist said the video segments carry the sound: keep the
            # video, as the website would play it, and say why it is silent
            self.ctx.log.warning(
                f"{common_logs.get_medialog(ele)} the stream's video segments have no "
                "audio, though its playlist lists an audio format; saving the video "
                "without sound"
            )
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
        job = self.ctx.thread.submit(_run_process, proc, cmd, timeout, cwd)
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

    async def _replace_silent(self, temp, ele):
        """Downloading a silent video again (see ``silent.recheck``): keep the
        new copy only if it has sound. ``_finish`` puts it in the silent
        copy's place."""
        old = getattr(ele, "replace_silent", None)
        if not old:
            return
        ffprobe = get_ffprobe()
        if getattr(self, "audio_refused", None) or not (
            ffprobe and await self._probe(_has_packets, ffprobe, temp, "a:0")
        ):
            # silent.recheck counts this as refused again
            ele.still_silent = True
            raise Exception("still without sound; the saved copy is kept")

    def _replace_in_place(self, temp, old):
        """Move ``temp`` next to the silent copy at ``old``, then replace it in
        one step (``os.replace``): the silent copy stays until the new one is
        whole beside it."""
        old = pathlib.Path(old)
        beside = old.with_name(old.name + ".sound.part")
        # the silent copy may have been moved away with its folder
        old.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(temp), str(beside))
            os.replace(beside, old)
        except BaseException:
            beside.unlink(missing_ok=True)
            raise
        return old

    async def _remember_sound(self, model_id, ele, path_to_file):
        """Flag a video saved silent because its audio was refused, so its
        audio is checked again; a video saved with sound needs no checks."""
        try:
            if getattr(self, "audio_refused", None):
                await self._probe(silent.flag, model_id, ele, path_to_file)
            else:
                await self._probe(silent.clear, model_id, ele.id)
        except Exception as e:
            self.ctx.log.debug(
                f"{common_logs.get_medialog(ele)} could not record whether it has sound: "
                f"{type(e).__name__}"
            )

    async def audio_check(self, c, raw):
        """Whether the CDN gives a video's audio now (``silent.recheck``):
        its audio playlist and first audio file, with ``raw``'s links."""
        best = fansly_video.select_best(raw)
        if not best or not best.is_stream:
            return silent.GONE
        try:
            url, audio_url = await self._stream_urls(c, best)
        except Exception:
            # the master playlist itself: says nothing about the audio
            return silent.FAILED
        try:
            if best.kind == fansly_video.DASH:
                tracks = fansly_video.local_dash(
                    await self._fetch_text(c, url, best.cookies), url
                )
                audio = tracks[1] if len(tracks) > 1 else None
            elif audio_url:
                audio = fansly_video.local_playlist(
                    await self._fetch_text(c, audio_url, best.cookies), audio_url, "a"
                )
            else:
                # the playlist now says the video segments carry the sound
                return silent.ACCEPTED if self.audio_inside else silent.GONE
            if not audio or not audio.files:
                return silent.GONE
            # a file that carries sound: a key or an init segment can be
            # served when the media isn't
            sample = (
                audio.files[min(1, len(audio.files) - 1)][0]
                if best.kind == fansly_video.DASH
                else fansly_video.first_media_url(audio.files)
            )
            if not sample:
                return silent.GONE
            async with c.requests_async(
                url=sample, cookies=best.cookies or None,
                actions=[HEADERS], headers={"Range": "bytes=0-0"}, retries=1,
            ) as r:
                if r.status in (401, 403):
                    return silent.REFUSED
                return silent.ACCEPTED if r.ok else silent.FAILED
        except Exception as e:
            return silent.REFUSED if _refused(e) else silent.FAILED

    async def _integrity_check(self, temp, ele):
        if not settings.get_settings().verify_all_integrity:
            return
        expected = ele.duration
        loop = asyncio.get_event_loop()
        if expected:
            ok = await loop.run_in_executor(
                self.ctx.thread, partial(verify_media_integrity, temp, expected)
            )
        else:
            ok = (
                await loop.run_in_executor(
                    self.ctx.thread, partial(get_media_duration, temp)
                )
            ) is not None
        if not ok:
            temp.unlink(missing_ok=True)
            raise Exception("Fansly stream download failed the integrity check")

    async def _finish(self, temp, placeholderObj, ele, username, model_id, total):
        loop = asyncio.get_event_loop()
        old = getattr(ele, "replace_silent", None)
        if old:
            # a silent copy downloaded again with sound takes its place
            try:
                path_to_file = await loop.run_in_executor(
                    self.ctx.thread, partial(self._replace_in_place, temp, old)
                )
            except OSError as E:
                # in use, read-only, a full disk, a drive that is gone: the
                # next download would end the same, so this uses a check
                ele.not_kept = f"the saved copy could not be replaced ({type(E).__name__})"
                raise
        else:
            # can end up under another name if a different file already has this one (#48)
            path_to_file = await loop.run_in_executor(
                self.ctx.thread,
                partial(common_paths.moveHelper, temp, placeholderObj.trunicated_filepath, ele),
            )
        common_paths.addGlobalDir(path_to_file.parent, self.ctx.dirSet)
        if ele.postdate:
            await loop.run_in_executor(
                self.ctx.thread,
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
                hashdata=await common.get_hash(path_to_file, self.ctx.thread),
                size=path_to_file.stat().st_size,
            )
        await set_profile_cache(ele, self.ctx.thread)
        await self._remember_sound(model_id, ele, path_to_file)
        ele.add_filepath(path_to_file)
        ele.add_size(total)
        await self._after_download_script(path_to_file)
        return ele.mediatype, total
