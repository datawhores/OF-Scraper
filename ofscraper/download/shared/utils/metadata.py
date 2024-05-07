import asyncio
import pathlib
from functools import partial

import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.download.shared.common.general as common
import ofscraper.download.shared.globals as common_globals
import ofscraper.download.shared.utils.media as media
import ofscraper.utils.args.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.constants as constants
from ofscraper.db.operations_.media import download_media_update
from ofscraper.download.shared.utils.log import get_medialog


async def force_download(ele, username, model_id):
    await download_media_update(
        ele,
        filename=None,
        model_id=model_id,
        username=username,
        downloaded=True,
    )


async def metadata(c, ele, username, model_id, placeholderObj=None):
    common_globals.log.info(
        f"{get_medialog(ele)} skipping adding download to disk because metadata is on"
    )
    placeholderObj = placeholderObj or await placeholderObjHelper(c, ele)
    await placeholderObj.init()
    common.add_additional_data(placeholderObj, ele)
    effected = None
    if ele.id:
        effected = await download_media_update(
            ele,
            filename=placeholderObj.trunicated_filepath,
            model_id=model_id,
            username=username,
            downloaded=await metadata_downloaded_helper(placeholderObj),
            changed=True,
        )

    return (
        (ele.mediatype if effected else "forced_skipped"),
        0,
    )


async def metadata_downloaded_helper(placeholderObj):
    if read_args.retriveArgs().metadata == "none":
        return None

    elif read_args.retriveArgs().metadata == "complete":
        return 1
    elif pathlib.Path(placeholderObj.trunicated_filepath).exists():
        return 1
    return 0


async def metadata_helper(c, ele):
    if not ele.url and not ele.mpd:
        placeholderObj = placeholder.Placeholders(
            ele, ext=media.content_type_missing(ele)
        )
        return placeholderObj
    else:
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
        common_globals.attempt.set(common_globals.attempt.get() + 1)
        common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('DOWNLOAD_FILE_NUM_TRIES')}]  Getting data for metadata insert"
        )
        async with c.requests_async(url=url, headers=None, params=params) as r:
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
            content_type = headers.get("content-type").split("/")[
                -1
            ] or media.content_type_missing(ele)
            placeholderObj = await (
                placeholderObj or placeholder.Placeholders(ele, ext=content_type)
            ).init()
            return placeholderObj


async def placeholderObjHelper(c, ele):
    download_data = await asyncio.get_event_loop().run_in_executor(
        common_globals.cache_thread, partial(cache.get, f"{ele.id}_headers")
    )
    if download_data:
        content_type = download_data.get("content-type").split("/")[
            -1
        ] or media.content_type_missing(ele)
        return placeholder.Placeholders(ele, content_type)
    # final fallback
    return await metadata_helper(c, ele)
