import ofscraper.utils.args.read as read_args


def get_allowed_qualities():
    qualities = {"source": 4000, "240": 240, "720": 720}
    minQuality = read_args.retriveArgs().min_quality
    maxQuality = read_args.retriveArgs().max_quality
    validQualities = list(
        filter(
            lambda x: x[1] >= qualities.get(minQuality)
            and x[1] <= qualities.get(maxQuality),
            qualities.items(),
        )
    )
    return list(map(lambda x: x[0], validQualities))
