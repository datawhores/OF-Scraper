import logging
import random
import re
from collections import defaultdict

import arrow

import ofscraper.db.operations_.wrapper as db_wrapper
import ofscraper.utils.separate as separate
import ofscraper.utils.settings as settings
import ofscraper.utils.me as me_util
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded,
    get_media_ids_downloaded_model_sync,
    get_media_post_ids_downloaded,
)
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.scripts.skip_download_script import retry_permanent_skips
from ofscraper.utils.args.accessors.areas import get_download_area

log = logging.getLogger("shared")


def undated_first(date):
    # a sort key that puts undated items first, as the oldest, without
    # comparing None to a date
    return (date is not None, date or "")


def sort_by_date(media):
    return sorted(media, key=lambda x: undated_first(x.date))


def is_purchased_copy(item):
    """Whether the media is a Purchased copy (OnlyFans or Fansly): found in
    Purchased, and its post wasn't also found in another area under the same
    id (``PostCollection`` keeps one post per id, from whichever area came
    first)."""
    return str(item.responsetype).lower() == "paid" and not getattr(
        item.post, "found_outside_purchased", False
    )


def media_key(item):
    """What makes a media one download and one database row: its id, or with
    allow-dupes its id and post, so each post gets its own copy (Purchased
    copies too; --skip-purchased-dupes is applied by
    ``skip_purchased_copies`` when picking downloads, not here)."""
    return (item.id, item.post_id) if settings.allow_dupes() else item.id


# dupe filters that prioritize viewable
def dupefiltermedia(media):
    output = defaultdict(lambda: None)
    media = sorted(
        media, key=lambda item: (undated_first(item.post.date), item.id, item.count)
    )
    for item in media:
        key = media_key(item)
        if not output[key]:
            output[key] = item
        elif item.canview and not output[key].canview:
            output[key] = item
    log.debug(
        f"Number of media after removing duplicated media_ids {len(output.values())}"
    )
    return list(output.values())


def skip_purchased_copies(media, username=None, model_id=None):
    """--skip-purchased-dupes, when picking what to download.

    A Purchased copy and the media's first other copy (the oldest post) are
    one download, whichever was found or saved first:
    - a Purchased copy is left out when another post in the list has the
      media, or a copy of it was downloaded before;
    - media only in Purchased keeps one Purchased copy (a viewable one);
    - the first other copy is left out when a Purchased copy of the media was
      downloaded before. Later copies (reposts) still get their own.
    Whether a copy is a Purchased one goes by its area, and for saved copies
    by the area recorded in its row, not by the order areas were scanned.
    Rows are still saved for every copy (``dupefiltermedia``)."""
    if not settings.skip_purchased_dupes():
        return media
    media = sorted(
        media, key=lambda item: (undated_first(item.post.date), item.id, item.count)
    )
    others = {(item.id, item.post_id) for item in media if not is_purchased_copy(item)}
    elsewhere = {media_id for media_id, _ in others}
    downloaded = downloaded_media_ids(username=username, model_id=model_id)
    if downloaded is None:  # --force-all
        saved, purchase_saved = set(), set()
    else:
        saved = {media_id for media_id, _ in downloaded}
        # a row saved from Purchased whose post is in another area this run
        # is that post, not a Purchased copy
        purchase_saved = {
            media_id
            for media_id, post_id in downloaded_purchased_pairs(
                username=username, model_id=model_id
            )
            if (media_id, post_id) not in others
        }
    kept = {}
    for item in media:
        if not is_purchased_copy(item) or item.id in elsewhere or item.id in saved:
            continue
        current = kept.get(item.id)
        if current is None or (item.canview and not current.canview):
            kept[item.id] = item
    out, first_seen, held = [], set(), 0
    for item in media:
        if is_purchased_copy(item):
            if kept.get(item.id) is item:
                out.append(item)
            continue
        if item.id not in first_seen:
            first_seen.add(item.id)
            if item.id in purchase_saved:
                held += (item.id, item.post_id) not in downloaded
                continue
        out.append(item)
    log_held_back(username, held, get_download_area())
    return out


def log_held_back(username, held, scanned):
    """--skip-purchased-dupes: a downloaded Purchased copy counts for the
    first other copy a run finds. When a run didn't scan Messages, that copy
    may be a repost of a bought message; say so, as it downloads only once a
    run includes Messages."""
    if not held or "Messages" in scanned:
        return
    copies = "1 copy" if held == 1 else f"{held} copies"
    they = "it downloads" if held == 1 else "they download"
    log.info(
        f"[{username}] --skip-purchased-dupes held back {copies} of media bought "
        "earlier: the downloaded Purchased file counts for the first copy this "
        "run found. Messages wasn't scanned; if the bought message is there, "
        f"{they} once a run includes Messages"
    )


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
    filtersettings = settings.get_settings().mediatypes
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
                lambda x: x.mediatype.capitalize() != "Videos"
                or x.duration is None
                or x.duration <= max_length,
                filteredMedia,
            )
        )
    if min_length:
        filteredMedia = list(
            filter(
                lambda x: x.mediatype.capitalize() != "Videos"
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
    is_reversed = settings.get_settings().media_desc
    log.debug(f"Using download sort {media_sort}")
    if media_sort == "random":
        random.shuffle(media)
    if media_sort == "date" and is_reversed:
        media = list(reversed(media))
    if media_sort == "text":
        media = sorted(media, key=lambda x: x.text, reverse=is_reversed)
    elif media_sort == "filename":
        media = sorted(media, key=lambda x: x.filename, reverse=is_reversed)
    return media


def previous_download_filter(medialist, username=None, model_id=None, left_out=None):
    """Leave out media the database marks as downloaded. ``left_out``, a
    dict, gets how many under "already downloaded"."""
    log.info("reading database to retrive previous downloads")

    # sort to key order same
    medialist = sorted(
        medialist,
        key=lambda item: (undated_first(item.post.date), item.id, item.count),
    )

    media_ids = downloaded_media_ids(username=username, model_id=model_id)
    # Early Exit if forcing all
    if media_ids is None:
        return medialist

    # Apply the filters to whichever pool we selected above
    count = len(medialist)
    medialist = [m for m in medialist if media_key(m) not in media_ids]
    if left_out is not None:
        left_out["already downloaded"] = count - len(medialist)
    log.debug(
        f"Number of new media_ids after dupe/previously downloaded ids removed: {len(medialist)}"
    )

    medialist = separate.seperate_avatars(medialist)
    log.debug("Removed previously downloaded avatars/headers")

    log.debug(f"Final Number of media to download {len(medialist)} ")
    return medialist


def per_creator():
    """Whether "already downloaded" goes by the creator's own media only.

    It does with force_model_unique. Without it, it goes by everything in
    the database, which for a SQLite file is its creator's media, so a run
    doesn't leave media out because another creator has it. A database that
    holds every creator (PostgreSQL) keeps to that: the creator's own."""
    return (
        bool(settings.get_settings().force_model_unique)
        or db_wrapper.backend_for({}).holds_every_creator
    )


def downloaded_media_ids(username=None, model_id=None):
    """The media a run leaves out as already downloaded, or None when
    --force-all downloads everything. Media ids, or with allow-dupes
    (media id, post id) pairs: compare them with ``media_key``."""
    if settings.get_settings().force_all:
        log.info("forcing all media to be downloaded")
        return None

    # Determine the pool of already downloaded media. With
    # --retry-permanent-skips, the script's permanent skips aren't in it, so
    # they're offered to the script again (#354)
    retry = retry_permanent_skips()
    if retry:
        log.info("offering permanently skipped media to the skip script again")
    if settings.allow_dupes():
        # a copy downloaded for one post doesn't count for the others
        media_ids = set(
            get_media_post_ids_downloaded(
                model_id=model_id,
                username=username,
                model_only=per_creator(),
                without_permanent_skips=retry,
            )
        )
        log.debug(
            f"Number of downloaded media and post pairs in database: {len(media_ids)}"
        )
    elif per_creator():
        log.info(f"Downloading unique media for model: {username}")
        media_ids = set(
            get_media_ids_downloaded_model_sync(
                model_id=model_id, username=username, without_permanent_skips=retry
            )
        )
        log.debug(
            f"Number of unique media ids in database for {username}: {len(media_ids)}"
        )
    else:
        log.info("Downloading unique media across all models")
        media_ids = set(
            get_media_ids_downloaded(
                model_id=model_id, username=username, without_permanent_skips=retry
            )
        )
        log.debug(
            f"Number of unique media ids in database for all models: {len(media_ids)}"
        )
    return media_ids


def downloaded_purchased_pairs(username=None, model_id=None):
    """(media id, post id) of the downloaded copies saved from Purchased (the
    row's api_type), for --skip-purchased-dupes. The same pool of rows as
    ``downloaded_media_ids`` with allow-dupes."""
    return set(
        get_media_post_ids_downloaded(
            model_id=model_id,
            username=username,
            model_only=per_creator(),
            without_permanent_skips=retry_permanent_skips(),
            purchased_only=True,
        )
    )


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
    is_reversed = settings.get_settings().post_desc
    log.debug(f"Using post sort {post_sort}")
    if post_sort == "date" and is_reversed:
        post = list(reversed(post))
    elif post_sort == "random":
        random.shuffle(post)
    return post


def seperate_self(media):
    """
    Filters out media that was posted by the user running the script.
    """
    if not of_env.getattr("FILTER_SELF_MEDIA"):
        log.debug("FILTER_SELF_MEDIA is disabled. Skipping self-media filtering.")
        return media

    my_id = me_util.get_id()
    initial_length = len(media)

    log.info("Filtering out media created by your own account...")

    # Keep only media where the poster's ID does not match your own ID
    filtered_data = list(filter(lambda x: x.post.fromuser != my_id, media))

    removed_count = initial_length - len(filtered_data)
    if removed_count > 0:
        log.debug(
            f"Removed {removed_count} media items belonging to your own account (ID: {my_id})."
        )

    log.debug(
        f"Number of media items remaining after self-filtering: {len(filtered_data)}"
    )

    return filtered_data
