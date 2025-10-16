import logging
import random
import re
from collections import defaultdict

import arrow

import ofscraper.utils.separate as seperate
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded,
    get_media_ids_downloaded_model,
)
import ofscraper.utils.of_env.of_env as of_env


log = logging.getLogger("shared")


def sort_by_date(media):
    return sorted(media, key=lambda x: x.date)


# dupe filters that prioritize viewable
def dupefiltermedia(media):
    output = defaultdict(lambda: None)
    media = sorted(media, key=lambda item: (item.post.date, item.id, item.count))
    if of_env.getattr("ALLOW_DUPE_MEDIA"):
        for item in media:
            if not output[(item.id, item.post_id)]:
                output[(item.id, item.post_id)] = item
    else:
        for item in media:
            if not output[item.id]:
                output[item.id] = item
            elif item.canview and not output[item.id].canview:
                output[item.id] = item
    return list(output.values())


def dupefilterPost(post):
    output = defaultdict(lambda: None)
    for item in post:
        if not output[item.id]:
            output[item.id] = item
        elif item.opened and not output[item.id].opened:
            output[item.id] = item
    return list(output.values())


# media filters
def ele_count_filter(media):
    count = settings.get_settings().max_post_count or None
    if count:
        return media[:count]
    return media


def mediatype_type_filter(media):
    filtersettings = settings.get_settings().mediatype
    if isinstance(filtersettings, str):
        filtersettings = filtersettings.split(",")
    if isinstance(filtersettings, list):
        filtersettings = list(map(lambda x: x.lower().replace(" ", ""), filtersettings))
        filtersettings = list(filter(lambda x: x != "", filtersettings))
        if len(filtersettings) == 0:
            return media
        media = list(filter(lambda x: x.mediatype.lower() in filtersettings, media))
    else:
        log.info("The settings you picked for the filter are not valid\nNot Filtering")
        log.debug(f"[bold]Combined Media Count Filtered:[/bold] {len(media)}")
    return media


def posts_date_filter_media(media):
    if settings.get_settings().before:
        media = list(
            filter(
                lambda x: x.postdate is None
                or arrow.get(x.postdate) <= settings.get_settings().before,
                media,
            )
        )
    if settings.get_settings().after:
        media = list(
            filter(
                lambda x: x.postdate is None
                or arrow.get(x.postdate) >= settings.get_settings().after,
                media,
            )
        )
    return media


def download_type_filter(media):
    if settings.get_settings().download_type == "protected":
        return list(filter(lambda x: x.protected, media))
    elif settings.get_settings().download_type == "normal":
        return list(filter(lambda x: not x.protected, media))
    else:
        return media


def media_length_filter(media):
    filteredMedia = media
    max_length = settings.get_settings().length_max
    min_length = settings.get_settings().length_min
    if max_length:
        filteredMedia = list(
            filter(
                lambda x: x.mediatype != "videos"
                or x.duration is None
                or x.duration <= max_length,
                filteredMedia,
            )
        )
    if min_length:
        filteredMedia = list(
            filter(
                lambda x: x.mediatype != "videos"
                or x.duration is None
                or x.duration >= min_length,
                filteredMedia,
            )
        )
    return filteredMedia


def url_filter(media):
    return list((filter(lambda x: x.url or x.mpd, media)))


def unviewable_media_filter(media):
    return list(filter(lambda x: x.canview, media))


def final_media_sort(media):
    media_sort = settings.get_settings().mediasort
    reversed = settings.get_settings().media_desc
    log.debug(f"Using download sort {media_sort}")
    if media_sort == "random":
        random.shuffle(media)
    if media_sort == "date" and reversed:
        media = reversed(media)
    if media_sort == "text":
        media = sorted(media, key=lambda x: x.text, reverse=reversed)
    elif media_sort == "filename":
        media = sorted(media, key=lambda x: x.filename, reverse=reversed)
    return media


def previous_download_filter(medialist, username=None, model_id=None):
    log = logging.getLogger("shared")
    log.info("reading database to retrive previous downloads")
    medialist = seperate.seperate_by_self(medialist)
    # sort to key order same
    medialist = sorted(
        medialist, key=lambda item: (item.post.date, item.id, item.count)
    )
    if settings.get_settings().force_all:
        log.info("forcing all media to be downloaded")
    elif settings.get_settings().force_model_unique:
        log.info("Downloading unique media for model")
        media_ids = set(
            get_media_ids_downloaded_model(model_id=model_id, username=username)
        )
        log.debug(
            f"Number of unique media ids in database for {username}: {len(media_ids)}"
        )
        medialist = seperate.separate_by_id(medialist, media_ids)
        log.debug(f"Number of new mediaids with dupe ids removed: {len(medialist)}")
        medialist = seperate.seperate_avatars(medialist)
        log.debug("Removed previously downloaded avatars/headers")
        log.debug(f"Final Number of media to download {len(medialist)}")
    else:
        log.info("Downloading unique media across all models")
        media_ids = set(get_media_ids_downloaded(model_id=model_id, username=username))
        log.debug("Number of unique media ids in database for all models")
        medialist = seperate.separate_by_id(medialist, media_ids)
        log.debug(f"Number of new mediaids with dupe ids removed: {len(medialist)}")
        medialist = seperate.seperate_avatars(medialist)
        log.debug("Removed previously downloaded avatars/headers")
        log.debug(f"Final Number of media to download {len(medialist)} ")
    return medialist


def media_id_filter(media):
    if not bool(settings.get_settings().media_id):
        return media
    wanted = set([str(x) for x in settings.get_settings().media_id])
    return list(filter(lambda x: str(x.id) in wanted, media))


def post_id_filter(media):
    if not bool(settings.get_settings().post_id):
        return media
    wanted = set([str(x) for x in settings.get_settings().post_id])
    return list(filter(lambda x: str(x.post_id) in wanted, media))


# post filters


def posts_date_filter(media):
    if settings.get_settings().before:
        media = list(
            filter(
                lambda x: x.date is None
                or arrow.get(x.date) <= settings.get_settings().before,
                media,
            )
        )
    if settings.get_settings().after:
        media = list(
            filter(
                lambda x: x.date is None
                or arrow.get(x.date) >= settings.get_settings().after,
                media,
            )
        )
    return media


def temp_post_filter(media):
    if settings.get_settings().timed_only is False:
        return list(filter(lambda x: not x.expires, media))
    elif settings.get_settings().timed_only is True:
        return list(filter(lambda x: x.expires, media))
    return media


def likable_post_filter(post):
    return list(
        filter(
            lambda x: x.opened
            and x.responsetype.capitalize()
            in {"Timeline", "Archived", "Pinned", "Streams"},
            post,
        )
    )


def post_text_filter(media):
    userfilter = settings.get_settings().filter
    if not userfilter:
        return media
    curr = media
    for ele in userfilter:
        if not ele.islower():
            curr = list(
                filter(
                    lambda x: re.search(ele, r"""{}""".format(x.text or ""))
                    is not None,
                    curr,
                )
            )
        else:
            curr = list(
                filter(
                    lambda x: re.search(
                        ele, r"""{}""".format(x.text or ""), re.IGNORECASE
                    )
                    is not None,
                    curr,
                )
            )
    return curr


def post_neg_text_filter(media):
    userfilter = settings.get_settings().neg_filter
    if not bool(userfilter):
        return media
    curr = media
    for ele in userfilter:
        if not ele.islower():
            curr = list(
                filter(
                    lambda x: re.search(ele, r"""{}""".format(x.text or "")) is None,
                    curr,
                )
            )
        else:
            curr = list(
                filter(
                    lambda x: re.search(
                        ele, r"""{}""".format(x.text or ""), re.IGNORECASE
                    )
                    is None,
                    curr,
                )
            )
    return curr


def mass_msg_filter(media):
    if settings.get_settings().mass_msg is None:
        return media
    elif settings.get_settings().mass_msg is True:
        return list((filter(lambda x: x.mass is True, media)))
    elif settings.get_settings().mass_msg is False:
        return list((filter(lambda x: x.mass is False, media)))


def final_post_sort(post):
    post_sort = settings.get_settings().post_sort
    reversed = settings.get_settings().post_desc
    log.debug(f"Using post sort {post_sort}")
    if post_sort == "date" and reversed:
        post = list(reversed(post))
    elif post_sort == "random":
        random.shuffle(post)
    return post
