import asyncio
import pathlib
import traceback
from functools import partial

from tenacity import AsyncRetrying, retry, stop_after_attempt, wait_random

import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.download.common.globals as common_globals
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
from ofscraper.download.common.log import get_medialog
from ofscraper.download.common.sem import sem_wrapper


async def metadata(c, ele, username, model_id, placeholderObj=None):
    common_globals.log.info(
        f"{get_medialog(ele)} skipping adding download to disk because metadata is on"
    )
    download_data = await asyncio.get_event_loop().run_in_executor(
        common_globals.cache_thread, partial(cache.get, f"{ele.id}_headers")
    )
    for _ in range(2):
        if placeholderObj:
            if ele.id:
                await operations.update_media_table(
                    ele,
                    filename=placeholderObj.trunicated_filepath,
                    model_id=model_id,
                    username=username,
                    downloaded=metadata_downloaded_helper(placeholderObj),
                )
            return (
                ele.mediatype
                if metadata_downloaded_helper(placeholderObj)
                else "forced_skipped",
                0,
            )
        elif download_data and download_data.get("content-type"):
            content_type = download_data.get("content-type").split("/")[-1]
            placeholderObj = placeholder.Placeholders(ele)
            await placeholderObj.set_trunicated_filepath(ele, content_type)
            if ele.id:
                await operations.update_media_table(
                    ele,
                    filename=placeholderObj.trunicated_filepath,
                    model_id=model_id,
                    username=username,
                    downloaded=metadata_downloaded_helper(placeholderObj),
                )
            return (
                ele.mediatype
                if metadata_downloaded_helper(placeholderObj)
                else "forced_skipped",
                0,
            )
        elif _ == 1:
            break
        else:
            try:
                async for _ in AsyncRetrying(
                    stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
                    wait=wait_random(
                        min=constants.getattr("OF_MIN"), max=constants.getattr("OF_MAX")
                    ),
                    reraise=True,
                ):
                    with _:
                        try:
                            placeholderObj = await metadata_helper(
                                c, ele, placeholderObj
                            )
                        except Exception as E:
                            raise E
            except Exception as E:
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} Could not get placeholderObj {E}"
                )
                common_globals.log.traceback_(
                    f"{get_medialog(ele)} Could not get placeholderObj {traceback.format_exc()}"
                )
                common_globals.log.debug(
                    f"{get_medialog(ele)} using a generic placeholderObj"
                )
                placeholderObj = await meta_data_placeholder(ele, username, model_id)


def metadata_downloaded_helper(placeholderObj):
    if read_args.retriveArgs().metadata == "none":
        return None

    elif read_args.retriveArgs().metadata == "complete":
        return 1
    elif pathlib.Path(placeholderObj.trunicated_filepath).exists():
        return 1
    return 0


@sem_wrapper
async def metadata_helper(c, ele, placeholderObj=None):
    url = ele.url or ele.mpd

    params = (
        {
            "Policy": ele.policy,
            "Key-Pair-Id": ele.keypair,
            "Signature": ele.signature,
        }
        if ele.mpd
        else None
    )
    common_globals.attempt.set(attempt.get(0) + 1)
    common_globals.log.debug(
        f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_RETRIES')}]  Getting data for metadata insert"
    )
    async with c.requests(url=url, headers=None, params=params)() as r:
        if r.ok:
            headers = r.headers
            await asyncio.get_event_loop().run_in_executor(
                common_globals.cache_thread,
                partial(
                    cache.set,
                    f"{ele.id}_headers",
                    {
                        "content-length": headers.get("content-length"),
                        "content-type": headers.get("content-type"),
                    },
                ),
            )
            content_type = headers.get("content-type").split("/")[-1]
            if not content_type and ele.mediatype.lower() == "videos":
                content_type = "mp4"
            elif not content_type and ele.mediatype.lower() == "images":
                content_type = "jpg"
            placeholderObj = placeholderObj or placeholder.Placeholders(ele)
            return placeholderObj

        else:
            r.raise_for_status()


async def meta_data_placeholder(ele, username, model_id):
    if ele.mediatype.lower() == "videos":
        content_type = "mp4"
    elif ele.mediatype.lower() == "images":
        content_type = "jpg"
    elif ele.mediatype.lower() == "audios":
        content_type = "mp3"
    placeholderObj = placeholder.Placeholders()
    return placeholderObj
