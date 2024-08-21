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
import re
import traceback
from functools import partial


import aiofiles
import arrow
import psutil
from humanfriendly import format_size

import ofscraper.classes.placeholder as placeholder
import ofscraper.actions.utils.globals as common_globals
import ofscraper.utils.constants as constants
from ofscraper.classes.download_retries import download_retry

from ofscraper.actions.utils.params import get_alt_params
from ofscraper.actions.utils.log import get_medialog
from ofscraper.actions.utils.log import (
    get_url_log,
    path_to_file_logger,
    temp_file_logger,
)
from ofscraper.actions.actions.download.utils.chunk import (
    get_ideal_chunk_size,
)
from ofscraper.actions.utils.retries import get_download_retries
from ofscraper.actions.utils.send.chunk import send_chunk_msg
from ofscraper.classes.sessionmanager.sessionmanager import (
    FORCED_NEW,
    SIGN,
)
import ofscraper.utils.auth.request as auth_requests
from ofscraper.actions.actions.download.managers.downloadmanager import DownloadManager
import ofscraper.actions.utils.paths.paths as common_paths
import ofscraper.actions.utils.log as common_logs
from ofscraper.db.operations_.media import download_media_update
import ofscraper.actions.utils.general as common
import ofscraper.utils.dates as dates
from ofscraper.utils.system.subprocess import run
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
import ofscraper.actions.actions.download.utils.keyhelpers as keyhelpers
import ofscraper.utils.cache as cache
import ofscraper.utils.live.updater as progress_updater
from ofscraper.actions.utils.send.message import send_msg


class AltDownloadManager(DownloadManager):
    def __init__(self, multi=False):
        super().__init__(multi=multi)

    async def alt_download(self, c, ele, username, model_id):
        common_globals.log.debug(
            f"{get_medialog(ele)} Downloading with protected media downloader"
        )
        async for _ in download_retry():
            with _:
                try:
                    sharedPlaceholderObj = await placeholder.Placeholders(
                        ele, "mp4"
                    ).init()
                    common_globals.log.debug(
                        f"{get_medialog(ele)} download url:  {get_url_log(ele)}"
                    )
                except Exception as e:
                    raise e

        audio = await ele.mpd_audio
        video = await ele.mpd_video
        path_to_file_logger(sharedPlaceholderObj, ele)

        audio = await self._alt_download_downloader(audio, c, ele)
        video = await self._alt_download_downloader(video, c, ele)

        post_result = await self._media_item_post_process_alt(
            audio, video, ele, username, model_id
        )
        if post_result:
            return post_result
        await self._media_item_keys_alt(c, audio, video, ele)

        return await self._handle_result_alt(
            sharedPlaceholderObj, ele, audio, video, username, model_id
        )

    async def _alt_download_downloader(self, item, c, ele):
        self._downloadspace(mediatype=ele.mediatype)
        placeholderObj = await placeholder.tempFilePlaceholder(
            ele, f"{item['name']}.part"
        ).init()
        item["path"] = placeholderObj.tempfilepath
        item["total"] = None
        
        async for _ in download_retry():
            with _:
                try:
                    _attempt = self._alt_attempt_get(item)
                    _attempt.set(_attempt.get(0) + 1)
                    if _attempt.get() > 1:
                        pathlib.Path(placeholderObj.tempfilepath).unlink(
                            missing_ok=True
                        )
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
            base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
            url = f"{base_url}{item['origname']}"
            common_globals.log.debug(
                f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}"
            )
            common_globals.log.debug(
                f"{get_medialog(ele)} [attempt {_attempt.get()}/{get_download_retries()}] download temp path {placeholderObj.tempfilepath}"
            )
            return await self._send_req_inner(c, ele, item, placeholderObj)
        except OSError as E:
            raise E
        except Exception as E:
            raise E

    async def _send_req_inner(self, c, ele, item, placeholderObj):
        total = None
        try:

            resume_size = self._get_resume_size(placeholderObj, mediatype=ele.mediatype)
            headers = self._get_resume_header(resume_size, item["total"])
            # reset total
            total = None
            common_globals.log.debug(f"{get_medialog(ele)} resume header {headers}")
            params = get_alt_params(ele)
            base_url = re.sub("[0-9a-z]*\.mpd$", "", ele.mpd, re.IGNORECASE)
            url = f"{base_url}{item['origname']}"
            headers = {"Cookie": f"{ele.hls_header}{auth_requests.get_cookies_str()}"}
            common_globals.log.debug(
                f"{get_medialog(ele)} [attempt {self._alt_attempt_get(item).get()}/{get_download_retries()}] Downloading media with url  {ele.mpd}"
            )
            async with c.requests_async(
                url=url,
                headers=headers,
                params=params,
                # action=[FORCED_NEW,SIGN] if constants.getattr("ALT_FORCE_KEY") else None
            ) as l:
                item["total"] = int(l.headers.get("content-length"))
                total = item["total"]

                data = {
                    "content-total": total,
                    "content-type": l.headers.get("content-type"),
                }

                common_globals.log.debug(
                    f"{get_medialog(ele)} data from request {data}"
                )
                common_globals.log.debug(
                    f"{get_medialog(ele)} total from request {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}"
                )
                await self._total_change_helper(None, total)
                await self._set_data(ele, item, data)

                temp_file_logger(placeholderObj, ele)
                if await self._check_forced_skip(ele, total) == 0:
                    item["total"] = 0
                    total = item["total"]
                    await self._total_change_helper(total, 0)
                    return item
                elif total != resume_size:
                    await self._download_fileobject_writer(
                        total, l, ele, placeholderObj, item
                    )

            await self._size_checker(placeholderObj.tempfilepath, ele, total)
            return item
        except Exception as E:
            await self._total_change_helper(total, 0) if total else None
            raise E

    async def _download_fileobject_writer(self, total, l, ele, placeholderObj, item):
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {self._alt_attempt_get(item).get()}/{get_download_retries()}] writing media to disk"
        )
        await self._download_fileobject_writer_streamer(ele, total, l, placeholderObj)
        # if total > constants.getattr("MAX_READ_SIZE"):
        #     await self._download_fileobject_writer_streamer(ele,total, l, placeholderObj)
        # else:
        #     await self._download_fileobject_writer_reader(ele,total, l, placeholderObj)
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {self._alt_attempt_get(item).get()}/{get_download_retries()}] finished writing media to disk"
        )

    async def _download_fileobject_writer_reader(self, ele, total, res, placeholderObj):

        task1 = await self._add_download_job_task(
            ele, total=total, placeholderObj=placeholderObj
        )
        fileobject = await aiofiles.open(placeholderObj.tempfilepath, "ab").__aenter__()
        try:
            await fileobject.write(await res.read_())
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

    async def _download_fileobject_writer_streamer(
        self, ele, total, res, placeholderObj
    ):

        task1 = await self._add_download_job_task(ele, total, placeholderObj)
        fileobject = await aiofiles.open(placeholderObj.tempfilepath, "ab").__aenter__()
        chunk_size = get_ideal_chunk_size(total, placeholderObj.tempfilepath)
        try:
            async for chunk in res.iter_chunked(chunk_size):
                await fileobject.write(chunk)
                send_chunk_msg(ele, total, placeholderObj)
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

    async def _handle_result_alt(
        self, sharedPlaceholderObj, ele, audio, video, username, model_id
    ):
        tempPlaceholder = await placeholder.tempFilePlaceholder(
            ele, f"temp_{ele.id or await ele.final_filename}.mp4"
        ).init()
        temp_path = tempPlaceholder.tempfilepath
        temp_path.unlink(missing_ok=True)
        t = run(
            [
                settings.get_ffmpeg(),
                "-i",
                str(video["path"]),
                "-i",
                str(audio["path"]),
                "-c",
                "copy",
                "-movflags",
                "use_metadata_tags",
                str(temp_path),
            ],
        )
        if t.stderr.decode().find("Output") == -1:
            common_globals.log.debug(f"{common_logs.get_medialog(ele)} ffmpeg failed")
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} ffmpeg {t.stderr.decode()}"
            )
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} ffmpeg {t.stdout.decode()}"
            )

        video["path"].unlink(missing_ok=True)
        audio["path"].unlink(missing_ok=True)

        common_globals.log.debug(
            f"Moving intermediate path {temp_path} to {sharedPlaceholderObj.trunicated_filepath}"
        )
        common_paths.moveHelper(
            temp_path, sharedPlaceholderObj.trunicated_filepath, ele
        )
        (
            common_paths.addGlobalDir(sharedPlaceholderObj.filedir)
            if system.get_parent_process()
            else common_paths.addLocalDir(sharedPlaceholderObj.filedir)
        )
        if ele.postdate:
            newDate = dates.convert_local_time(ele.postdate)
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}"
            )
            common_paths.set_time(sharedPlaceholderObj.trunicated_filepath, newDate)
            common_globals.log.debug(
                f"{common_logs.get_medialog(ele)} Date set to {arrow.get(sharedPlaceholderObj.trunicated_filepath.stat().st_mtime).format('YYYY-MM-DD HH:mm')}"
            )
        if ele.id:
            await download_media_update(
                ele,
                filepath=sharedPlaceholderObj.trunicated_filepath,
                model_id=model_id,
                username=username,
                downloaded=True,
                hashdata=await common.get_hash(
                    sharedPlaceholderObj, mediatype=ele.mediatype
                ),
                size=sharedPlaceholderObj.size,
            )
        common.add_additional_data(sharedPlaceholderObj, ele)
        return ele.mediatype, video["total"] + audio["total"]

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
        resume_size = self._get_resume_size(placeholderObj, mediatype=ele.mediatype)
        resume_size = self._resume_cleaner(
            resume_size, total, placeholderObj.tempfilepath
        )

        common_globals.log.debug(
            f"{get_medialog(ele)} resume_size: {resume_size}  and total: {total }"
        )

        if await self._check_forced_skip(ele, total) == 0:
            item["total"] = 0
            return item, True
        elif total == resume_size:
            common_globals.log.debug(
                f"{get_medialog(ele)} total==resume_size skipping download"
            )
            temp_file_logger(placeholderObj, ele)
            if self._alt_attempt_get(item).get() == 0:
                pass
            await self._total_change_helper(None, total)
            return item, True
        elif total != resume_size:
            return item, False

    async def _fresh_data_handler_alt(self, item, ele, placeholderObj):
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] fresh download for media"
        )
        resume_size = self._get_resume_size(placeholderObj, mediatype=ele.mediatype)
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
        if (audio["total"] + video["total"]) == 0:
            if ele.mediatype != "forced_skipped":
                await self._force_download(ele, username, model_id)
            return ele.mediatype, 0
        for m in [audio, video]:
            m["total"] = self._get_item_total(m)

        for m in [audio, video]:
            if not isinstance(m, dict):
                return m
            await self._size_checker(m["path"], ele, m["total"])

    async def _media_item_keys_alt(self, c, audio, video, ele):
        for item in [audio, video]:
            item = await keyhelpers.un_encrypt(item, c, ele)

    async def _add_download_job_task(self, ele, total=None, placeholderObj=None):
        pathstr = str(placeholderObj.tempfilepath)
        task1 = None
        if not self._multi:
            task1 = progress_updater.add_download_job_task(
                f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
                total=total,
            )
        else:
            await send_msg(
                partial(
                    progress_updater.add_download_job_multi_task,
                    f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
                    ele.id,
                    total=total,
                    file=placeholderObj.tempfilepath,
                )
            )
        return task1
