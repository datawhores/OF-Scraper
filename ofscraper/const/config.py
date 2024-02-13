import os
import pathlib

SANITIZE_DB_DEFAULT = False
SUPPRESS_LOG_LEVEL = 21
RESUME_DEFAULT = True
CACHEDEFAULT = "sqlite"
KEY_DEFAULT = "cdrm"
DIR_FORMAT_DEFAULT = "{model_username}/{responsetype}/{mediatype}/"
FILE_FORMAT_DEFAULT = "{filename}.{ext}"
METADATA_DEFAULT = "{configpath}/{profile}/.data/{model_username}_{model_id}"
FILE_SIZE_LIMIT_DEFAULT = 0
FILE_SIZE_MIN_DEFAULT = 0
TEXTLENGTH_DEFAULT = 0
SPACE_REPLACER_DEFAULT = " "
FILTER_DEFAULT = ["Images", "Audios", "Videos"]
SAVE_PATH_DEFAULT = str(pathlib.Path.home() / "Data/ofscraper")
DATE_DEFAULT = "MM-DD-YYYY"
PROFILE_DEFAULT = "main_profile"
PREMIUM_DEFAULT = "Premium"
KEYDB_DEFAULT = ""
MP4DECRYPT_DEFAULT = ""
FFMPEG_DEFAULT = ""
DISCORD_DEFAULT = ""
BACKEND_DEFAULT = "aio"
THREADS_DEFAULT = int(os.cpu_count() * (2 / 3))
DOWNLOAD_SEM_DEFAULT = 6
DYNAMIC_DEFAULT = "deviint"
TEXT_TYPE_DEFAULT = "letter"
TRUNCATION_DEFAULT = True
MAX_COUNT_DEFAULT = 0
TEMP_FOLDER_DEFAULT = None
APPEND_DEFAULT = True
RESPONSE_TYPE_DEFAULT = {
    "message": "Messages",
    "timeline": "Posts",
    "archived": "Archived",
    "paid": "Messages",
    "stories": "Stories",
    "highlights": "Stories",
    "profile": "Profile",
    "pinned": "Posts",
}
SYSTEM_FREEMIN_DEFAULT = 0
AVATAR_DEFAULT = True
PROGRESS_DEFAULT = False
KEYDB_DEFAULT = ""
CODE_EXECUTION_DEFAULT = False
INFINITE_LOOP_DEFAULT = False
DISABLE_AFTER_DEFAULT = False
DEFAULT_USER_LIST = "main"
DEFAULT_BLACK_LIST = ""
