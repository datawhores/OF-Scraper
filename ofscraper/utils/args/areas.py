import ofscraper.utils.args.read as read_args


def get_like_area():
    post = None
    all_choices = [
        "Archived",
        "Timeline",
        "Pinned",
        "Labels",
    ]
    if len(read_args.retriveArgs().like_area) == 0:
        post = set(read_args.retriveArgs().posts)
    else:
        post = set(read_args.retriveArgs().like_area)
    if "All" in post:
        post.update(set(all_choices))
    return list(
        filter(
            lambda x: x != "All"
            and x[0] != "-"
            and f"-{x}" not in post
            and x in all_choices,
            post,
        )
    )


def get_download_area():
    post = None
    all_choices = [
        "Highlights",
        "Archived",
        "Messages",
        "Timeline",
        "Pinned",
        "Stories",
        "Purchased",
        "Profile",
        "Labels",
    ]
    if len(read_args.retriveArgs().download_area) == 0:
        post = set(read_args.retriveArgs().posts)
    else:
        post = set(read_args.retriveArgs().download_area)
    if "All" in post:
        post.update(set(all_choices))
    return list(
        filter(
            lambda x: x != "All"
            and x[0] != "-"
            and f"-{x}" not in post
            and x in all_choices,
            post,
        )
    )
