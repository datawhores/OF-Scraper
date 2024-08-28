import logging

import ofscraper.filters.media.filters as helpers
import ofscraper.filters.media.sorter as sorter
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
from ofscraper.filters.media.utils.trace import trace_log_media, trace_log_post
from ofscraper.utils.args.accessors.command import get_command


log = logging.getLogger("shared")


def filtermediaFinal(media, username, model_id):
    actions = read_args.retriveArgs().action
    scrape_paid = read_args.retriveArgs().scrape_paid
    if get_command() == "metadata":
        return filterMediaFinalMetadata(media, username, model_id)
    elif "download" in actions or scrape_paid:
        return filterMediaFinalDownload(media, username, model_id)
    else:
        log.debug("Skipping filtering because download/metadata not in actions")
        return media


def filterMediaFinalMetadata(media, username, model_id):
    log.info(f"finalizing media filtering username:{username} model_id:{model_id} for metadata")
    count = 1
    trace_log_media(count, media, "initial media no filter:")
    log.debug(f"filter {count}-> initial media no filter count: {len(media)}")
    media = helpers.sort_by_date(media)
    count += 1
    trace_log_media(count, media, "sorted by date initial")
    log.debug(f"filter {count}-> sorted media count: {len(media)}")

    if constants.getattr("REMOVE_UNVIEWABLE_METADATA"):
        media = helpers.unviewable_media_filter(media)
        count += 1
        trace_log_media(count, media, "filtered viewable media")
        log.debug(f"filter {count}-> viewable media filter count: {len(media)}")
    media = helpers.ele_count_filter(media)
    count += 1
    trace_log_media(count, media, "media max post count filter:")
    log.debug(f"filter {count}->  media max post count filter count: {len(media)}")
    return helpers.previous_download_filter(media, username=username, model_id=model_id)


def filterMediaFinalDownload(media, username, model_id):
    log.info(f"finalizing media filtering username:{username} model_id: {model_id} for download")
    count = 1
    trace_log_media(count, media, "initial media no filter:")
    log.debug(f"filter {count}-> initial media no filter count: {len(media)}")
    media = helpers.sort_by_date(media)
    count += 1
    trace_log_media(count, media, "sorted by date initial")
    log.debug(f"filter {count}-> sorted media count: {len(media)}")

    media = helpers.unviewable_media_filter(media)
    count += 1
    trace_log_media(count, media, "filtered viewable media")
    log.debug(f"filter {count}-> viewable media filter count: {len(media)}")

    media = helpers.dupefiltermedia(media)
    count += 1
    trace_log_media(count, media, "media dupe media_id filter:")
    log.debug(f"filter {count}->  media dupe media_id filter count: {len(media)}")

    media = helpers.ele_count_filter(media)
    count += 1
    trace_log_media(count, media, "media max post count filter:")
    log.debug(f"filter {count}->  media max post count filter count: {len(media)}")
    return helpers.previous_download_filter(media, username=username, model_id=model_id)


def filtermediaAreas(media, **kwargs):

    actions = read_args.retriveArgs().action
    scrape_paid = read_args.retriveArgs().scrape_paid
    if get_command()== "metadata":
        return filterMediaAreasMetadata(media)
    elif "download" in actions or scrape_paid:
        return filterMediaAreasDownload(media)
    else:
        log.debug("Skipping filtering because download/metadata not in actions")
        return media


def filterMediaAreasMetadata(media):
    log.info("Initial media filtering for metadata")
    return filterMediaAreasHelper(media)


def filterMediaAreasDownload(media):
    log.info("Initial media filtering for download")
    return filterMediaAreasHelper(media)


def filterMediaAreasHelper(media):
    count = 1
    trace_log_media(count, media, "initial media no filter:")
    log.debug(f"filter {count}-> initial media no filter count: {len(media)}")
    media = helpers.sort_by_date(media)

    media = sorter.post_datesorter(media)
    count += 1
    trace_log_media(count, media, "media datesort")
    log.debug(f"filter {count}-> media datesort count: {len(media)}")

    media = helpers.mediatype_type_filter(media)
    count += 1
    trace_log_media(count, media, "media post media type filter:")
    log.debug(f"filter {count}-> media post media type filter count: {len(media)}")

    media = helpers.posts_date_filter_media(media)
    count += 1
    trace_log_media(count, media, "media post date filter:")
    log.debug(f"filter {count}-> media post date filter: {len(media)}")

    media = helpers.temp_post_filter(media)
    count += 1
    trace_log_media(count, media, "media post timed post filter:")
    log.debug(f"filter {count}->  media post timed post filter count: {len(media)}")

    media = helpers.post_text_filter(media)
    count += 1
    trace_log_media(count, media, "media text filter:")
    log.debug(f"filter {count}->  media text filter count: {len(media)}")

    media = helpers.post_neg_text_filter(media)
    count += 1
    trace_log_media(count, media, "media excluded text filter:")
    log.debug(f"filter {count}->  media excluded text filter count: {len(media)}")

    media = helpers.download_type_filter(media)
    count += 1
    trace_log_media(count, media, "download type filter:")
    log.debug(f"filter {count}->  media download type filter count: {len(media)}")

    media = helpers.mass_msg_filter(media)
    count += 1
    trace_log_media(count, media, "mass message filter:")
    log.debug(f"filter {count}->  media mass message filter count: {len(media)}")

    media = helpers.media_length_filter(media)
    count += 1
    trace_log_media(count, media, "media length filter:")

    media = helpers.media_id_filter(media)
    count += 1
    trace_log_media(count, media, "media with media id filter")
    log.debug(f"filter {count}-> media with media id filter count: {len(media)}")

    media = helpers.post_id_filter(media)
    count += 1
    trace_log_media(count, media, "media with media id filter")
    log.debug(f"filter {count}-> media with media id filter count: {len(media)}")

    media = helpers.final_media_sort(media)
    count += 1
    trace_log_media(count, media, "final sort filter:")
    log.debug(f"filter {count}->  media final sort filter count: {len(media)}")

    return list(media)


def filterPostFinalText(post):
    actions = read_args.retriveArgs().action
    scrape_paid = read_args.retriveArgs().scrape_paid
    if "download" not in actions and not scrape_paid:
        log.debug("Skipping filtering because download not in actions")
        return []

    if not settings.get_download_text():
        log.info("Skipping filtering Text files download not toggled")
        return []
    count = 1
    trace_log_post(count, post, "initial posts no filter:")
    log.debug(f"filter {count}-> initial posts no filter count: {len(post)}")

    count += 1
    post = helpers.sort_by_date(post)
    trace_log_post(count, post, "post date sort filter:")
    log.debug(f"filter {count}->  post date sort filter count: {len(post)}")

    count += 1
    post = helpers.dupefilterPost(post)
    trace_log_post(count, post, "post dupe filter:")
    log.debug(f"filter {count}-> post dupe filter count: {len(post)}")

    count += 1
    post = helpers.temp_post_filter(post)
    log.debug(f"filter {count}-> timed posts filter count: {len(post)}")
    trace_log_post(count, post, "timed posts filter:")

    count += 1
    post = helpers.post_text_filter(post)
    log.debug(f"filter {count}->  post text filter count: {len(post)}")
    trace_log_post(count, post, "post text filter:")

    count += 1
    post = helpers.post_neg_text_filter(post)
    log.debug(f"filter {count}->  post excluded text filter count {len(post)}")
    trace_log_post(count, post, "post excluded text filter:")

    count += 1
    post = helpers.mass_msg_filter(post)
    log.debug(f"filter {count}->  mass msg filter count {len(post)}")

    count += 1
    post = helpers.final_post_sort(post)
    trace_log_post(count, post, "all post final sort:")
    return post


def post_filter_for_like(post, like=False):

    actions = read_args.retriveArgs().action
    if "like" not in actions and "unlike" not in actions:
        log.debug("Skipping filtering because like and unlike not in actions")
        return post
    log.info("Filtering posts for like action")
    log.debug(f"initial number of posts for {actions}")

    post = helpers.temp_post_filter(post)
    post_type = "likable" if like else "unlikable"
    alt_post_type = "unliked" if like else "liked"
    log.debug(
        f"[bold]Number of {post_type} posts left after filtering for {alt_post_type} posts[/bold] {len(post)}"
    )
    post = helpers.final_post_sort(post)
    post = helpers.ele_count_filter(post)
    log.debug(f"[bold]Final Number of open and {post_type} post[/bold] {len(post)}")
    return post
