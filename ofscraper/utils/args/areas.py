import ofscraper.utils.args.globals as global_args


def get_like_area():
    post = None
    all_choices = [
        "Archived",
        "Timeline",
        "Pinned",
        "Labels",
    ]
    if len(global_args.getArgs().like_area) == 0:
        post = set(global_args.getArgs().posts)
    else:
        post = set(global_args.getArgs().like_area)
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
    if len(global_args.getArgs().download_area) == 0:
        post = set(global_args.getArgs().posts)
    else:
        post = set(global_args.getArgs().download_area)
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
