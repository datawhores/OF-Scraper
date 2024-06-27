from humanfriendly import format_size
import ofscraper.download.shared.general as common
import ofscraper.download.shared.globals as common_globals
from ofscraper.download.shared.retries import get_download_retries
from ofscraper.download.shared.general import (
    check_forced_skip,
    get_medialog,
)
from ofscraper.download.shared.log import (
    temp_file_logger,
)
from ofscraper.download.shared.resume import get_resume_size
from ofscraper.download.shared.alt.attempt import alt_attempt_get
from ofscraper.download.shared.total import total_change_helper,batch_total_change_helper



async def resume_data_handler_alt(data, item,ele, placeholderObj,batch=False):
    common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] using data for possible download resumption"
    )
    common_globals.log.debug(f"{get_medialog(ele)} Data from cache{data}")
    common_globals.log.debug(f"{get_medialog(ele)} Total size from cache {format_size(data.get('content-total')) if data.get('content-total') else 'unknown'}")
    total=(
        int(data.get("content-total")) if data.get("content-total") else None
    )
    item["total"]=total

    resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
    common_globals.log.debug(f"{get_medialog(ele)} resume_size: {resume_size}  and total: {total }")

    if await check_forced_skip(ele, total) == 0:
        item["total"] = 0
        return item,True
    elif total == resume_size:
        common_globals.log.debug(f"{get_medialog(ele)} total==resume_size skipping download")
        temp_file_logger(placeholderObj, ele)
        if alt_attempt_get(item).get() ==0:
            pass
        elif not batch:
            total_change_helper(None, total)
        elif batch:
            batch_total_change_helper(None,total)
        return item,True
    elif total!= resume_size:
        return item,False
        


async def fresh_data_handler_alt(item, ele, placeholderObj):
    common_globals.log.debug(
            f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{get_download_retries()}] fresh download for media"
    )
    resume_size = get_resume_size(placeholderObj, mediatype=ele.mediatype)
    common_globals.log.debug(f"{get_medialog(ele)} resume_size: {resume_size}")
    return item,False
