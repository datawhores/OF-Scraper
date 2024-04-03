import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as const


def get_like_area():
    post = None
    all_choices = [
        "Archived",
        "Timeline",
        "Pinned",
    ]
    all_choices.append("Label") if const.getattr("INCLUDE_LABELS_ALL") else None
    if len(read_args.retriveArgs().like_area) == 0:
        post = set(read_args.retriveArgs().posts)
    else:
        post = set(read_args.retriveArgs().like_area)
    if "All" in post:
        post.update(set(all_choices))
    elif ("Labels*" or "Labels+") in post:
        post.update(set(all_choices))
        post.update({"Labels"})
        post.discard("Labels*")
        post.discard("Labels+")
    return list(
        filter(
            lambda x: x != "All"
            and x[0] != "-"
            and f"-{x}" not in post
            and x in all_choices + ["Labels"],
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
    ]
    all_choices.append("Label") if const.getattr("INCLUDE_LABELS_ALL") else None
    if len(read_args.retriveArgs().download_area) == 0:
        post = set(read_args.retriveArgs().posts)
    else:
        post = set(read_args.retriveArgs().download_area)
    if "All" in post:
        post.update(set(all_choices))
    elif ("Labels*" or "Labels+") in post:
        post.update(set(all_choices))
        post.update({"Labels"})
        post.discard("Labels*")
        post.discard("Laabels+")
    return list(
        filter(
            lambda x: x != "All"
            and x[0] != "-"
            and f"-{x}" not in post
            and x in all_choices + ["Labels"],
            post,
        )
    )
