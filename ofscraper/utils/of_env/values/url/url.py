import os


def load_api_endpoints_config():
    """
    Loads OnlyFans API endpoint URLs from environment variables with default values.

    Returns:
        A dictionary containing all loaded API endpoint URLs.
    """
    config = {}

    # --- OnlyFans API Endpoints ---
    # initEP: Initial API endpoint for session initialization.
    # Default: "https://onlyfans.com/api2/v2/init"
    config["initEP"] = os.getenv(
        "OFSC_API_INIT_EP", "https://onlyfans.com/api2/v2/init"
    )

    # LICENCE_URL: URL for media DRM license acquisition.
    # Default: "https://onlyfans.com/api2/v2/users/media/{}/drm/{}/{}?type=widevine"
    config["LICENCE_URL"] = os.getenv(
        "OFSC_API_LICENCE_URL",
        "https://onlyfans.com/api2/v2/users/media/{}/drm/{}/{}?type=widevine",
    )

    # INDIVIDUAL_TIMELINE: Endpoint for a single timeline post.
    # Default: "https://onlyfans.com/api2/v2/posts/{}?skip_users=all"
    config["INDIVIDUAL_TIMELINE"] = os.getenv(
        "OFSC_API_INDIVIDUAL_TIMELINE",
        "https://onlyfans.com/api2/v2/posts/{}?skip_users=all",
    )

    # meEP: Endpoint for the current user's profile information.
    # Default: "https://onlyfans.com/api2/v2/users/me"
    config["meEP"] = os.getenv(
        "OFSC_API_ME_EP", "https://onlyfans.com/api2/v2/users/me"
    )

    # subscriptionsEP: Endpoint for all subscriptions.
    # Default: "https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=all&format=infinite"
    config["subscriptionsEP"] = os.getenv(
        "OFSC_API_SUBSCRIPTIONS_EP",
        "https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=all&format=infinite",
    )

    # subscriptionsActiveEP: Endpoint for active subscriptions.
    # Default: "https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=active&format=infinite"
    config["subscriptionsActiveEP"] = os.getenv(
        "OFSC_API_SUBSCRIPTIONS_ACTIVE_EP",
        "https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=active&format=infinite",
    )

    # subscriptionsExpiredEP: Endpoint for expired subscriptions.
    # Default: "https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=expired&format=infinite"
    config["subscriptionsExpiredEP"] = os.getenv(
        "OFSC_API_SUBSCRIPTIONS_EXPIRED_EP",
        "https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=expired&format=infinite",
    )

    # subscribeCountEP: Endpoint for subscription count.
    # Default: "https://onlyfans.com/api2/v2/subscriptions/count/all"
    config["subscribeCountEP"] = os.getenv(
        "OFSC_API_SUBSCRIBE_COUNT_EP",
        "https://onlyfans.com/api2/v2/subscriptions/count/all",
    )

    # sortSubscriptions: Endpoint for sorting subscriptions.
    # Default: "https://onlyfans.com/api2/v2/lists/following/sort"
    config["sortSubscriptions"] = os.getenv(
        "OFSC_API_SORT_SUBSCRIPTIONS",
        "https://onlyfans.com/api2/v2/lists/following/sort",
    )

    # profileEP: Endpoint for a specific user profile.
    # Default: "https://onlyfans.com/api2/v2/users/{}"
    config["profileEP"] = os.getenv(
        "OFSC_API_PROFILE_EP", "https://onlyfans.com/api2/v2/users/{}"
    )

    # timelineEP: Endpoint for user's timeline posts.
    # Default: "https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&pinned=0&format=infinite"
    config["timelineEP"] = os.getenv(
        "OFSC_API_TIMELINE_EP",
        "https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&pinned=0&format=infinite",
    )

    # timelineNextEP: Endpoint for next set of timeline posts.
    # Default: "https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&pinned=0&format=infinite"
    config["timelineNextEP"] = os.getenv(
        "OFSC_API_TIMELINE_NEXT_EP",
        "https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&pinned=0&format=infinite",
    )

    # timelinePinnedEP: Endpoint for user's pinned timeline posts.
    # Default: "https://onlyfans.com/api2/v2/users/{}/posts?skip_users=all&pinned=1&counters={}&format=infinite"
    config["timelinePinnedEP"] = os.getenv(
        "OFSC_API_TIMELINE_PINNED_EP",
        "https://onlyfans.com/api2/v2/users/{}/posts?skip_users=all&pinned=1&counters={}&format=infinite",
    )

    # streamsEP: Endpoint for user's streams/live content.
    # Default: "https://onlyfans.com/api2/v2/users/{}/posts/streams?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&format=infinite"
    config["streamsEP"] = os.getenv(
        "OFSC_API_STREAMS_EP",
        "https://onlyfans.com/api2/v2/users/{}/posts/streams?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&format=infinite",
    )

    # streamsNextEP: Endpoint for next set of streams/live content.
    # Default: "https://onlyfans.com/api2/v2/users/{}/posts/streams?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&format=infinite"
    config["streamsNextEP"] = os.getenv(
        "OFSC_API_STREAMS_NEXT_EP",
        "https://onlyfans.com/api2/v2/users/{}/posts/streams?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&format=infinite",
    )

    # archivedEP: Endpoint for user's archived posts.
    # Default: "https://onlyfans.com/api2/v2/users/{}/posts/archived?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&format=infinite"
    config["archivedEP"] = os.getenv(
        "OFSC_API_ARCHIVED_EP",
        "https://onlyfans.com/api2/v2/users/{}/posts/archived?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&format=infinite",
    )

    # archivedNextEP: Endpoint for next set of archived posts.
    # Default: "https://onlyfans.com/api2/v2/users/{}/posts/archived?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&format=infinite"
    config["archivedNextEP"] = os.getenv(
        "OFSC_API_ARCHIVED_NEXT_EP",
        "https://onlyfans.com/api2/v2/users/{}/posts/archived?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&format=infinite",
    )

    # highlightsWithStoriesEP: Endpoint for highlights with stories.
    # Default: "https://onlyfans.com/api2/v2/users/{}/stories/highlights?limit=5&offset={}&unf=1"
    config["highlightsWithStoriesEP"] = os.getenv(
        "OFSC_API_HIGHLIGHTS_WITH_STORIES_EP",
        "https://onlyfans.com/api2/v2/users/{}/stories/highlights?limit=5&offset={}&unf=1",
    )

    # highlightsWithAStoryEP: Endpoint for highlights with a single story.
    # Default: "https://onlyfans.com/api2/v2/users/{}/stories?unf=1"
    config["highlightsWithAStoryEP"] = os.getenv(
        "OFSC_API_HIGHLIGHTS_WITH_A_STORY_EP",
        "https://onlyfans.com/api2/v2/users/{}/stories?unf=1",
    )

    # storyEP: Endpoint for a specific story.
    # Default: "https://onlyfans.com/api2/v2/stories/highlights/{}?unf=1"
    config["storyEP"] = os.getenv(
        "OFSC_API_STORY_EP", "https://onlyfans.com/api2/v2/stories/highlights/{}?unf=1"
    )

    # messagesEP: Endpoint for chat messages.
    # Default: "https://onlyfans.com/api2/v2/chats/{}/messages?limit=100&order=desc&skip_users=all&skip_users_dups=1"
    config["messagesEP"] = os.getenv(
        "OFSC_API_MESSAGES_EP",
        "https://onlyfans.com/api2/v2/chats/{}/messages?limit=100&order=desc&skip_users=all&skip_users_dups=1",
    )

    # messagesNextEP: Endpoint for next set of chat messages.
    # Default: "https://onlyfans.com/api2/v2/chats/{}/messages?limit=100&id={}&order=desc&skip_users=all&skip_users_dups=1"
    config["messagesNextEP"] = os.getenv(
        "OFSC_API_MESSAGES_NEXT_EP",
        "https://onlyfans.com/api2/v2/chats/{}/messages?limit=100&id={}&order=desc&skip_users=all&skip_users_dups=1",
    )

    # favoriteEP: Endpoint for favoriting/unfavoriting a post.
    # Default: "https://onlyfans.com/api2/v2/posts/{}/favorites/{}"
    config["favoriteEP"] = os.getenv(
        "OFSC_API_FAVORITE_EP", "https://onlyfans.com/api2/v2/posts/{}/favorites/{}"
    )

    # postURL: Base URL for a post on OnlyFans.
    # Default: "https://onlyfans.com/{}/{}"
    config["postURL"] = os.getenv("OFSC_POST_URL", "https://onlyfans.com/{}/{}")

    # donateEP: Donation endpoint (Buy Me A Coffee example).
    # Default: "https://www.buymeacoffee.com/excludedBittern"
    config["donateEP"] = os.getenv(
        "OFSC_DONATE_EP", "https://www.buymeacoffee.com/excludedBittern"
    )

    # purchased_contentEP: Endpoint for purchased content by user ID.
    # Default: "https://onlyfans.com/api2/v2/posts/paid?limit=100&skip_users=all&format=infinite&offset={}&user_id={}"
    config["purchased_contentEP"] = os.getenv(
        "OFSC_PURCHASED_CONTENT_EP",
        "https://onlyfans.com/api2/v2/posts/paid?limit=100&skip_users=all&format=infinite&offset={}&user_id={}",
    )

    # purchased_contentALL: Endpoint for all purchased content.
    # Default: "https://onlyfans.com/api2/v2/posts/paid?limit=100&skip_users=all&format=infinite&offset={}"
    config["purchased_contentALL"] = os.getenv(
        "OFSC_PURCHASED_CONTENT_ALL_EP",
        "https://onlyfans.com/api2/v2/posts/paid?limit=100&skip_users=all&format=infinite&offset={}",
    )

    # highlightSPECIFIC: Endpoint for a specific highlight story.
    # Default: "https://onlyfans.com/api2/v2/stories/highlights/{}"
    config["highlightSPECIFIC"] = os.getenv(
        "OFSC_HIGHLIGHT_SPECIFIC_EP",
        "https://onlyfans.com/api2/v2/stories/highlights/{}",
    )

    # storiesSPECIFIC: Endpoint for a specific story.
    # Default: "https://onlyfans.com/api2/v2/stories/{}"
    config["storiesSPECIFIC"] = os.getenv(
        "OFSC_STORIES_SPECIFIC_EP", "https://onlyfans.com/api2/v2/stories/{}"
    )

    # messageSPECIFIC: Endpoint for specific chat messages (by first ID).
    # Default: "https://onlyfans.com/api2/v2/chats/{}/messages?limit=10&order=desc&skip_users=all&firstId={}"
    config["messageSPECIFIC"] = os.getenv(
        "OFSC_MESSAGE_SPECIFIC_EP",
        "https://onlyfans.com/api2/v2/chats/{}/messages?limit=10&order=desc&skip_users=all&firstId={}",
    )

    # messageTableSPECIFIC: Web UI URL for specific messages.
    # Default: "https://onlyfans.com/my/chats/{}/?id={}"
    config["messageTableSPECIFIC"] = os.getenv(
        "OFSC_MESSAGE_TABLE_SPECIFIC_URL", "https://onlyfans.com/my/chats/{}/?id={}"
    )

    # labelsEP: Endpoint for user's labels.
    # Default: "https://onlyfans.com/api2/v2/users/{}/labels?limit=100&offset={}&order=desc&non-empty=1"
    config["labelsEP"] = os.getenv(
        "OFSC_LABELS_EP",
        "https://onlyfans.com/api2/v2/users/{}/labels?limit=100&offset={}&order=desc&non-empty=1",
    )

    # labelledPostsEP: Endpoint for posts under a specific label.
    # Default: "https://onlyfans.com/api2/v2/users/{}/posts?limit=100&offset={}&order=publish_date_desc&skip_users=all&counters=0&format=infinite&label={}"
    config["labelledPostsEP"] = os.getenv(
        "OFSC_LABELLED_POSTS_EP",
        "https://onlyfans.com/api2/v2/users/{}/posts?limit=100&offset={}&order=publish_date_desc&skip_users=all&counters=0&format=infinite&label={}",
    )

    # listEP: Endpoint for user's custom lists.
    # Default: "https://onlyfans.com/api2/v2/lists?offset={}&skip_users=all&limit=100&format=infinite"
    config["listEP"] = os.getenv(
        "OFSC_LIST_EP",
        "https://onlyfans.com/api2/v2/lists?offset={}&skip_users=all&limit=100&format=infinite",
    )

    # listusersEP: Endpoint for users within a specific list.
    # Default: "https://onlyfans.com/api2/v2/lists/{}/users?offset={}&limit=100&format=infinite"
    config["listusersEP"] = os.getenv(
        "OFSC_LIST_USERS_EP",
        "https://onlyfans.com/api2/v2/lists/{}/users?offset={}&limit=100&format=infinite",
    )

    # sortSubscriptions: API endpoint for sorting subscriptions
    # Default: https://onlyfans.com/api2/v2/lists/following/sort
    config["sortSubscriptions"] = os.getenv(
        "OF_SORT_SUBSCRIPTIONS_URL", "https://onlyfans.com/api2/v2/lists/following/sort"
    )

    return config
