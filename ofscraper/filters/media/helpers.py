import logging
import re

import arrow

import ofscraper.utils.args as args_
import ofscraper.utils.config as config

log = logging.getLogger("shared")


def sort_media(media):
    return sorted(media, key=lambda x: x.date)


def dupefilter(media):
    output = []
    ids = set()
    log.info("Removing duplicate media")
    for item in media:
        if not item.id or item.id not in ids:
            output.append(item)
            ids.add(item.id)
    return output


def post_datesorter(output):
    return list(sorted(output, key=lambda x: x.date, reverse=True))


def timeline_array_filter(posts):
    out = []
    undated = list(filter(lambda x: x.get("postedAt") is None, posts))
    dated = list(filter(lambda x: x.get("postedAt") is not None, posts))
    dated = sorted(dated, key=lambda x: arrow.get(x.get("postedAt")))
    if args_.getargs().before:
        dated = list(
            filter(
                lambda x: arrow.get(x.get("postedAt")) <= args_.getargs().before, dated
            )
        )
    if args_.getargs().after:
        dated = list(
            filter(
                lambda x: arrow.get(x.get("postedAt")) >= args_.getargs().after, dated
            )
        )
    out.extend(undated)
    out.extend(dated)
    return out


def posts_type_filter(media):
    filtersettings = args_.getargs().mediatype or config.get_filter(
        config.read_config()
    )
    if isinstance(filtersettings, str):
        filtersettings = filtersettings.split(",")
    if isinstance(filtersettings, list):
        filtersettings = list(map(lambda x: x.lower().replace(" ", ""), filtersettings))
        filtersettings = list(filter(lambda x: x != "", filtersettings))
        if len(filtersettings) == 0:
            return media
        log.info(f"filtering Media to {','.join(filtersettings)}")
        media = list(filter(lambda x: x.mediatype.lower() in filtersettings, media))
    else:
        log.info("The settings you picked for the filter are not valid\nNot Filtering")
        log.debug(f"[bold]Combined Media Count Filtered:[/bold] {len(media)}")
    return media


def posts_date_filter(media):
    if args_.getargs().before:
        media = list(
            filter(
                lambda x: x.postdate is None
                or arrow.get(x.postdate) <= args_.getargs().before,
                media,
            )
        )
    if args_.getargs().after:
        media = list(
            filter(
                lambda x: x.postdate is None
                or arrow.get(x.postdate) >= args_.getargs().after,
                media,
            )
        )
    return media


def post_timed_filter(media):
    if args_.getargs().timed_only is False:
        return list(filter(lambda x: not x.expires, media))
    elif args_.getargs().timed_only is True:
        return list(filter(lambda x: x.expires, media))
    return media


def post_user_filter(media):
    userfilter = args_.getargs().filter
    if not userfilter:
        return media
    elif not userfilter.islower():
        return list(
            filter(lambda x: re.search(userfilter, x.text or "") is not None, media)
        )
    else:
        return list(
            filter(
                lambda x: re.search(userfilter, x.text or "", re.IGNORECASE)
                is not None,
                media,
            )
        )


def anti_post_user_filter(media):
    userfilter = args_.getargs().neg_filter
    if not userfilter:
        return media
    elif not userfilter.islower():
        return list(
            filter(lambda x: re.search(userfilter, x.text or "") is None, media)
        )
    else:
        return list(
            filter(
                lambda x: re.search(userfilter, x.text or "", re.IGNORECASE) is None,
                media,
            )
        )


def download_type_filter(media):
    if args_.getargs().protected_only:
        return list(filter(lambda x: x.mpd is not None, media))
    elif args_.getargs().normal_only:
        return list(filter(lambda x: x.url is not None, media))
    else:
        return media


def mass_msg_filter(media):
    if args_.getargs().mass_msg is None:
        return media
    elif args_.getargs().mass_msg is True:
        return list((filter(lambda x: x.mass is True, media)))
    elif args_.getargs().mass_msg is False:
        return list((filter(lambda x: x.mass is False, media)))
