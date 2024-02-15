import logging

import ofscraper.filters.media.helpers as helpers

log = logging.getLogger("shared")


def filterMedia(media):
    count = 1
    logformater = "{} data: {} id: {} postid: {}"
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media no filter:",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}-> all media no filter count: {len(media)}")
    media = helpers.sort_media(media)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> final media  from retrived post: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}->  final media count from retrived post: {len(media)}")
    media = helpers.dupefilter(media)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media dupe filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )

    log.debug(f"filter {count}-> all media dupe filter count: {len(media)}")
    media = helpers.post_datesorter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 3-> all media datesort: ", x.media, x.id, x.postid
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}-> all media datesort count: {len(media)}")
    media = helpers.posts_type_filter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media post media type filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )

    log.debug(f"filter {count}-> all media post media type filter count: {len(media)}")
    media = helpers.posts_date_filter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media post date filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}-> all media post date filter: {len(media)}")
    media = helpers.post_timed_filter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  all media post timed post filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}->  all media post timed post filter count: {len(media)}")
    media = helpers.post_user_filter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media post included text filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(
        f"filter {count}->  all media post included text filter count: {len(media)}"
    )
    media = helpers.anti_post_user_filter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}-> all media post excluded text filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(
        f"filter {count}->  all media post excluded text filter count: {len(media)}"
    )
    media = helpers.download_type_filter(media)
    count += 1

    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  all download type filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter {count}->  all media download type filter count: {len(media)}")

    media = helpers.mass_msg_filter(media)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  mass message filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )

    media = helpers.url_filter(media)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  valid url filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter{count}->  all media valid url filter count {len(media)}")

    media = helpers.final_post_sort(media)
    count += 1
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        f"filter {count}->  all media final sort: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter{count}-> all media final sort count {len(media)}")

    return media


def media_filter_for_like(media, like=False):
    media = helpers.timeline_array_filter(media)
    post_type = "likable" if like else "unlikable"
    log.debug(
        f"[bold]Number of {post_type} posts left after date filter[/bold] {len(media)}"
    )
    media = helpers.final_post_sort(media)
    media = helpers.post_count_filter(media)
    log.debug(f"[bold]Final Number of open and {post_type} post[/bold] {len(media)}")
    return media
