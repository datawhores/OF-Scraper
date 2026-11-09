import asyncio
import pathlib
import re
import traceback
from functools import partial
from urllib.parse import urlsplit, urlunsplit

import aiofiles
import arrow
import psutil
from humanfriendly import format_size
import aiohttp

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.actions.utils.general as common
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.commands.scraper.actions.utils.paths as common_paths
import ofscraper.commands.scraper.actions.utils.log as common_logs
from ofscraper.commands.scraper.actions.utils.log import (
    get_medialog,
    path_to_file_logger,
    temp_file_logger,
)
from ofscraper.commands.scraper.actions.utils.params import get_alt_params
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.dates as dates
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.system.system as system
from ofscraper.utils.system.subprocess import async_run
from ofscraper.utils.system.ffprobe import verify_media_integrity
import ofscraper.utils.live.updater as progress_updater

from ofscraper.commands.scraper.actions.download.managers.downloadmanager import (
    DownloadManager,
    StartOver,
)
from ofscraper.commands.scraper.actions.download.utils.retries import (
    download_retry,
    get_download_retries,
)
from ofscraper.commands.scraper.actions.download.utils.chunk import (
    get_chunk_size,
    get_chunk_timeout,
)
from ofscraper.commands.scraper.actions.utils.chunk import send_chunk_msg
import ofscraper.commands.scraper.actions.download.utils.keyhelpers as keyhelpers
from ofscraper.utils.system.ffmpeg import get_ffmpeg

from ofscraper.classes.of.media import Media
from ofscraper.db.operations_.media import mark_media_as_downloaded


class AltDownloadManager(DownloadManager):

    async def alt_download(self, c, ele: Media, username, model_id):
        # Acquire semaphore at the very beginning of the process
        await common_globals.sem.acquire()
        try:
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} Downloading with protected media downloader"
            )

            sharedPlaceholderObj = await placeholder.Placeholders(ele, "mp4").init()
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} download url:  {common_logs.get_url_log(ele)}"
            )

            audio = await ele.mpd_audio
            video = await ele.mpd_video
            path_to_file_logger(sharedPlaceholderObj, ele)

            # Only attempt to download tracks that actually exist. The size
            # limits are for the whole video (#316): they're checked once the
            # last track's size is known, on its size plus the audio's
            mediatype = ele.mediatype
            if audio:
                audio = await self._alt_download_downloader(
                    audio, c, ele, before=None if video else 0
                )
            if video:
                video = await self._alt_download_downloader(
                    video, c, ele, before=audio["total"] if audio else 0
                )
            if ele.mediatype != mediatype or any(
                track and track["total"] == 0 for track in (audio, video)
            ):
                # a size limit changes the mediatype; skip_download_script
                # skips a track without changing it, and leaves its total 0
                # (#325). Either way the item is skipped and its tracks
                # aren't kept: a DRM video is no use with a track missing.
                # Nothing after this reads ele.mpd, which a new mediatype
                # makes None
                for track in (audio, video):
                    if track:
                        pathlib.Path(track["path"]).unlink(missing_ok=True)
                return "forced_skipped", 0

            # Safely calculate total size
            audio_size = audio["total"] if audio else 0
            video_size = video["total"] if video else 0
            ele.add_size(audio_size + video_size)

            post_result = await self._media_item_post_process_alt(
                audio, video, ele, username, model_id
            )
            if post_result:
                return post_result

            await self._media_item_keys_alt(c, audio, video, ele)

            return await self._handle_result_alt(
                sharedPlaceholderObj, ele, audio, video, username, model_id
            )
        finally:
            common_globals.sem.release()

    async def _alt_download_downloader(self, item, c, ele, before=0):
        """Download one track. before is the size of the tracks already
        downloaded: the size limits are checked on it plus this track's
        size. None checks no limits (another track comes after this one)."""
        self._downloadspace()
        placeholderObj = await placeholder.tempFilePlaceholder(
            ele, f"{item['name']}.part"
        ).init()
        item["path"] = placeholderObj.tempfilepath
        item["total"] = None
        item["validator"] = None
        item["before"] = before

        _attempt = self._alt_attempt_get(item)
        _attempt.set(0)

        async for _ in download_retry():
            with _:
                try:
                    _attempt = self._alt_attempt_get(item)
                    _attempt.set(_attempt.get(0) + 1)
                    # a retry keeps the part and resumes it (#268): the saved
                    # size checks it, as on the next run
                    data = await self._get_data(ele, item)
                    status = False
                    if data:
                        item, status = await self._resume_data_handler_alt(
                            data, item, ele, placeholderObj
                        )

                    else:
                        item, status = await self._fresh_data_handler_alt(
                            item, ele, placeholderObj
                        )
                    if not status:
                        try:
                            item = await self._alt_download_sendreq(
                                item, c, ele, placeholderObj
                            )
                        except Exception as E:
                            raise E
                    return item
                except OSError as E:
                    common_globals.log.debug(
                        f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] Number of Open Files -> { len(psutil.Process().open_files())}"
                    )
                    common_globals.log.debug(
                        f" {get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] Open Files -> {list(map(lambda x:(x.path,x.fd),psutil.Process().open_files()))}"
                    )
                    raise E
                except Exception as E:
                    common_globals.log.traceback_(
                        f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] {traceback.format_exc()}"
                    )
                    common_globals.log.traceback_(
                        f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] {E}"
                    )
                    raise E

    async def _alt_download_sendreq(self, item, c, ele, placeholderObj):
        try:
            _attempt = self._alt_attempt_get(item)
            url = _mpd_segment_url(ele.mpd, item["origname"])
            common_globals.log.debug(
                f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}"
            )
            common_globals.log.debug(
                f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] download temp path {placeholderObj.tempfilepath}"
            )
            try:
                return await self._send_req_inner(c, ele, item, placeholderObj)
            except StartOver as E:
                # the part was deleted; ask for the whole track, without a range
                common_globals.log.debug(f"{get_medialog(ele)} {E}")
                item["total"] = None
                item["validator"] = None
                return await self._send_req_inner(c, ele, item, placeholderObj)
        except OSError as E:
            raise E
        except Exception as E:
            raise E

    async def _send_req_inner(self, c, ele, item, placeholderObj):
        total = None
        try:

            resume_size = self._get_resume_size(placeholderObj)
            saved_total = item["total"]
            headers = self._get_resume_header(
                resume_size, saved_total, item.get("validator")
            )
            # reset total
            total = None
            common_globals.log.debug(f"{get_medialog(ele)} resume header {headers}")
            params = get_alt_params(ele)
            url = _mpd_segment_url(ele.mpd, item["origname"])
            headers = {
                **(headers or {}),
                "Cookie": f"{ele.hls_header}{auth_requests.get_cookies_str()}",
            }
            common_globals.log.debug(
                f"{get_medialog(ele)} [attempt {self._alt_attempt_get(item).get()}/{get_download_retries()}] Downloading media with url  {url}"
            )
            async with c.requests_async(
                url=url,
                stream=True,
                headers=headers,
                params=params,
                total_timeout=None,
                read_timeout=get_chunk_timeout(),
            ) as l:
                self._check_status(l, ele, headers)
                content_type = (l.headers.get("content-type") or "").lower()
                asked = resume_size
                try:
                    total, resume_size = self._full_size_from_reply(
                        l, resume_size, placeholderObj.tempfilepath, saved_total
                    )
                except (TypeError, ValueError):
                    total = None
                item["total"] = total
                self._check_same_file(
                    l, resume_size, placeholderObj.tempfilepath, item.get("validator")
                )

                if any(
                    x in content_type
                    for x in ("dash+xml", "mpegurl", "application/xml", "text/xml")
                ):
                    raise Exception(
                        f"{get_medialog(ele)} DRM segment returned playlist "
                        f"content-type={content_type!r} url={url}"
                    )
                if total is not None and total <= 0:
                    raise Exception(
                        f"{get_medialog(ele)} DRM segment empty size "
                        f"(content-type={content_type or 'unknown'}, url={url})"
                    )

                data = {
                    "content-total": total,
                    "content-type": l.headers.get("content-type"),
                    # the validator of the reply that started the part: a
                    # resume keeps the saved one
                    "validator": (
                        item.get("validator") if resume_size else self._validator(l)
                    ),
                }

                common_globals.log.debug(
                    f"{get_medialog(ele)} data from request {data}"
                )
                common_globals.log.debug(
                    f"{get_medialog(ele)} total from request {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}"
                )
                temp_file_logger(placeholderObj, ele)
                if await self._check_forced_skip(ele, total, item.get("before", 0)) == 0:
                    if asked and not resume_size:
                        # a whole-file reply to a resume: the part is stale
                        pathlib.Path(placeholderObj.tempfilepath).unlink(
                            missing_ok=True
                        )
                    await self._set_data(ele, item, data)
                    item["total"] = 0
                    total = item["total"]
                    return item
                elif total != resume_size:
                    # the part and its saved size and validator are replaced
                    # only once the reply's first bytes arrive (#271)
                    written = await self._download_fileobject_writer(
                        total,
                        l,
                        ele,
                        placeholderObj,
                        item,
                        resume_size,
                        partial(self._set_data, ele, item, data),
                    )
                    if total is None:
                        total = self._size_written(ele, written)
                        item["total"] = total
                    await self._total_change_helper(total)

            await self._size_checker(placeholderObj.tempfilepath, ele, total)
            return item
        except Exception as E:
            await self._total_change_helper(0)
            raise E

    async def _download_fileobject_writer(
        self, total, l, ele, placeholderObj, item, resume_size=0, on_first_chunk=None
    ):
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {self._alt_attempt_get(item).get()}/{get_download_retries()}] writing media to disk"
        )
        written = await self._download_fileobject_writer_streamer(
            ele, total, l, placeholderObj, resume_size, on_first_chunk
        )
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {self._alt_attempt_get(item).get()}/{get_download_retries()}] finished writing media to disk"
        )
        return written

    async def _download_fileobject_writer_streamer(
        self, ele, total, res, placeholderObj, resume_size=0, on_first_chunk=None
    ):
        """Write the reply to the part and return the bytes written. The part
        is opened on the first chunk: appended to when resuming, else
        replaced from 0. Until then the part on disk is left as it was, so a
        reply with no data doesn't cost it (#271). on_first_chunk runs once
        the first chunk is written."""
        task1 = await self._add_download_job_task(ele, total, placeholderObj)
        fileobject = None
        written = 0
        try:
            chunk_iter = res.iter_chunked(get_chunk_size())

            while True:
                try:
                    chunk = await chunk_iter.__anext__()
                    first = fileobject is None
                    if first:
                        fileobject = await aiofiles.open(
                            placeholderObj.tempfilepath, "ab" if resume_size else "wb"
                        ).__aenter__()
                    await fileobject.write(chunk)
                    written += len(chunk)
                    if first and on_first_chunk:
                        await on_first_chunk()
                    send_chunk_msg(ele, total, placeholderObj)
                except StopAsyncIteration:
                    break  # Exit loop when no more chunks

        # Catch native aiohttp socket read timeouts
        except (asyncio.TimeoutError, aiohttp.ServerTimeoutError) as E:
            common_globals.log.info(
                f"{common_logs.get_medialog(ele)}⚠️ CDN went silent (sock_read timeout). Connection stalled, forcing retry!"
            )
            raise Exception("Chunk download timed out")
        except Exception as E:
            common_globals.log.info(f"An error occurred during download for {ele}: {E}")
            raise E
        finally:
            if fileobject:
                try:
                    await fileobject.close()
                except Exception as E:
                    common_globals.log.debug(f"Error closing file for {ele}: {E}")
                    raise E
            try:
                await self._remove_download_job_task(task1, ele)
            except Exception as E:
                common_globals.log.debug(
                    f"Error removing download job task for {ele}: {E}"
                )
                raise E
        return written

    async def _handle_result_alt(
        self, sharedPlaceholderObj, ele, audio, video, username, model_id
    ):
        tempPlaceholder = await placeholder.tempFilePlaceholder(
            ele, f"temp_{ele.id or await ele.final_filename}.mp4"
        ).init()
        temp_path = tempPlaceholder.tempfilepath
        temp_path.unlink(missing_ok=True)

        # Dynamically build FFmpeg command based on available tracks
        ffmpeg_cmd = [get_ffmpeg()]
        if video:
            ffmpeg_cmd.extend(["-i", str(video["path"])])
        if audio:
            ffmpeg_cmd.extend(["-i", str(audio["path"])])

        ffmpeg_cmd.extend(
            [
                "-c",
                "copy",
                "-movflags",
                "use_metadata_tags",
                str(temp_path),
                "-y",
            ]
        )

        # Async run FFmpeg with the -y flag
        t = await async_run(
            ffmpeg_cmd,
            name="ffmpeg",
            level=of_env.getattr("FFMPEG_SUBPROCESS_LEVEL"),
        )

        # Fallback error check if stderr is captured and Output is missing
        if t.stderr and t.stderr.decode().find("Output") == -1:
            common_globals.log.debug(f"{common_logs.get_medialog(ele)} ffmpeg failed")
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} ffmpeg {t.stderr.decode()}"
            )
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} ffmpeg {t.stdout.decode()}"
            )

        # Clean up temp tracks
        if video:
            video["path"].unlink(missing_ok=True)
        if audio:
            audio["path"].unlink(missing_ok=True)

        expected_duration = ele.duration
        if not verify_media_integrity(temp_path, expected_duration):
            common_globals.log.warning(
                f"DRM Merge failed integrity check for {ele.id}: {temp_path}"
            )
            temp_path.unlink(missing_ok=True)
            raise Exception("Merged DRM media failed integrity check")

        common_globals.log.debug(
            f"Moving intermediate path {temp_path} to {sharedPlaceholderObj.trunicated_filepath}"
        )

        # Thread executor for disk I/O move operation; the file can end up
        # under another name if a different file already has this one (#48)
        final_path = await asyncio.get_event_loop().run_in_executor(
            common_globals.thread,
            partial(
                common_paths.moveHelper,
                temp_path,
                sharedPlaceholderObj.trunicated_filepath,
                ele,
            ),
        )

        (common_paths.addGlobalDir(final_path.parent))

        if ele.postdate:
            newDate = dates.convert_local_time(ele.postdate)
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}"
            )
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread,
                partial(
                    common_paths.set_time,
                    final_path,
                    newDate,
                ),
            )

        if ele.id:
            await mark_media_as_downloaded(
                ele,
                filepath=final_path,
                model_id=model_id,
                username=username,
                downloaded=True,
                hashdata=await common.get_hash(final_path),
                size=final_path.stat().st_size,
            )
        ele.add_filepath(final_path)

        await self._after_download_script(final_path)

        audio_total = audio["total"] if audio else 0
        video_total = video["total"] if video else 0
        return ele.mediatype, video_total + audio_total

    async def _resume_data_handler_alt(self, data, item, ele, placeholderObj):
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] using data for possible download resumption"
        )
        common_globals.log.debug(f"{get_medialog(ele)} Data from cache{data}")
        common_globals.log.debug(
            f"{get_medialog(ele)} Total size from cache {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}"
        )
        total = int(data.get("content-total")) if data.get("content-total") else None
        item["total"] = total
        item["validator"] = data.get("validator")
        resume_size = self._get_resume_size(placeholderObj)
        resume_size = self._resume_cleaner(
            resume_size, total, placeholderObj.tempfilepath
        )

        common_globals.log.debug(
            f"{get_medialog(ele)} resume_size: {resume_size}  and total: {total }"
        )

        if total is None or int(total) <= 0:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    common_globals.thread,
                    partial(
                        cache.set,
                        f"{item['name']}_{ele.id}_{ele.username}_headers",
                        None,
                    ),
                )
            except Exception:
                pass
            return item, False

        if await self._check_forced_skip(ele, total, item.get("before", 0)) == 0:
            item["total"] = 0
            return item, True
        elif total == resume_size:
            common_globals.log.debug(
                f"{get_medialog(ele)} total==resume_size skipping download"
            )
            temp_file_logger(placeholderObj, ele)
            if self._alt_attempt_get(item).get() == 0:
                pass
            return item, True
        elif total != resume_size:
            return item, False

    async def _fresh_data_handler_alt(self, item, ele, placeholderObj):
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] fresh download for media"
        )
        resume_size = self._get_resume_size(placeholderObj)
        common_globals.log.debug(f"{get_medialog(ele)} resume_size: {resume_size}")
        return item, False

    def _alt_attempt_get(self, item):
        if item["type"] == "video":
            return common_globals.attempt
        if item["type"] == "audio":
            return common_globals.attempt2

    async def _get_data(self, ele, item):
        data = await asyncio.get_event_loop().run_in_executor(
            common_globals.thread,
            partial(cache.get, f"{item['name']}_{ele.id}_{ele.username}_headers"),
        )
        return data

    async def _set_data(self, ele, item, data):
        data = await asyncio.get_event_loop().run_in_executor(
            common_globals.thread,
            partial(cache.set, f"{item['name']}_{ele.id}_{ele.username}_headers", data),
        )
        return data

    def _get_item_total(self, item):
        return item["path"].absolute().stat().st_size

    async def _media_item_post_process_alt(self, audio, video, ele, username, model_id):
        audio_total = audio["total"] if audio else 0
        video_total = video["total"] if video else 0

        if (audio_total + video_total) == 0:
            if ele.mediatype.capitalize() == "Forced_skipped":
                return ele.mediatype, 0
            raise Exception(
                f"{get_medialog(ele)} DRM download produced 0 bytes "
                "(audio+video). Not marking as downloaded."
            )

        for m in [audio, video]:
            if m is not None:
                m["total"] = self._get_item_total(m)

        for m in [audio, video]:
            if m is not None:
                if not isinstance(m, dict):
                    return m
                await self._size_checker(m["path"], ele, m["total"])

    async def _media_item_keys_alt(self, c, audio, video, ele):
        async for _ in download_retry():
            with _:
                try:
                    for item in [audio, video]:
                        if item is not None:
                            item = await keyhelpers.un_encrypt(item, c, ele)
                except Exception as E:
                    common_globals.log.traceback_(E)
                    common_globals.log.traceback_(traceback.format_exc())
                    raise E

    async def _add_download_job_task(self, ele, total=None, placeholderObj=None):
        pathstr = str(placeholderObj.tempfilepath)
        task1 = progress_updater.download.add_job_task(
            f"{(pathstr[:of_env.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > of_env.getattr('PATH_STR_MAX') else pathstr}\n",
            total=total,
        )
        return task1

def _mpd_segment_url(mpd_url: str, segment_name: str) -> str:
    parts = urlsplit((mpd_url or "").strip())
    name = (segment_name or "").strip().lstrip("/")
    path = parts.path or ""
    base_path = re.sub(r"[^/]+\.mpd$", "", path, flags=re.IGNORECASE)
    if base_path == path:
        base_path = (path.rsplit("/", 1)[0] + "/") if "/" in path else "/"
    elif not base_path.endswith("/"):
        base_path += "/"
    return urlunsplit((parts.scheme, parts.netloc, base_path + name, parts.query, ""))

