import arrow

import ofscraper.utils.args.accessors.read as read_args


def update_before():
    import ofscraper.utils.settings as settings
    args = read_args.retriveArgs()
    if args.before_original:
        return
    args.before = arrow.now().shift(days=4)
    settings.update_args(args)
