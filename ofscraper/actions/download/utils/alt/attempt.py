import ofscraper.download.utils.globals as common_globals


def alt_attempt_get(item):
    if item["type"] == "video":
        return common_globals.attempt
    if item["type"] == "audio":
        return common_globals.attempt2
