r"""
                                                             
        _____                                    ay           
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import pathlib
import os
preferences = 'pref_config.py'
configPath = '.config/ofscraper'
configFile = 'config.json'
authFile = 'auth.json'
databaseFile = 'models.db'
mainProfile = 'main_profile'
requestAuth = 'request_auth.json'
debug = False


# LIST NAMES (IF HARDCODED, MOST WILL BE AUTOMATIC

of_posts_list_name = 'list'

initEP = 'https://onlyfans.com/api2/v2/init'

INDVIDUAL_TIMELINE="https://onlyfans.com/api2/v2/posts/{}?skip_users=all"
meEP = 'https://onlyfans.com/api2/v2/users/me'

subscriptionsEP = 'https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=all&format=infinite'
subscriptionsActiveEP='https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=active&format=infinite'
subscriptionsExpiredEP='https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&limit=10&type=expired&format=infinite'

subscribeCountEP='https://onlyfans.com/api2/v2/subscriptions/count/all'
sortSubscriptions="https://onlyfans.com/api2/v2/lists/following/sort"
profileEP = 'https://onlyfans.com/api2/v2/users/{}'

timelineEP = 'https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&pinned=0&format=infinite'
timelineNextEP = 'https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&pinned=0&format=infinite'

timelinePinnedEP = 'https://onlyfans.com/api2/v2/users/{}/posts?skip_users=all&pinned=1&counters={}&format=infinite'
archivedEP = 'https://onlyfans.com/api2/v2/users/{}/posts/archived?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&format=infinite'
archivedNextEP = 'https://onlyfans.com/api2/v2/users/{}/posts/archived?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&format=infinite'

highlightsWithStoriesEP = 'https://onlyfans.com/api2/v2/users/{}/stories/highlights?limit=5&offset={}&unf=1'
highlightsWithAStoryEP = 'https://onlyfans.com/api2/v2/users/{}/stories?unf=1'
storyEP = 'https://onlyfans.com/api2/v2/stories/highlights/{}?unf=1'


messagesEP = 'https://onlyfans.com/api2/v2/chats/{}/messages?limit=100&offset=0&order=desc&skip_users=all&skip_users_dups=1'
messagesNextEP = 'https://onlyfans.com/api2/v2/chats/{}/messages?limit=100&offset=0&id={}&order=desc&skip_users=all&skip_users_dups=1'

favoriteEP = 'https://onlyfans.com/api2/v2/posts/{}/favorites/{}'
postURL = 'https://onlyfans.com/{}/{}'

DIGITALCRIMINALS = 'https://raw.githubusercontent.com/DIGITALCRIMINALS/dynamic-rules/main/onlyfans.json'

DEVIINT = 'https://raw.githubusercontent.com/deviint/onlyfans-dynamic-rules/main/dynamicRules.json'
donateEP = "https://www.buymeacoffee.com/excludedBittern"

purchased_contentEP = "https://onlyfans.com/api2/v2/posts/paid?limit=100&skip_users=all&format=infinite&offset={}&user_id={}"
purchased_contentALL = "https://onlyfans.com/api2/v2/posts/paid?limit=100&skip_users=all&format=infinite&offset={}"

highlightSPECIFIC="https://onlyfans.com/api2/v2/stories/highlights/{}"
storiesSPECIFIC="https://onlyfans.com/api2/v2/stories/{}"
messageSPECIFIC= "https://onlyfans.com/api2/v2/chats/{}/messages?limit=10&order=desc&skip_users=all&firstId={}"
messageTableSPECIFIC="https://onlyfans.com/my/chats/{}/?id={}"

labelsEP = "https://onlyfans.com/api2/v2/users/{}/labels?limit=100&offset={}&order=desc&non-empty=1"
labelledPostsEP = "https://onlyfans.com/api2/v2/users/{}/posts?limit=100&offset={}&order=publish_date_desc&skip_users=all&counters=0&format=infinite&label={}"

listEP="https://onlyfans.com/api2/v2/lists?offset={}&skip_users=all&limit=100&format=infinite"
listusersEP="https://onlyfans.com/api2/v2/lists/{}/users?offset={}&limit=100&format=infinite"
mainPromptChoices = {
    'Download content from a user': 0,
    'Like all of a user\'s posts': 1,
    'Unlike all of a user\'s posts': 2,
    'Edit auth.json file': 3,
    'Edit config.json file': 4,
    'Edit advanced config.json settings': 5,
    'Edit Profile': 6,

}
usernameOrListChoices = {
    'Select from accounts on profile': 0,
    'Enter a username': 1,
    'Scrape all users that I\'m subscribed to': 2
}
profilesPromptChoices = {
    'Change default profile': 0,
    'Edit a profile name': 1,
    'Create a profile': 2,
    'Delete a profile': 3,
    'View profiles': 4
}

disclaimers = [
'This tool is not affiliated, associated, or partnered with OnlyFans in any way. We are not authorized, endorsed, or sponsored by OnlyFans. All OnlyFans trademarks remain the property of Fenix International Limited.',
  'This tool is for educational purposes only and is not intended for actual use. Should you choose to actually use it you accept all consequences and agree that you are not using it to redistribute content or  for any other action that will cause loss of revenue to creators or platforms scraped.',
  
]
CACHEDEFAULT="sqlite"
KEY_DEFAULT="cdrm2"
DIR_FORMAT_DEFAULT="{model_username}/{responsetype}/{mediatype}/"
FILE_FORMAT_DEFAULT="{filename}.{ext}"
METADATA_DEFAULT="{configpath}/{profile}/.data/{model_username}_{model_id}"
FILE_SIZE_LIMIT_DEFAULT=0
FILE_SIZE_MIN_DEFAULT=0
TEXTLENGTH_DEFAULT=0
FILTER_DEFAULT=["Images","Audios","Videos"]
SAVE_PATH_DEFAULT=str(pathlib.Path.home()/'Data/ofscraper')
DATE_DEFAULT="MM-DD-YYYY"
PROFILE_DEFAULT="main_profile"
PREMIUM_DEFAULT="Premium"
MP4DECRYPT_DEFAULT=""
FFMPEG_DEFAULT =""
DISCORD_DEFAULT =""
BACKEND_DEFAULT ="aio"
THREADS_DEFAULT=int(os.cpu_count()*(2/3))
DOWNLOAD_SEM_DEFAULT=6
DYNAMIC_DEFAULT="deviint"
SUPPRESS_LOG_LEVEL=21
PROGRESS_DEFAULT=False

RESPONSE_TYPE_DEFAULT= {
            "message":"Messages",
            "timeline":"Posts",
            "archived":"Archived",
            "paid":"Messages",
            "stories":"Stories",
            "highlights":"Stories",
            "profile":"Profile",
            "pinned":"Posts"
        }
NUM_TRIES=10
DATABASE_TIMEOUT=300

RESPONSE_EXPIRY=5000000
CHECK_EXPIRY=86400
DAILY_EXPIRY=86400
HOURLY_EXPIRY=3600
SIZE_TIMEOUT=1209600
KEY_EXPIRY=None
DISCORDWAIT=5
OF_MIN=10
OF_MAX=20
LICENCE_URL="https://onlyfans.com/api2/v2/users/media/{}/drm/{}/{}?type=widevine"
logname="ofscraper"
PATH_STR_MAX=200
TABLE_STR_MAX=100

refreshScreen=50

MP4DECRYPT_LINUX="https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-640.x86_64-unknown-linux.zip"
MP4DECRYPT_WINDOWS="https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-640.x86_64-microsoft-win32.zip"
MP4DECRYPT_MAC="https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-640.universal-apple-macosx.zip"
FFMPEG_LINUX="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
FFMPEG_WINDOWS="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_MAC="https://evermeet.cx/ffmpeg/ffmpeg-111111-gc44fe10160.zip"


MAX_SEMAPHORE=14
MAXFILE_SEMAPHORE=0
AlT_SEM=4
CODE_EXECUTION_DEFAULT =False

NUMBER_REGEX="[0-9]"
USERNAME_REGEX="[^/]"

API_REQUEST_TIMEOUT=90
SUPRESS_OUTPUTS={"CRITICAL","ERROR","WARNING","OFF","LOW","PROMPT"}
CHUNK_ITER=10
maxChunkSize=1024*1024*10
maxChunkSizeB=1024*1024
KEY_OPTIONS=["cdrm","cdrm2","manual","keydb"]

OFSCRAPER_RESERVED_LIST="ofscraper.main"
OFSCRAPER_ACTIVE_LIST="ofscraper.active"
OFSCRAPER_EXPIRED_LIST="ofscraper.expired"


MULTIPROCESS_MIN=200
DBINTERVAL=259200
LARGEZIP="https://proof.ovh.net/files/100Mb.dat"

CDRM2='http://172.106.17.134:8080/wv'
KEYDB='https://keysdb.net/api'
CDRM='https://cdrm-project.com/wv'