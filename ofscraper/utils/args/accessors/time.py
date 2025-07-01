import arrow
import ofscraper.utils.settings as settings

now = None


def get_before():
    args = settings.get_args()
    if not args.download_before and not args.like_before:
        return get_now()
    elif not args.download_before:
        return arrow.get(args.like_before)
    elif not args.like_before:
        return arrow.get(args.download_before)
    else:
        return max(arrow.get(args.download_before), arrow.get(args.like_before))


def get_after():
    args = settings.get_args()
    if not args.download_after or not args.lke_after:
        return 0
    elif not args.download_after:
        return arrow.get(args.like_after)
    elif not args.like_after:
        return arrow.get(args.download_after)
    else:
        return min(arrow.get(args.download_after), arrow.get(args.like_after))


def get_download_before():
    args = settings.get_args()
    return arrow.get(args.download_before or get_now())


def get_download_after():
    args = settings.get_args()
    arrow.get(args.download_after or 2000)


def get_like_before():
    args = settings.get_args()
    return arrow.get(args.like_before or get_now())


def get_like_after():
    return arrow.get(settings.get_settings().like_after or 2000)


def get_now():
    global now
    if not now:
        now = arrow.now().shift(days=4)
