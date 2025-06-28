import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings


def get_like_area():
    post = None
    all_choices = ["Archived", "Timeline", "Pinned", "Streams"]
    all_choices.append("Label") if of_env.getattr("INCLUDE_LABELS_ALL") else None
    if len(settings.get_settings().like_area or []) == 0:
        post = set(settings.get_settings().posts or [])
    else:
        post = set(settings.get_settings().like_area or [])
    if "All" in post:
        post.update(set(all_choices))
    return finalize_choice(all_choices, post)


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
        "Streams",
    ]
    all_choices.append("Label") if of_env.getattr("INCLUDE_LABELS_ALL") else None
    if len(settings.get_settings().download_area or []) == 0:
        post = set(settings.get_settings().posts or [])
    else:
        post = set(settings.get_settings().download_area or [])
    if "All" in post:
        post.update(set(all_choices))
    return finalize_choice(all_choices, post)


def get_text_area():
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
        "Streams",
    ]
    all_choices.append("Label") if of_env.getattr("INCLUDE_LABELS_ALL") else None
    post = set(settings.get_settings().download_text or [])
    if "All" in post:
        post.update(set(all_choices))
    return finalize_choice(all_choices, post)


def finalize_choice(all_choices, post):
    out = set(post)
    if ("Labels*" or "Labels+") in post:
        post.update(set(all_choices))
        post.update({"Labels"})
        post.discard("Labels*")
        post.discard("Labels+")
        all_choices.append("Labels")
    out = set(
        list(
            filter(
                lambda x: x != "All"
                and x[0] != "-"
                and f"-{x}" not in post
                and x in all_choices + ["Labels"],
                post,
            )
        )
    )
    return out


def get_final_posts_area():
    final_post_areas = set()
    actions = settings.get_settings().action
    if "download" in actions:
        final_post_areas.update(get_download_area())
        final_post_areas.update(get_text_area())
    if settings.get_settings().command == "metadata":
        final_post_areas.update(get_download_area())
    if "like" in actions or "unlike" in actions:
        final_post_areas.update(get_like_area())
    return final_post_areas
