def converthelper(media, **kwargs):
    if isinstance(media, list, **kwargs):
        return media
    elif isinstance(media, filter, **kwargs):
        return list(filter)
    else:
        return [media]
