import logging
import re
import traceback
from collections import defaultdict
from functools import partial

import ofscraper.data.api.highlights as highlights_
import ofscraper.data.api.messages as messages_
import ofscraper.data.api.paid as paid
import ofscraper.data.api.profile as profile
import ofscraper.db.operations as operations
import ofscraper.commands.scraper.actions.download.download as download
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater

import ofscraper.utils.system.network as network
from ofscraper.data.api.common.timeline import get_individual_timeline_post
from ofscraper.commands.utils.strings import download_manual_str, post_str_manual
from ofscraper.db.operations import make_changes_to_content_tables
from ofscraper.db.operations_.media import batch_mediainsert
from ofscraper.utils.checkers import check_auth
from ofscraper.utils.context.run_async import run
from ofscraper.main.close.final.final import final_action
import ofscraper.managers.manager as manager
import ofscraper.utils.settings as settings
from ofscraper.managers.postcollection import PostCollection
from ofscraper.scripts.after_download_action_script import after_download_action_script

log = logging.getLogger("shared")


def manual_download(urls=None):
    """
    Main function to handle manual download of posts from URLs.
    """
    try:
        network.check_cdm()
        allow_manual_dupes()
        log = logging.getLogger("shared")
        check_auth()

        url_dicts = process_urls(urls)
        if not url_dicts:
            log.warning("No valid data found from the provided URLs.")
            return

        with progress_utils.setup_live("manual"):
            # Consolidate media and posts from all processed collections
            all_media = [
                item
                for url_dict in url_dicts.values()
                for item in url_dict["collection"].all_unique_media
            ]
            all_posts = [
                item
                for url_dict in url_dicts.values()
                for item in url_dict["collection"].posts
            ]
            log.debug(f"Total unique media items found: {len(all_media)}")
            log.debug(f"Total posts found: {len(all_posts)}")

            if not all_media and not all_posts:
                log.warning("No media or posts were found to process.")
                return
            # Set user data for models that will be processed
            set_user_data(url_dicts)

        for _, value in url_dicts.items():
            collection = value["collection"]
            model_id = collection.model_id
            username = collection.username
            media = collection.all_unique_media
            posts = collection.posts

            log.info(download_manual_str.format(username=username))
            progress_updater.activity.update_task(
                description=download_manual_str.format(username=username), visible=True
            )

            operations.table_init_create(model_id=model_id, username=username)
            make_changes_to_content_tables(posts, model_id=model_id, username=username)
            batch_mediainsert(media, username=username, model_id=model_id)

            download.download_process(
                username,
                model_id,
                media,
                posts,
            )
            manager.Manager.model_manager.mark_as_processed(
                username, activity="download"
            )
            manager.Manager.stats_manager.update_and_print_stats(
                username, "download", media, ignore_missing=True
            )
            after_download_action_script(username, media)
        final_action()

    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
        raise e


def process_urls(urls):
    """
    Parses URLs, fetches data, and organizes it by model.
    This version is refactored to be data-driven and reduce repetition.
    """
    out_dict = defaultdict(lambda: {"collection": None})

    # Map API types to their corresponding data-fetching functions
    API_MAP = {
        "post": get_individual_timeline_post,
        "msg": messages_.get_individual_messages_post,
        "msg2": messages_.get_individual_messages_post,
        "highlights": highlights_.get_individual_highlights,
        "stories": highlights_.get_individual_stories,  # Assumed function
        "unknown": unknown_type_helper,
    }

    with progress_utils.setup_live("api"):
        for url in url_helper(urls):
            progress_updater.activity.update_task(
                description=post_str_manual.format(url=url), visible=True
            )

            model_id, post_id, api_type = get_info(url)
            if not api_type:
                log.warning(f"Could not determine type for URL: {url}")
                continue

            # Get user info first if available
            username = None
            if model_id:
                user_data = profile.scrape_profile(model_id)
                model_id = user_data.get("id")
                username = user_data.get("username")

            # Fetch data using the mapped function
            fetch_func = API_MAP.get(api_type)
            if not fetch_func:
                log.warning(f"No fetch function defined for API type: {api_type}")
                continue

            # Use partial for functions that need model_id
            if api_type in {"msg", "msg2"}:
                fetch_func = partial(fetch_func, model_id)

            value = fetch_func(post_id)
            if not value or value.get("error"):
                log.warning(f"Failed to get data for URL {url}")
                continue

            # For unknown types, extract user info from the response
            if api_type == "unknown":
                username, model_id = get_profile_helper(value)
                if not username:
                    log.warning(f"Could not find user info for post ID {post_id}")
                    continue

            # Initialize collection if it doesn't exist
            if out_dict[model_id]["collection"] is None:
                out_dict[model_id]["collection"] = PostCollection(
                    username=username, model_id=model_id
                )

            # Add the fetched post to the collection
            out_dict[model_id]["collection"].add_posts(value)

    return out_dict


def get_info(url):
    """
    Parses a URL to extract model ID, post ID, and API type.
    Refactored to use a data-driven pattern for maintainability.
    """
    # Each tuple: (regex_pattern, (api_type, model_group_index, post_group_index))
    # Indices are 1-based for match groups. 0 means not present in URL.
    URL_PATTERNS = [
        (
            re.compile(
                f"chats/chat/({of_env.getattr('NUMBER_REGEX')}+)/.*?({of_env.getattr('NUMBER_REGEX')}+)"
            ),
            ("msg", 1, 2),
        ),
        (
            re.compile(f"/({of_env.getattr('NUMBER_REGEX')}+)/stories/highlights"),
            ("highlights", 0, 1),
        ),
        (
            re.compile(f"/stories/highlights/({of_env.getattr('NUMBER_REGEX')}+)"),
            ("highlights", 0, 1),
        ),
        (
            re.compile(f"/({of_env.getattr('NUMBER_REGEX')}+)/stories"),
            ("stories", 0, 1),
        ),
        (
            re.compile(
                f"chats/({of_env.getattr('USERNAME_REGEX')}+)/.*?(id|firstId)=({of_env.getattr('NUMBER_REGEX')}+)"
            ),
            ("msg2", 1, 3),
        ),
        (
            re.compile(
                f"/({of_env.getattr('NUMBER_REGEX')}+)/({of_env.getattr('USERNAME_REGEX')}+)"
            ),
            ("post", 2, 1),
        ),
        (re.compile(f"^{of_env.getattr('NUMBER_REGEX')}+$"), ("unknown", 0, 0)),
    ]

    for pattern, (api_type, model_idx, post_idx) in URL_PATTERNS:
        match = pattern.search(url)
        if match:
            model_id = match.group(model_idx) if model_idx > 0 else None
            post_id = match.group(post_idx) if post_idx > 0 else url
            return model_id, post_id, api_type

    return None, None, None


# --- Helper Functions ---


def url_helper(urls):
    """Combines URLs from args and the provided list."""
    args = settings.get_args()
    out = []
    out.extend(args.get("file", []) or [])
    out.extend(args.get("url", []) or [])
    out.extend(urls or [])
    return map(str.strip, out)


def get_profile_helper(value):
    """Extracts username and model_id from a post's author data."""
    author_info = value.get("author", {})
    model_id = author_info.get("id")
    if model_id:
        data = profile.scrape_profile(model_id)
        return data.get("username"), data.get("id")
    return None, None


@run
async def unknown_type_helper(postid):
    """
    Helper for 'unknown' type URLs.
    Tries to fetch the post from the timeline. If the post has no media,
    it attempts a fallback search on the user's paid content.
    """
    log = logging.getLogger("shared")
    value = get_individual_timeline_post(postid)

    # If timeline post is found and has media, we are done.
    if value and not value.get("error") and (value.get("media") or value.get("medias")):
        return value

    # If timeline post has no media, or was not found, try paid posts.
    log.debug(
        f"Post {postid} from timeline has no media or was not found. Attempting paid fallback."
    )

    if value and not value.get("error"):
        username, model_id = get_profile_helper(value)
        if username and model_id:
            paid_post = await _find_paid_post_by_id(postid, model_id, username)
            if paid_post:
                return paid_post  # Return the paid post if found

    return value  # Return original timeline value (or None) if fallback fails


def set_user_data(url_dicts):
    """Adds models found to the main model manager."""
    for url_dict in url_dicts.values():
        if url_dict["collection"] and url_dict["collection"].username:
            manager.Manager.model_manager.add_models(
                url_dict["collection"].username, activity="download"
            )


def allow_manual_dupes():
    """Forces settings to allow debug duplicate downloads for manual mode."""
    args = settings.get_args()
    args.force_all = True
    settings.update_args(args)


async def _find_paid_post_by_id(post_id, model_id, username):
    """Async helper to search a user's paid posts for a specific post ID."""
    post_id = str(post_id)
    log = logging.getLogger("shared")
    log.debug(f"Searching paid content for post_id: {post_id} under user {username}")
    async with manager.Manager.aget_ofsession(
        sem_count=of_env.getattr("API_REQ_CHECK_MAX"),
    ) as c:
        paid_posts_data = await paid.get_paid_posts(username, model_id, c=c) or []
        for post_data in paid_posts_data:
            if str(post_data.get("id")) == post_id:
                log.debug(f"Found matching paid post for id {post_id}")
                # Ensure author info is present for downstream processing
                if "author" not in post_data:
                    post_data["author"] = {"id": model_id}
                return post_data
    return None
