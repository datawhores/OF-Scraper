import logging

import ofscraper.filters.media.helpers as helpers

log = logging.getLogger("shared")


def filterMedia(media):
    logformater = "{} data: {} id: {} postid: {}"
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 1-> all media no filter:", x.media, x.id, x.postid
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter 1-> all media no filter count: {len(media)}")
    media = helpers.dupefilter(media)
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 2-> all media dupe filter: ", x.media, x.id, x.postid
                    ),
                    media,
                )
            )
        )
    )

    log.debug(f"filter 2-> all media dupe filter count: {len(media)}")
    media = helpers.post_datesorter(media)
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
    log.debug(f"filter 3-> all media datesort count: {len(media)}")
    media = helpers.posts_type_filter(media)
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 4-> all media post media type filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )

    log.debug(f"filter 4-> all media post media type filter count: {len(media)}")
    media = helpers.posts_date_filter(media)
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 5-> all media post date filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter 5-> all media post date filter: {len(media)}")
    media = helpers.post_timed_filter(media)
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 6->  all media post timed post filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter 6->  all media post timed post filter count: {len(media)}")
    media = helpers.post_user_filter(media)
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 7-> all media post included text filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter 7->  all media post included text filter count: {len(media)}")
    media = helpers.anti_post_user_filter(media)
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 8-> all media post excluded text filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter 8->  all media post excluded text filter count: {len(media)}")
    media = helpers.download_type_filter(media)
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 9->  all download type filter: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter 9->  all media download type filter count: {len(media)}")

    media = helpers.mass_msg_filter(media)
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 10->  mass message filter: ", x.media, x.id, x.postid
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter 10->  all media mass message filter count: {len(media)}")

    media = helpers.sort_media(media)
    log.trace(
        "\n\n\n".join(
            list(
                map(
                    lambda x: logformater.format(
                        "filter 11-> final media  from retrived post: ",
                        x.media,
                        x.id,
                        x.postid,
                    ),
                    media,
                )
            )
        )
    )
    log.debug(f"filter 11->  final media count from retrived post: {len(media)}")
    return media
