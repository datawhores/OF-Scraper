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
    log.debug(f"filter{count}->  all media mass message filter count: {len(media)}")

    return media
