r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/

"""

import asyncio
import pathlib
import traceback
from functools import partial


import aiofiles
import arrow
import psutil
from humanfriendly import format_size

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.actions.utils.general as common
import ofscraper.commands.scraper.actions.utils.globals as common_globals
from ofscraper.commands.scraper.actions.download.utils.retries import download_retry
from ofscraper.commands.scraper.actions.utils.general import (
    get_unknown_content_type,
)

from ofscraper.commands.scraper.actions.utils.log import get_medialog
from ofscraper.commands.scraper.actions.utils.log import (
    get_url_log,
    path_to_file_logger,
)
from ofscraper.commands.scraper.actions.download.utils.chunk import get_chunk_size
from ofscraper.commands.scraper.actions.utils.retries import get_download_retries
from ofscraper.commands.scraper.actions.utils.chunk import send_chunk_msg
from ofscraper.commands.scraper.actions.download.managers.downloadmanager import (
    DownloadManager,
)
import ofscraper.commands.scraper.actions.utils.paths as common_paths
import ofscraper.commands.scraper.actions.utils.log as common_logs
from ofscraper.db.operations_.media import download_media_update
import ofscraper.utils.dates as dates
import ofscraper.utils.system.system as system
import ofscraper.utils.cache as cache
from ofscraper.commands.scraper.actions.download.utils.chunk import get_chunk_timeout
from ofscraper.classes.of.media import Media


class MainDownloadManager(DownloadManager):

    async def main_download(self, c, ele: Media, username, model_id):
        ele.mark_download_attempt()
        await common_globals.sem.acquire()
        common_globals.log.debug(
            f"{get_medialog(ele)} Downloading with normal downloader"
        )
        common_globals.log.debug(
            f"{get_medialog(ele)} download url:  {get_url_log(ele)}"
        )
        if common.is_bad_url(ele.url):
            common_globals.log.debug(
                f"{get_medialog(ele)} Forcing download because known bad url"
            )
            await self._force_download(ele, username, model_id)
            return ele.mediatype, 0
        result = await self._main_download_downloader(
            c,
            ele,
        )

        # special case for zero byte files
        if result[0] == 0:
            if ele.mediatype != "forced_skipped":
                await self._force_download(ele, username, model_id)
            return ele.mediatype, 0
        return await self._handle_results_main(result, ele, username, model_id)

    async def _main_download_downloader(self, c, ele):
        self._downloadspace()
        tempholderObj = await placeholder.tempFilePlaceholder(
            ele, f"{ele.filename}_{ele.id}_{ele.postid}.part"
        ).init()
        async for _ in download_retry():
            with _:
                try:
                    common_globals.attempt.set(common_globals.attempt.get(0) + 1)
                    if common_globals.attempt.get() > 1:
                        pathlib.Path(tempholderObj.tempfilepath).unlink(missing_ok=True)
                    data = await self._get_data(ele)
                    total = None
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
                        f"[attempt {common_globals.attempt.get()}/{get_download_retries()}] Number of Open Files -> { len(psutil.Process().open_files())}"
                    )
                    common_globals.log.debug(
                        f"[attempt {common_globals.attempt.get()}/{get_download_retries()}] Open Files  -> {list(map(lambda x:(x.path,x.fd),psutil.Process().open_files()))}"
                    )
                    raise E
                except Exception as E:
                    common_globals.log.traceback_(
                        f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] {traceback.format_exc()}"
                    )
                    common_globals.log.traceback_(
                        f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] {E}"
                    )
                    raise E

    async def _main_download_sendreq(
        self, c, ele, tempholderObj, placeholderObj=None, total=None
    ):
        try:
            common_globals.log.debug(
                f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] download temp path {tempholderObj.tempfilepath}"
            )
            return await self._send_req_inner(
                c, ele, tempholderObj, placeholderObj=placeholderObj, total=total
            )
        except OSError as E:
            raise E
        except Exception as E:
            raise E

    async def _send_req_inner(
        self, c, ele, tempholderObj, placeholderObj=None, total=None
    ):
        try:
            resume_size = self._get_resume_size(tempholderObj)
            headers = self._get_resume_header(resume_size, total)
            # reset total
            total = None
            common_globals.log.debug(
                f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] Downloading media with url {ele.url}"
            )
            async with c.requests_async(
                url=ele.url,
                stream=True,
                headers=headers,
            ) as r:
                total = int(r.headers["content-length"])
                data = {
                    "content-total": total,
                    "content-type": r.headers.get("content-type"),
                }

                common_globals.log.debug(
                    f"{get_medialog(ele)} data from request {data}"
                )
                common_globals.log.debug(
                    f"{get_medialog(ele)} total from request {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}"
                )
                await self._set_data(ele, data)
                content_type = r.headers.get("content-type").split("/")[-1]
                content_type = content_type or get_unknown_content_type(ele)
                if not placeholderObj:
                    placeholderObj = await placeholder.Placeholders(
                        ele, content_type
                    ).init()
                path_to_file_logger(placeholderObj, ele)
                if await self._check_forced_skip(ele, total) == 0:
                    total = 0
                    return (total, tempholderObj.tempfilepath, placeholderObj)
                elif total != resume_size:
                    self._resume_cleaner(resume_size, total, tempholderObj.tempfilepath)
                    await self._download_fileobject_writer(
                        r, ele, tempholderObj, placeholderObj, total
                    )
                    await self._total_change_helper(total)
            await self._size_checker(tempholderObj.tempfilepath, ele, total)
            return (total, tempholderObj.tempfilepath, placeholderObj)
        except Exception as E:
            await self._total_change_helper(0)
            raise E
        finally:
            common_globals.sem.release()

    async def _download_fileobject_writer(
        self, r, ele, tempholderObj, placeholderObj, total
    ):
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] writing media to disk"
        )
        await self._download_fileobject_writer_streamer(
            r, ele, tempholderObj, placeholderObj, total
        )
        # if total > env.getattr("MAX_READ_SIZE"):

        # else:
        #     await self._download_fileobject_writer_reader(
        #         r, ele, tempholderObj, placeholderObj, total
        #     )
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] finished writing media to disk"
        )

    async def _download_fileobject_writer_reader(
        self, r, ele, tempholderObj, placeholderObj, total
    ):
        task1 = await self._add_download_job_task(
            ele, total=total, tempholderObj=tempholderObj, placeholderObj=placeholderObj
        )

        fileobject = await aiofiles.open(tempholderObj.tempfilepath, "ab").__aenter__()
        try:
            await fileobject.write(await r.read_())
        except Exception as E:
            raise E
        finally:
            # Close file if needed
            try:
                await fileobject.close()
            except Exception as E:
                raise E
            try:
                await self._remove_download_job_task(task1, ele)
            except Exception as E:
                raise E

    async def _download_fileobject_writer_streamer(  # Renamed function as per user's prompt
        self, res, ele, tempholderObj, placeholderObj, total
    ):
        task1 = await self._add_download_job_task(
            ele, total=total, tempholderObj=tempholderObj, placeholderObj=placeholderObj
        )
        fileobject = None  # Initialize to None for finally block
        try:
            # Use asyncio.timeout as a context manager for the entire download process
            async with asyncio.timeout(None):
                fileobject = await aiofiles.open(
                    tempholderObj.tempfilepath, "ab"
                ).__aenter__()
                chunk_iter = res.iter_chunked(get_chunk_size())
                while True:
                    try:
                        chunk = await chunk_iter.__anext__()
                        await fileobject.write(chunk)
                        send_chunk_msg(ele, total, tempholderObj)
                    except StopAsyncIteration:
                        break  # Exit loop when no more chunks
        except asyncio.TimeoutError:
            # This catches the timeout for the entire async with block
            common_globals.log.warning(
                f"{common_logs.get_medialog(ele)}⚠️ No chunk received in {(get_chunk_timeout())} seconds or download timed out!"
            )
            return  # Exit the function on timeout
        except Exception as E:
            # Catch other potential exceptions during file operations or chunk iteration
            common_globals.log.error(
                f"An error occurred during download for {ele}: {E}"
            )
            raise E  # Re-raise the exception after logging
        finally:
            # Close file if needed
            if fileobject:  # Ensure fileobject was successfully opened
                try:
                    await fileobject.close()
                except Exception as E:
                    common_globals.log.error(f"Error closing file for {ele}: {E}")
                    raise E  # Re-raise if closing fails
            try:
                await self._remove_download_job_task(task1, ele)
            except Exception as E:
                common_globals.log.error(
                    f"Error removing download job task for {ele}: {E}"
                )
                raise E  # Re-raise if task removal fails

    async def _handle_results_main(self, result, ele, username, model_id):
        total, temp, placeholderObj = result
        path_to_file = placeholderObj.trunicated_filepath
        await self._size_checker(temp, ele, total)
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} {await ele.final_filename} size match target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}"
        )
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} renaming {pathlib.Path(temp).absolute()} -> {path_to_file}"
        )
        common_paths.moveHelper(temp, path_to_file, ele)
        (
            common_paths.addGlobalDir(placeholderObj.filedir)
            if system.get_parent_process()
            else common_paths.addLocalDir(placeholderObj.filedir)
        )
        if ele.postdate:
            newDate = dates.convert_local_time(ele.postdate)
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}"
            )
            common_paths.set_time(path_to_file, newDate)
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}"
            )

        if ele.id:
            await download_media_update(
                ele,
                filepath=path_to_file,
                model_id=model_id,
                username=username,
                downloaded=True,
                hashdata=await common.get_hash(path_to_file),
                size=placeholderObj.size,
            )
        await common.set_profile_cache_helper(ele)
        ele.add_filepath(placeholderObj.trunicated_filepath)
        self._after_download_script(path_to_file)

        return ele.mediatype, total

    async def _get_data(self, ele):
        data = await asyncio.get_event_loop().run_in_executor(
            common_globals.thread,
            partial(cache.get, f"{ele.id}_{ele.username}_headers"),
        )
        # data=cache.get(f"{ele.id}_{ele.username}_headers")
        return data

    async def _set_data(self, ele, data):
        data = await asyncio.get_event_loop().run_in_executor(
            common_globals.thread,
            partial(cache.set, f"{ele.id}_{ele.username}_headers", data),
        )
        return data

    async def _fresh_data_handler_main(self, ele, tempholderObj):
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] fresh download for media {ele.url}"
        )
        resume_size = self._get_resume_size(tempholderObj)
        common_globals.log.debug(f"{get_medialog(ele)} resume_size: {resume_size}")

    async def _resume_data_handler_main(self, data, ele, tempholderObj):
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] using data for possible download resumption"
        )
        common_globals.log.debug(f"{get_medialog(ele)} Data from cache{data}")
        common_globals.log.debug(
            f"{get_medialog(ele)} Total size from cache {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}"
        )

        content_type = data.get("content-type").split("/")[-1]
        total = int(data.get("content-total")) if data.get("content-total") else None
        resume_size = self._get_resume_size(tempholderObj)
        resume_size = self._resume_cleaner(
            resume_size, total, tempholderObj.tempfilepath
        )

        common_globals.log.debug(
            f"{get_medialog(ele)} resume_size: {resume_size}  and total: {total}"
        )
        placeholderObj = await placeholder.Placeholders(ele, content_type).init()

        # other
        check = None
        if await self._check_forced_skip(ele, total) == 0:
            total = 0
            path_to_file_logger(placeholderObj, ele, common_globals.log)
            check = True
        elif total == resume_size:
            common_globals.log.debug(
                f"{get_medialog(ele)} total==resume_size skipping download"
            )
            path_to_file_logger(placeholderObj, ele, common_globals.log)
            if common_globals.attempt.get() == 0:
                pass
            check = True
        return total, placeholderObj, check
