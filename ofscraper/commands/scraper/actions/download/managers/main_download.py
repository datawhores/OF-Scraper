import asyncio
import pathlib
import traceback
from functools import partial

import aiofiles
import psutil
from humanfriendly import format_size
import aiohttp

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.actions.utils.general as common
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.commands.scraper.actions.utils.paths as common_paths
import ofscraper.commands.scraper.actions.utils.log as common_logs
import ofscraper.utils.dates as dates
import ofscraper.utils.system.system as system
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.settings as settings
from ofscraper.utils.system.ffprobe import verify_media_integrity
from ofscraper.utils.cache.profile import set_profile_cache

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

from ofscraper.classes.of.media import Media
from ofscraper.db.operations_.media import mark_media_as_downloaded


class MainDownloadManager(DownloadManager):

    async def main_download(self, c, ele: Media, username, model_id):
        await common_globals.sem.acquire()
        try:
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} Downloading with normal downloader"
            )
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} download url:  {common_logs.get_url_log(ele)}"
            )
            if common.is_bad_url(ele.url):
                common_globals.log.debug(
                    f"{common_logs.get_medialog(ele)} Forcing download because known bad url"
                )
                await self._force_download(ele, username, model_id)
                return ele.mediatype, 0

            result = await self._main_download_downloader(c, ele)
            ele.add_size(result[0])

            if result[0] == 0:
                if ele.mediatype.capitalize() != "Forced_skipped":
                    await self._force_download(ele, username, model_id)
                return ele.mediatype.capitalize(), 0

            return await self._handle_result_main(result, ele, username, model_id)

        finally:
            common_globals.sem.release()

    async def _main_download_downloader(self, c, ele):
        self._downloadspace()
        tempholderObj = await placeholder.tempFilePlaceholder(
            ele, f"{ele.filename}_{ele.id}_{ele.post_id}.part"
        ).init()

        common_globals.attempt.set(0)

        async for _ in download_retry():
            with _:
                try:
                    common_globals.attempt.set(common_globals.attempt.get(0) + 1)
                    # a retry keeps the part and resumes it (#268): the saved
                    # size checks it, as on the next run
                    data = await self._get_data(ele)
                    total = None
                    validator = (data or {}).get("validator")
                    placeholderObj = None
                    status = False
                    if data:
                        total, placeholderObj, status = (
                            await self._resume_data_handler_main(
                                data, ele, tempholderObj
                            )
                        )
                    else:
                        await self._fresh_data_handler_main(ele, tempholderObj)
                    if not status:
                        try:
                            return await self._main_download_sendreq(
                                c,
                                ele,
                                tempholderObj,
                                placeholderObj=placeholderObj,
                                total=total,
                                validator=validator,
                            )
                        except Exception as E:
                            raise E
                    else:
                        return (
                            total,
                            tempholderObj.tempfilepath,
                            placeholderObj,
                        )

                except OSError as E:
                    common_globals.log.debug(
                        f"[{common_logs.get_medialog(ele)}] [attempt {common_globals.attempt.get()}/{get_download_retries()}] Number of Open Files -> { len(psutil.Process().open_files())}"
                    )
                    if self._skipped_by_size(ele, E):
                        pathlib.Path(tempholderObj.tempfilepath).unlink(missing_ok=True)
                        return (0, tempholderObj.tempfilepath, None)
                    raise E
                except Exception as E:
                    common_globals.log.traceback_(
                        f"{common_logs.get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] {traceback.format_exc()}"
                    )
                    common_globals.log.traceback_(
                        f"{common_logs.get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] {E}"
                    )
                    if self._skipped_by_size(ele, E):
                        pathlib.Path(tempholderObj.tempfilepath).unlink(missing_ok=True)
                        return (0, tempholderObj.tempfilepath, None)
                    raise E

    async def _main_download_sendreq(
        self, c, ele, tempholderObj, placeholderObj=None, total=None, validator=None
    ):
        try:
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] download temp path {tempholderObj.tempfilepath}"
            )
            try:
                return await self._send_req_inner(
                    c,
                    ele,
                    tempholderObj,
                    placeholderObj=placeholderObj,
                    total=total,
                    validator=validator,
                )
            except StartOver as E:
                # the part was deleted; ask for the whole file, without a range
                common_globals.log.debug(f"{common_logs.get_medialog(ele)} {E}")
                return await self._send_req_inner(
                    c, ele, tempholderObj, placeholderObj=placeholderObj, total=None
                )
        except OSError as E:
            raise E
        except Exception as E:
            raise E

    async def _send_req_inner(
        self, c, ele, tempholderObj, placeholderObj=None, total=None, validator=None
    ):
        try:
            resume_size = self._get_resume_size(tempholderObj)
            headers = self._get_resume_header(resume_size, total, validator)
            saved_total, total = total, None
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] Downloading media with url {ele.url}"
            )

            async with c.requests_async(
                url=ele.url,
                stream=True,
                headers=headers,
                total_timeout=None,
                read_timeout=get_chunk_timeout(),
            ) as r:
                self._check_status(r, ele, headers)
                asked = resume_size
                total, resume_size = self._full_size_from_reply(
                    r, resume_size, tempholderObj.tempfilepath, saved_total
                )
                self._check_same_file(
                    r, resume_size, tempholderObj.tempfilepath, validator
                )
                data = {
                    "content-total": total,
                    "content-type": r.headers.get("content-type"),
                    # the validator of the reply that started the part: a
                    # resume keeps the saved one
                    "validator": validator if resume_size else self._validator(r),
                }

                common_globals.log.debug(
                    f"{common_logs.get_medialog(ele)} data from request {data}"
                )
                common_globals.log.debug(
                    f"{common_logs.get_medialog(ele)} total from request {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}"
                )
                content_type = r.headers.get("content-type").split("/")[-1]
                content_type = content_type or common.get_unknown_content_type(ele)
                if not placeholderObj:
                    placeholderObj = await placeholder.Placeholders(
                        ele, content_type
                    ).init()
                common_logs.path_to_file_logger(placeholderObj, ele)
                if await self._check_forced_skip(ele, total) == 0:
                    if asked and not resume_size:
                        # a whole-file reply to a resume: the part is stale
                        pathlib.Path(tempholderObj.tempfilepath).unlink(missing_ok=True)
                    await self._set_data(ele, data)
                    total = 0
                    return (total, tempholderObj.tempfilepath, placeholderObj)
                elif total != resume_size:
                    self._resume_cleaner(resume_size, total, tempholderObj.tempfilepath)
                    # the part and its saved size and validator are replaced
                    # only once the reply's first bytes arrive (#271)
                    written = await self._download_fileobject_writer(
                        r,
                        ele,
                        tempholderObj,
                        placeholderObj,
                        total,
                        resume_size,
                        partial(self._set_data, ele, data),
                    )
                    if total is None:
                        total = self._size_written(ele, written)
                        # the size is known only now: check the size limits
                        # and skip_download_script on it, as for a reply that
                        # gave its size (#336)
                        if await self._check_forced_skip(ele, total) == 0:
                            pathlib.Path(tempholderObj.tempfilepath).unlink(
                                missing_ok=True
                            )
                            return (0, tempholderObj.tempfilepath, placeholderObj)
                    await self._total_change_helper(total)
            await self._size_checker(tempholderObj.tempfilepath, ele, total)
            return (total, tempholderObj.tempfilepath, placeholderObj)
        except Exception as E:
            await self._total_change_helper(0)
            raise E

    async def _download_fileobject_writer(
        self,
        r,
        ele,
        tempholderObj,
        placeholderObj,
        total,
        resume_size=0,
        on_first_chunk=None,
    ):
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] writing media to disk"
        )
        written = await self._download_fileobject_writer_streamer(
            r, ele, tempholderObj, placeholderObj, total, resume_size, on_first_chunk
        )
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] finished writing media to disk"
        )
        return written

    async def _download_fileobject_writer_streamer(
        self,
        res,
        ele,
        tempholderObj,
        placeholderObj,
        total,
        resume_size=0,
        on_first_chunk=None,
    ):
        """Write the reply to the part and return the bytes written. The part
        is opened on the first chunk: appended to when resuming, else
        replaced from 0. Until then the part on disk is left as it was, so a
        reply with no data doesn't cost it (#271). on_first_chunk runs once
        the first chunk is written."""
        task1 = await self._add_download_job_task(
            ele, total=total, tempholderObj=tempholderObj, placeholderObj=placeholderObj
        )
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
                            tempholderObj.tempfilepath, "ab" if resume_size else "wb"
                        ).__aenter__()
                    await fileobject.write(chunk)
                    written += len(chunk)
                    if first and on_first_chunk:
                        await on_first_chunk()
                    send_chunk_msg(ele, total, tempholderObj)
                except StopAsyncIteration:
                    break

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

    async def _handle_result_main(self, result, ele, username, model_id):
        total, temp, placeholderObj = result
        path_to_file = placeholderObj.trunicated_filepath

        # 1. Check that the file size matches the API reported size
        await self._size_checker(temp, ele, total)

        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} {await ele.final_filename} size match target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}"
        )

        # 2. Video Integrity Check (Optional for Standard Downloads)
        if (
            ele.mediatype.lower() in {"videos", "audios"}
            and settings.get_settings().verify_all_integrity
        ):
            expected_duration = ele.duration
            if not verify_media_integrity(temp, expected_duration):
                common_globals.log.warning(
                    f"Removing corrupted/truncated standard video: {temp}"
                )
                pathlib.Path(temp).unlink(missing_ok=True)
                raise Exception("Standard video failed duration integrity check")

        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} renaming {pathlib.Path(temp).absolute()} -> {path_to_file}"
        )

        # 3. Move the verified file to final path; it can end up under another
        # name if a different file already has this one (#48)
        path_to_file = await asyncio.get_event_loop().run_in_executor(
            common_globals.thread,
            partial(common_paths.moveHelper, temp, path_to_file, ele),
        )

        (common_paths.addGlobalDir(path_to_file.parent))

        # 4. Set File Dates
        if ele.postdate:
            newDate = dates.convert_local_time(ele.postdate)
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread,
                partial(common_paths.set_time, path_to_file, newDate),
            )

        # 5. Mark as Downloaded in Database
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

        # 6. Run Post-Download Scripts
        await self._after_download_script(path_to_file)

        return ele.mediatype, total

    async def _get_data(self, ele):
        data = await asyncio.get_event_loop().run_in_executor(
            common_globals.thread,
            partial(cache.get, f"{ele.id}_{ele.username}_headers"),
        )
        return data

    async def _set_data(self, ele, data):
        data = await asyncio.get_event_loop().run_in_executor(
            common_globals.thread,
            partial(cache.set, f"{ele.id}_{ele.username}_headers", data),
        )
        return data

    async def _fresh_data_handler_main(self, ele, tempholderObj):
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] fresh download for media {ele.url}"
        )
        resume_size = self._get_resume_size(tempholderObj)
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} resume_size: {resume_size}"
        )

    async def _resume_data_handler_main(self, data, ele, tempholderObj):
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] using data for possible download resumption"
        )
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} Data from cache{data}"
        )
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} Total size from cache {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}"
        )

        content_type = data.get("content-type").split("/")[-1]
        total = int(data.get("content-total")) if data.get("content-total") else None
        resume_size = self._get_resume_size(tempholderObj)
        resume_size = self._resume_cleaner(
            resume_size, total, tempholderObj.tempfilepath
        )

        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} resume_size: {resume_size}  and total: {total}"
        )
        placeholderObj = await placeholder.Placeholders(ele, content_type).init()

        check = None
        if await self._check_forced_skip(ele, total) == 0:
            total = 0
            common_logs.path_to_file_logger(placeholderObj, ele, common_globals.log)
            check = True
        elif total == resume_size:
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} total==resume_size skipping download"
            )
            common_logs.path_to_file_logger(placeholderObj, ele, common_globals.log)
            if common_globals.attempt.get() == 0:
                pass
            check = True
        return total, placeholderObj, check
