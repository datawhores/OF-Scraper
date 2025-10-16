import ofscraper.utils.settings as settings


def get_allowed_qualities():
    qualities = {"source": 4000, "240": 240, "720": 720}
    minQuality = settings.get_settings().quality or "source"
    validQualities = list(
        filter(
            lambda x: x[1] >= qualities.get(minQuality),
            qualities.items(),
        )
    )
    return list(map(lambda x: x[0], validQualities))
