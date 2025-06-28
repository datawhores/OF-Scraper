import logging

import ofscraper.filters.media.filters as helpers
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.utils.logs.utils.trace import is_trace


log = logging.getLogger("shared")


def filterMediaFinalMetadata(media, username, model_id):
    log.info(
        f"finalizing media filtering username:{username} model_id:{model_id} for metadata"
    )
    count = 1
    trace_log_media(count, media, "initial media no filter:")
    log.debug(f"filter {count}-> initial media no filter count: {len(media)}")
    media = helpers.sort_by_date(media)
    count += 1
    trace_log_media(count, media, "sorted by date initial")
    log.debug(f"filter {count}-> sorted media count: {len(media)}")

    if of_env.getattr("REMOVE_UNVIEWABLE_METADATA"):
        media = helpers.unviewable_media_filter(media)
        count += 1
        trace_log_media(count, media, "filtered viewable media")
        log.debug(f"filter {count}-> viewable media filter count: {len(media)}")
    media = helpers.previous_download_filter(
        media, username=username, model_id=model_id
    )
    media = helpers.ele_count_filter(media)
    count += 1
    trace_log_media(count, media, "media max post count filter:")
    log.debug(f"filter {count}->  media max post count filter count: {len(media)}")
    return media
