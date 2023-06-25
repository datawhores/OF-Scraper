r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import pathlib
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

meEP = 'https://onlyfans.com/api2/v2/users/me'

subscriptionsEP = 'https://onlyfans.com/api2/v2/subscriptions/subscribes?offset={}&type=all&sort=asc&field=expire_date&limit=10'
subscribeCountEP='https://onlyfans.com/api2/v2/subscriptions/count/all'
profileEP = 'https://onlyfans.com/api2/v2/users/{}'

timelineEP = 'https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&pinned=0&format=infinite'
timelineNextEP = 'https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&pinned=0&format=infinite'
timelinePinnedEP = 'https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&pinnedf=1&format=infinite'
timelinePinnedNextEP = 'https://onlyfans.com/api2/v2/users/{}/posts?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&pinned=1&afterPublishTime={}&format=infinite'
archivedEP = 'https://onlyfans.com/api2/v2/users/{}/posts/archived?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&format=infinite'
archivedNextEP = 'https://onlyfans.com/api2/v2/users/{}/posts/archived?limit=100&order=publish_date_asc&skip_users=all&skip_users_dups=1&afterPublishTime={}&format=infinite'

highlightsWithStoriesEP = 'https://onlyfans.com/api2/v2/users/{}/stories/highlights?limit=5&offset=0&unf=1'
highlightsWithAStoryEP = 'https://onlyfans.com/api2/v2/users/{}/stories?unf=1'
storyEP = 'https://onlyfans.com/api2/v2/stories/highlights/{}?unf=1'

messagesEP = 'https://onlyfans.com/api2/v2/chats/{}/messages?limit=100&offset=0&order=desc&skip_users=all&skip_users_dups=1'
messagesNextEP = 'https://onlyfans.com/api2/v2/chats/{}/messages?limit=100&offset=0&id={}&order=desc&skip_users=all&skip_users_dups=1'

favoriteEP = 'https://onlyfans.com/api2/v2/posts/{}/favorites/{}'
postURL = 'https://onlyfans.com/{}/{}'

DYNAMIC = 'https://raw.githubusercontent.com/deviint/onlyfans-dynamic-rules/main/dynamicRules.json'

donateEP = "https://www.buymeacoffee.com/excludedBittern"

purchased_contentEP = "https://onlyfans.com/api2/v2/posts/paid?limit=100&skip_users=all&format=infinite&offset={}&user_id={}"
purchased_contentALL = "https://onlyfans.com/api2/v2/posts/paid?limit=100&skip_users=all&format=infinite&offset={}"

messageSPECIFIC="https://onlyfans.com/my/chats/chat/{}/?firstId={}"
highlightSPECIFIC="https://onlyfans.com/api2/v2/stories/highlights/{}"
storiesSPECIFIC="https://onlyfans.com/api2/v2/stories/{}"
messageSPECIFIC= "https://onlyfans.com/api2/v2/chats/{}/messages?limit=10&order=desc&skip_users=all&firstId={}"

mainPromptChoices = {
    'Download content from a user': 0,
    'Like all of a user\'s posts': 1,
    'Unlike all of a user\'s posts': 2,
    'Edit auth.json file': 3,
    'Edit config.json file': 4,
    'Edit Profile': 5,

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

DIR_FORMAT_DEFAULT="{model_username}/{responsetype}/{mediatype}/"
FILE_FORMAT_DEFAULT="{filename}.{ext}"
METADATA_DEFAULT="{configpath}/{profile}/.data/{model_username}_{model_id}"
FILE_SIZE_DEFAULT=0
TEXTLENGTH_DEFAULT=0
FILTER_DEFAULT=["Images","Audios","Videos"]
SAVE_PATH_DEFAULT=str(pathlib.Path.home()/'Data/ofscraper')
DATE_DEFAULT="MM-DD-YYYY"
PROFILE_DEFAULT="main_profile"
PREMIUM_DEFAULT="Premium"
MP4DECRYPT_DEFAULT=""
FFMPEG_DEFAULT =""
DISCORD_DEFAULT =""
SUPPRESS_LOG_LEVEL=21
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
RESPONSE_EXPIRY=5000000
CHECK_EXPIRY=86400
DAILY_EXPIRY=86400
HOURLY_EXPIRY=3600
DISCORDWAIT=5
OF_MIN=15
OF_MAX=50
LICENCE_URL="https://onlyfans.com/api2/v2/users/media/{}/drm/{}/{}?type=widevine"
logname="ofscraper"
PATH_STR_MAX=200
TABLE_STR_MAX=100

refreshScreen=20

MP4DECRYPT_LINUX="https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-640.x86_64-unknown-linux.zip"
MP4DECRYPT_WINDOWS="https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-640.x86_64-microsoft-win32.zip"
MP4DECRYPT_MAC="https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-640.universal-apple-macosx.zip"
FFMPEG_LINUX="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
FFMPEG_WINDOWS="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_MAC="https://evermeet.cx/ffmpeg/ffmpeg-111111-gc44fe10160.zip"


THREADS_DEFAULT=8
MAX_SEMAPHORE=8
AlT_SEM=4
CODE_EXECUTION_DEFAULT =False

NUMBER_REGEX="[0-9]"
USERNAME_REGEX="[^/]"