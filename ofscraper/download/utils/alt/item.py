import ofscraper.download.shared.general as common
import ofscraper.download.shared.keyhelpers as keyhelpers
from ofscraper.download.shared.metadata import force_download



async def media_item_post_process_alt(audio, video, ele, username, model_id):
    if (audio["total"] + video["total"]) == 0:
        if ele.mediatype != "forced_skipped":
            await force_download(ele, username, model_id)
        return ele.mediatype, 0
    for m in [audio, video]:
        m["total"] = common.get_item_total(m)

    for m in [audio, video]:
        if not isinstance(m, dict):
            return m
        await common.size_checker(m["path"], ele, m["total"])


async def media_item_keys_alt(c, audio, video, ele):
    for item in [audio, video]:
        item = await keyhelpers.un_encrypt(item, c, ele)
