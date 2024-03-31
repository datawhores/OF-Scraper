def converthelper(media):
    if isinstance(media, list):
        return media
    elif isinstance(media, filter):
        return list(filter)
    else:
        return [media]
