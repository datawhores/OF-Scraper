import ofscraper.download.utils.keyhelpers as keyhelpers
from ofscraper.download.utils.metadata import force_download
from ofscraper.download.utils.check.size import (
    size_checker

)



def get_item_total(item):
    return item["path"].absolute().stat().st_size

async def media_item_post_process_alt(audio, video, ele, username, model_id):
    if (audio["total"] + video["total"]) == 0:
        if ele.mediatype != "forced_skipped":
            await force_download(ele, username, model_id)
        return ele.mediatype, 0
    for m in [audio, video]:
        m["total"] = get_item_total(m)

    for m in [audio, video]:
        if not isinstance(m, dict):
            return m
        await size_checker(m["path"], ele, m["total"])


async def media_item_keys_alt(c, audio, video, ele):
    for item in [audio, video]:
        item = await keyhelpers.un_encrypt(item, c, ele)
