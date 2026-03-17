def converthelper(media, **kwargs):
    if isinstance(media, list):
        return media
    elif isinstance(media, filter):
        return list(media)
    else:
        return [media]
