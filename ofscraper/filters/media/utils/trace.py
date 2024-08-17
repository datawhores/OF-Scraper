import logging
from ofscraper.utils.logs.utils.trace import is_trace

log = logging.getLogger("shared")


def trace_log_media(count, media, filter_str):
    if not is_trace():
        return
    log.trace(f"filter {filter_str} ->  total item count:{count}->")
    for count, ele in enumerate(media):
        log.trace(
            "{} current item count: {} mediaid: {} postid: {} data: {} \n\n".format(
                filter_str, count, ele.id, ele.postid, ele.media, ele.media
            )
        )


def trace_log_post(count, media, filter_str):
    if not is_trace():
        return

    log.trace(f"filter {count}-> {filter_str}")
    for count, ele in enumerate(media):
        log.trace(
            "{} current item  count: {} postid: {} data: {} \n\n".format(
                filter_str, count, ele.id, ele.post
            )
        )
