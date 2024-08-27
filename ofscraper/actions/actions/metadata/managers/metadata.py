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

import traceback

import ofscraper.actions.utils.globals as common_globals
from ofscraper.actions.utils.log import get_medialog
from ofscraper.actions.utils.log import (
    set_media_log,
)
import asyncio
import pathlib
from functools import partial

import ofscraper.classes.placeholder as placeholder
import ofscraper.actions.utils.general as common
import ofscraper.actions.utils.paths.media as media
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.hash as hash
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.media import (
    download_media_update,
    prev_download_media_data,
)
from ofscraper.actions.utils.retries import get_download_retries
from ofscraper.actions.utils.params import get_alt_params
from ofscraper.classes.sessionmanager.sessionmanager import FORCED_NEW, SIGN
import ofscraper.utils.constants as constants


class MetaDataManager:
    def __init__(self, multi=False):
        self._multi = multi

    async def metadata(self, c, ele, model_id, username):
        try:
            self._prepare(ele)
            return await self._change_metadata(c, ele, username, model_id)
        except Exception as E:
            common_globals.log.debug(f"{get_medialog(ele)} exception {E}")
            common_globals.log.debug(
                f"{get_medialog(ele)} exception {traceback.format_exc()}"
            )
            common_globals.log.traceback_(f"{get_medialog(ele)} Metadata Failed\n")
            return "skipped"

    def _prepare(self, ele):
        if self._multi:
            set_media_log(common_globals.log, ele)
            common_globals.attempt.set(0)

    async def _change_metadata(self, c, ele, username, model_id, placeholderObj=None):
        common_globals.log.info(
            f"{get_medialog(ele)} skipping adding download to disk because metadata is on"
        )
        placeholderObj = placeholderObj or await self._placeholderObjHelper(c, ele)
        await placeholderObj.init(create=False)
        common.add_additional_data(placeholderObj, ele)
        effected = None
        if ele.id:
            prevData = (
                await prev_download_media_data(
                    ele, model_id=model_id, username=username
                )
                or {}
            )
            await download_media_update(
                ele,
                filename=self._metadata_file_helper(placeholderObj, prevData),
                directory=self._metadata_dir_helper(placeholderObj, prevData),
                model_id=model_id,
                username=username,
                downloaded=self._metadata_downloaded_helper(placeholderObj, prevData),
                hashdata=self._metadata_hash_helper(placeholderObj, prevData, ele),
                size=self._metadata_size_helper(placeholderObj, prevData),
            )
            effected = prevData != await prev_download_media_data(
                ele, model_id=model_id, username=username
            )
        return ele.mediatype if effected else "forced_skipped"

    def _metadata_downloaded_helper(self, placeholderObj, prevData):
        if read_args.retriveArgs().metadata == "check":
            return prevData["downloaded"] if prevData else None
        elif read_args.retriveArgs().metadata == "complete":
            return 1
        # for update
        elif pathlib.Path(placeholderObj.trunicated_filepath).exists():
            return 1
        elif pathlib.Path(prevData.get("filename") or "").is_file():
            return 1
        elif pathlib.Path(
            prevData.get("directory") or "", prevData.get("filename") or ""
        ).is_file():
            return 1
        return 0

    def _metadata_file_helper(self, placeholderObj, prevData):
        if read_args.retriveArgs().metadata != "update":
            return str(placeholderObj.trunicated_filename)
        # for update
        elif pathlib.Path(placeholderObj.trunicated_filepath).exists():
            return str(placeholderObj.trunicated_filename)
        elif pathlib.Path(prevData.get("filename") or "").is_file():
            return prevData.get("filename")
        elif pathlib.Path(
            prevData.get("directory") or "", prevData.get("filename") or ""
        ).is_file():
            return pathlib.Path(
                prevData.get("directory") or "", prevData.get("filename") or ""
            )
        return str(placeholderObj.trunicated_filename)

    def _metadata_dir_helper(self, placeholderObj, prevData):
        if read_args.retriveArgs().metadata != "update":
            return str(placeholderObj.trunicated_filedir)
        # for update
        elif pathlib.Path(placeholderObj.trunicated_filedir).exists():
            return str(placeholderObj.trunicated_filedir)
        elif pathlib.Path(prevData.get("directory") or "").is_dir():
            return prevData.get("directory")
        elif pathlib.Path(
            prevData.get("directory") or "", prevData.get("filename") or ""
        ).is_file():
            return pathlib.Path(
                prevData.get("directory") or "", prevData.get("filename") or ""
            ).parent
        return str(placeholderObj.trunicated_filedir)

    def _metadata_hash_helper(self, placeholderObj, prevData, ele):
        if not settings.get_hash(mediatype=ele.mediatype):
            return prevData.get("hash")
        elif pathlib.Path(placeholderObj.trunicated_filepath).is_file():
            return hash.get_hash(
                pathlib.Path(placeholderObj.trunicated_filepath),
                mediatype=ele.mediatype,
            )
        elif pathlib.Path(
            prevData.get("directory") or "", prevData.get("filename") or ""
        ).is_file():
            return hash.get_hash(
                pathlib.Path(
                    prevData.get("directory") or "", prevData.get("filename") or ""
                )
            )

    def _metadata_size_helper(self, placeholderObj, prevData):
        if placeholderObj.size:
            return placeholderObj.size
        elif pathlib.Path(
            prevData.get("directory") or "", prevData.get("filename") or ""
        ).is_file():
            return (
                pathlib.Path(
                    prevData.get("directory") or "", prevData.get("filename") or ""
                )
                .stat()
                .st_size
            )
        else:
            return prevData.get("size")

    async def _metadata_helper(self, c, ele):
        placeholderObj = None
        if not ele.url and not ele.mpd:
            placeholderObj = placeholder.Placeholders(
                ele, ext=media.content_type_missing(ele)
            )
            return placeholderObj
        else:
            url = ele.url or ele.mpd
            params = get_alt_params(ele) if ele.mpd else None
            actions = (
                [FORCED_NEW, SIGN]
                if ele.mpd and constants.getattr("ALT_FORCE_KEY")
                else []
            )
            common_globals.attempt.set(common_globals.attempt.get() + 1)
            common_globals.log.debug(
                f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}]  Getting data for metadata insert"
            )
            async with c.requests_async(
                url=url, headers=None, params=params, actions=actions
            ) as r:
                headers = r.headers
                content_type = headers.get("content-type").split("/")[
                    -1
                ] or media.content_type_missing(ele)
                # request fail if not read
                async for _ in r.iter_chunked(1024*1024*30):
                    pass
                placeholderObj = placeholder.Placeholders(ele, ext=content_type)
                return placeholderObj

    async def _placeholderObjHelper(self, c, ele):
        download_data = await asyncio.get_event_loop().run_in_executor(
            common_globals.thread, partial(cache.get, f"{ele.id}_headers")
        )
        if download_data:
            content_type = download_data.get("content-type").split("/")[
                -1
            ] or media.content_type_missing(ele)
            return placeholder.Placeholders(ele, content_type)
        # final fallback
        return await self._metadata_helper(c, ele)
