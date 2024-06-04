import logging

import ofscraper.filters.media.helpers.helpers as helpers
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants

log = logging.getLogger("shared")


def filtermediaFinal(media,username=None,model_id=None):
    count = 1

    helpers.trace_log_media(count, media, "initial media no filter:")
    log.debug(f"filter {count}-> initial media no filter count: {len(media)}")

    media = helpers.sort_by_date(media)
    count += 1
    helpers.trace_log_media(count, media, "sorted by date initial")
    log.debug(f"filter {count}-> sorted media count: {len(media)}")


    media = helpers.unviewable_media_filter(media)
    count += 1
    helpers.trace_log_media(count, media, "filtered viewable media")
    log.debug(f"filter {count}-> viewable media filter count: {len(media)}")


    if not read_args.retriveArgs().command == "metadata":
        media = helpers.dupefiltermedia(media)
        count += 1
        helpers.trace_log_media(count, media, "media dupe media_id filter:")
        log.debug(f"filter {count}->  media dupe media_id filter count: {len(media)}")
        media = helpers.unviewable_media_filter(media)
        count += 1
        helpers.trace_log_media(count, media, "unviewable media filter:")
        log.debug(f"filter {count}->  media unviewable filter count: {len(media)}")
    elif read_args.retriveArgs().command == "metadata":
        if constants.getattr("REMOVE_UNVIEWABLE_METADATA"):
            count += 1
            helpers.trace_log_media(count, media, "unviewable media filter:")
            log.debug(f"filter {count}->  media unviewable filter count: {len(media)}")
    return helpers.previous_download_filter(media, username=username, model_id=model_id)






def filtermediaAreas(media, **kwargs):
    count = 1

    helpers.trace_log_media(count, media, "initial media no filter:")
    log.debug(f"filter {count}-> initial media no filter count: {len(media)}")

    media = helpers.sort_by_date(media)
    count += 1
    helpers.trace_log_media(count, media, "sorted by date initial")

    media = helpers.post_datesorter(media)
    count += 1
    helpers.trace_log_media(count, media, "media datesort:")
    log.debug(f"filter {count}-> media datesort count: {len(media)}")

    media = helpers.mediatype_type_filter(media)
    count += 1
    helpers.trace_log_media(count, media, "media post media type filter:")
    log.debug(f"filter {count}-> media post media type filter count: {len(media)}")

    media = helpers.posts_date_filter_media(media)
    count += 1
    helpers.trace_log_media(count, media, "media post date filter:")
    log.debug(f"filter {count}-> media post date filter: {len(media)}")

    media = helpers.temp_post_filter(media)
    count += 1
    helpers.trace_log_media(count, media, "media post timed post filter:")
    log.debug(f"filter {count}->  media post timed post filter count: {len(media)}")

    media = helpers.post_text_filter(media)
    count += 1
    helpers.trace_log_media(count, media, "media text filter:")
    log.debug(f"filter {count}->  media text filter count: {len(media)}")

    media = helpers.post_neg_text_filter(media)
    count += 1
    helpers.trace_log_media(count, media, "media excluded text filter:")

    log.debug(f"filter {count}->  media excluded text filter count: {len(media)}")

    media = helpers.download_type_filter(media)
    count += 1
    helpers.trace_log_media(count, media, "download type filter:")
    log.debug(f"filter {count}->  media download type filter count: {len(media)}")

    media = helpers.mass_msg_filter(media)
    count += 1
    helpers.trace_log_media(count, media, "mass message filter:")
    log.debug(f"filter {count}->  media mass message filter count: {len(media)}")

    media = helpers.media_length_filter(media)
    count += 1
    helpers.trace_log_media(count, media, "media length filter:")

    media = helpers.final_media_sort(media)
    count += 1
    helpers.trace_log_media(count, media, "final sort filter:")
    log.debug(f"filter {count}->  media final sort filter count: {len(media)}")
    return media

def filterPostFinal(post):
    count = 1
    helpers.trace_log_post(count, post, "initial posts no filter:")
    log.debug(f"filter {count}-> initial posts no filter count: {len(post)}")

    count += 1
    post = helpers.sort_by_date(post)
    helpers.trace_log_post(count, post, "post date sort filter:")
    log.debug(f"filter {count}->  post date sort filter count: {len(post)}")

    count += 1
    post = helpers.dupefilterPost(post)
    helpers.trace_log_post(count, post, "post dupe filter:")
    log.debug(f"filter {count}-> post dupe filter count: {len(post)}")

    count += 1
    post = helpers.temp_post_filter(post)
    log.debug(f"filter {count}-> timed posts filter count: {len(post)}")
    helpers.trace_log_post(count, post, "timed posts filter:")

    count += 1
    post = helpers.post_text_filter(post)
    log.debug(f"filter {count}->  post text filter count: {len(post)}")
    helpers.trace_log_post(count, post, "post text filter:")

    count += 1
    post = helpers.post_neg_text_filter(post)
    log.debug(f"filter {count}->  post excluded text filter count {len(post)}")
    helpers.trace_log_post(count, post, "post excluded text filter:")

    count += 1
    post = helpers.mass_msg_filter(post)
    log.debug(f"filter {count}->  mass msg filter count {len(post)}")

    count += 1
    post = helpers.final_post_sort(post)
    helpers.trace_log_post(count, post, "all post final sort:")
    return post


def post_filter_for_like(post, like=False):
    post = helpers.temp_post_filter(post)
    post_type = "likable" if like else "unlikable"
    log.debug(
        f"[bold]Number of {post_type} posts left after filtering for likeable posts[/bold] {len(post)}"
    )
    post = helpers.final_post_sort(post)
    post = helpers.ele_count_filter(post)
    log.debug(f"[bold]Final Number of open and {post_type} post[/bold] {len(post)}")
    return post
