import arrow



def update_before():
    import ofscraper.utils.settings as settings
    args = settings.get_args()
    if args.before_original:
        return
    args.before = arrow.now().shift(days=4)
    settings.update_args(args)
