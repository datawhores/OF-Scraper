import logging
import random
import re

import arrow

import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.data as config_data

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
    if read_args.retriveArgs().before:
        dated = list(
            filter(
                lambda x: arrow.get(x.get("postedAt"))
                <= read_args.retriveArgs().before,
                dated,
            )
        )
    if read_args.retriveArgs().after:
        dated = list(
            filter(
                lambda x: arrow.get(x.get("postedAt")) >= read_args.retriveArgs().after,
                dated,
            )
        )
    out.extend(undated)
    out.extend(dated)
    return out


def post_count_filter(media):
    count = (
        read_args.retriveArgs().max_count or config_data.get_max_post_count() or None
    )
    return media[:count]


def posts_type_filter(media):
    filtersettings = read_args.retriveArgs().mediatype or config_data.get_filter()
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
    if read_args.retriveArgs().before:
        media = list(
            filter(
                lambda x: x.postdate is None
                or arrow.get(x.postdate) <= read_args.retriveArgs().before,
                media,
            )
        )
    if read_args.retriveArgs().after:
        media = list(
            filter(
                lambda x: x.postdate is None
                or arrow.get(x.postdate) >= read_args.retriveArgs().after,
                media,
            )
        )
    return media


def post_timed_filter(media):
    if read_args.retriveArgs().timed_only is False:
        return list(filter(lambda x: not x.expires, media))
    elif read_args.retriveArgs().timed_only is True:
        return list(filter(lambda x: x.expires, media))
    return media


def post_user_filter(media):
    userfilter = read_args.retriveArgs().filter
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
    userfilter = read_args.retriveArgs().neg_filter
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
    if read_args.retriveArgs().protected_only:
        return list(filter(lambda x: x.mpd is not None, media))
    elif read_args.retriveArgs().normal_only:
        return list(filter(lambda x: x.url is not None, media))
    else:
        return media


def mass_msg_filter(media):
    if read_args.retriveArgs().mass_msg is None:
        return media
    elif read_args.retriveArgs().mass_msg is True:
        return list((filter(lambda x: x.mass is True, media)))
    elif read_args.retriveArgs().mass_msg is False:
        return list((filter(lambda x: x.mass is False, media)))


def url_filter(media):
    return list((filter(lambda x: x.url or x.mpd, media)))


def final_post_sort(media):
    item_sort = read_args.retriveArgs().item_sort
    log.debug(f"Using download sort {item_sort}")
    if not item_sort:
        return media
    elif item_sort == "date-asc":
        return media
    elif item_sort == "date-desc":
        return list(reversed(media))
    elif item_sort == "random":
        random.shuffle(media)
        return media
    elif item_sort == "text-asc":
        return sorted(media, key=lambda x: x.text)
    elif item_sort == "text-desc":
        return sorted(media, key=lambda x: x.text, reverse=True)
    elif item_sort == "filename-asc":
        return sorted(media, key=lambda x: x.filename)
    elif item_sort == "filename-desc":
        return sorted(media, key=lambda x: x.filename, reverse=True)
