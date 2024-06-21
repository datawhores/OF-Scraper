initEP = "https://onlyfans.com/api2/v2/init"
LICENCE_URL = "https://onlyfans.com/api2/v2/users/media/{}/drm/{}/{}?type=widevine"


INDIVIDUAL_TIMELINE = "https://onlyfans.com/api2/v2/posts/{}?skip_users=all"
meEP = "https://onlyfans.com/api2/v2/users/me"

subscriptionsEP = "https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=all&format=infinite"
subscriptionsActiveEP = "https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=active&format=infinite"
subscriptionsExpiredEP = "https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=expired&format=infinite"

subscribeCountEP = "https://onlyfans.com/api2/v2/subscriptions/count/all"
sortSubscriptions = "https://onlyfans.com/api2/v2/lists/following/sort"
profileEP = "https://onlyfans.com/api2/v2/users/{}"

timelineEP = "https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&pinned=0&format=infinite"
timelineNextEP = "https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&pinned=0&format=infinite"

timelinePinnedEP = "https://onlyfans.com/api2/v2/users/{}/posts?skip_users=all&pinned=1&counters={}&format=infinite"

streamsEP = "https://onlyfans.com/api2/v2/users/{}/posts/streams?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&format=infinite"

streamsNextEP = "https://onlyfans.com/api2/v2/users/{}/posts/streams?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&format=infinite"

archivedEP = "https://onlyfans.com/api2/v2/users/{}/posts/archived?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&format=infinite"
archivedNextEP = "https://onlyfans.com/api2/v2/users/{}/posts/archived?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&format=infinite"

highlightsWithStoriesEP = (
    "https://onlyfans.com/api2/v2/users/{}/stories/highlights?limit=5&offset={}&unf=1"
)
highlightsWithAStoryEP = "https://onlyfans.com/api2/v2/users/{}/stories?unf=1"
storyEP = "https://onlyfans.com/api2/v2/stories/highlights/{}?unf=1"

messagesEP = "https://onlyfans.com/api2/v2/chats/{}/messages?limit=100&order=desc&skip_users=all&skip_users_dups=1"
messagesNextEP = "https://onlyfans.com/api2/v2/chats/{}/messages?limit=100&id={}&order=desc&skip_users=all&skip_users_dups=1"

favoriteEP = "https://onlyfans.com/api2/v2/posts/{}/favorites/{}"
postURL = "https://onlyfans.com/{}/{}"


donateEP = "https://www.buymeacoffee.com/excludedBittern"

purchased_contentEP = "https://onlyfans.com/api2/v2/posts/paid?limit=100&skip_users=all&format=infinite&offset={}&user_id={}"
purchased_contentALL = "https://onlyfans.com/api2/v2/posts/paid?limit=100&skip_users=all&format=infinite&offset={}"

highlightSPECIFIC = "https://onlyfans.com/api2/v2/stories/highlights/{}"
storiesSPECIFIC = "https://onlyfans.com/api2/v2/stories/{}"
messageSPECIFIC = "https://onlyfans.com/api2/v2/chats/{}/messages?limit=10&order=desc&skip_users=all&firstId={}"
messageTableSPECIFIC = "https://onlyfans.com/my/chats/{}/?id={}"

labelsEP = "https://onlyfans.com/api2/v2/users/{}/labels?limit=100&offset={}&order=desc&non-empty=1"
labelledPostsEP = "https://onlyfans.com/api2/v2/users/{}/posts?limit=100&offset={}&order=publish_date_desc&skip_users=all&counters=0&format=infinite&label={}"

listEP = "https://onlyfans.com/api2/v2/lists?offset={}&skip_users=all&limit=100&format=infinite"
listusersEP = (
    "https://onlyfans.com/api2/v2/lists/{}/users?offset={}&limit=100&format=infinite"
)
