"""Descriptions the code doesn't carry, for scripts/reference/build_reference.py.

Every key here must name something that exists, and the things listed in
test/test_reference.py must all have an entry. Keep each description to a few
plain sentences: what it does and how it interacts with other settings.
Defaults, types and names are generated; don't repeat them.

Style:
- Present tense, active voice, one idea per sentence.
- Say "falls back to" when a missing or invalid value is replaced by another.
- Say "The `-x`/`--long-name` option overrides it for one run" for a command-line override.
- Put code names (options, keys, functions, files) in backticks.
"""

# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------

# extra notes for options, keyed by the option's dest (the name in the args)
CLI = {
    "redownload": "Sets `force_all`, `--after 2000` and `--before` tomorrow for the run. Every item is scanned and downloaded again. The merge happens in `merged_settings`.",
    "text_only": "Also turns on `--text`. Text files are written and media is skipped.",
    "original": "Turns off file name truncation for the run, whatever `file_options.truncation_default` says.",
    "no_auto_resume": "Turns `download_options.auto_resume` off for the run.",
    "no_cache": "Disables both the general cache and the API cache for the run, and turns off incremental downloads. Setting `advanced_options.cache-mode` to `disabled` in `config.json` does the same.",
    "no_api_cache": "Disables only the API response cache. Setting `advanced_options.cache-mode` to `api_disabled` does the same.",
    "download_limit": "Values below 1024 bytes per second are raised to 1024. All downloads in the run share the limit.",
    "key_mode": "`cdrm` posts the request headers, cookies included, to cdrm-project.com. `manual` uses the local CDM files (`--private-key`, `--client-id`).",
    "quality": "The lowest video quality to accept. The smallest available quality at or above it is downloaded, or `source` when none matches (`ofscraper/utils/args/accessors/quality.py`, `classes/of/media.py`). Without this option, `source` is used.",
    "env_files": "Loaded before settings are built. It replaces `advanced_options.env_files` instead of adding to it.",
    "output_level": "`LOW` and `PROMPT` hide status lines and the live progress screen. Errors and prompts still show. `LOW` also shows warnings; `PROMPT` shows only errors.",
    "retry_permanent_skips": "The files `skip_download_script` skipped for good (`medias.skip_permanent = 1`) are no longer treated as downloaded for the run, so the creators' files in the run are offered to the script again. Areas are scanned in full unless `--after` is given, since those files can be in older posts. A file the script keeps downloads. `skip-permanent` keeps it skipped for good. A plain skip counts as skipped and sets it back to not downloaded, so the next run asks again. Without a script set, nothing skips them, so they download. Real downloads and other rows don't change.",
    "unmark_permanent_skips": "`ofscraper db` only. Of the rows the other options select (creator, `--post-id`, `--media-id` and the media filters), it keeps those `skip_download_script` skipped for good, prints them, and sets them back to not downloaded with `skip_permanent` cleared. The next normal run asks the script about them again. A media's download state is kept on all of its rows, so its rows in other posts change too. Other rows never change. Without it, `db` only reads.",
}

# --------------------------------------------------------------------------
# environment defaults
# --------------------------------------------------------------------------

ENV_INTRO = """
These are the built-in defaults the app reads with `of_env.getattr(KEY)` (`ofscraper/utils/of_env/of_env.py`). They are loaded once from the files in `ofscraper/utils/of_env/values/` and cached.

Two kinds of environment variable override a default:

- The listed `OFSC_*` variable. It is read once, when the defaults load.
- A variable named after the bare key, for example `DATABASE_TIMEOUT`. It is read on every lookup and converted to the default's type.

Before the app reads either kind, it loads these into the environment. Each one overrides variables that are already set (`ofscraper/utils/of_env/load.py`):

1. A `.env` file found by python-dotenv. It searches upward from `ofscraper/utils/of_env/`. It searches from the working folder only in the standalone binaries, the REPL or a debugger.
2. The env files named in `advanced_options.env_files`.

The values shown are the defaults with no environment variables set. Paths under your home directory appear as `{home_directory}`. Each description comes from the comment above the value in the source, where there is one.
"""

ENV_SLEEPER = """
Requests back off when they get rate-limit errors (429, 503, 504) or 403 errors. The logic is in `ofscraper/managers/sessionmanager/sleepers.py` and in `SessionSleep` in `sessionmanager.py`.

Each kind of request has its own set of values. Rate limits use `<KIND>_SESSION_*` and 403s use `<KIND>_SESSION_403_*`. The standard API uses `SESSION_*`.

How the wait changes:
- The wait starts at `*_MIN_SLEEP`.
- On the first error, if `*_MIN_SLEEP` is 0, the wait becomes `*_SLEEP_INIT` seconds (or 1 if that is 0). Otherwise the first error already multiplies the wait.
- Each error multiplies the wait by `*_SLEEP_INCREASE_FACTOR`, up to `*_SLEEP_MAX`. This happens only if `*_SLEEP_INCREASE_TIME_DIFF` seconds have passed since the last change, since the program started, or since the last per-creator reset.
- After `*_SLEEP_DECAY_THRESHOLD` seconds without a change, the wait is divided by `*_SLEEP_DECAY_FACTOR`, down to `*_MIN_SLEEP`. If the result would drop below 0.5 seconds, the wait goes straight to `*_MIN_SLEEP` and the backoff ends.

How the waits combine:
- `*_MIN_SLEEP` is also the minimum gap kept between requests.
- Before each request, the rate-limit wait runs first. The 403 backoff runs next, if one is active.
- The 403 `*_MIN_SLEEP` gap is kept only when the rate-limit `*_MIN_SLEEP` is 0 and no rate-limit backoff is active.

Only the standard API session (`SESSION_403_*`) backs off on a 403. Downloads, CDM, likes, metadata, Discord and subscriptions never start a 403 backoff, because a 403 there is usually an expired link. Their `<KIND>_SESSION_403_*` values therefore have no effect. The one exception is `<KIND>_SESSION_403_MIN_SLEEP`, which is still kept as a gap under the rule above.
"""

# env.md section titles, one per file in ofscraper/utils/of_env/values/
# (path relative to that folder). The page lists sections in this order.
ENV_FILES = {
    "action/download.py": "Downloads",
    "action/like.py": "Likes",
    "action/metadata.py": "Metadata",
    "req/req.py": "Connections, proxies and concurrency",
    "req/ratelimit.py": "Rate-limit values per request type",
    "req/api.py": "API limits and retries",
    "req/mpd.py": "DRM manifests (MPD)",
    "req/cdm.py": "CDM",
    "req/auth.py": "Authentication",
    "req/anon.py": "Anonymous requests",
    "req/discord.py": "Discord",
    "req/git.py": "Dynamic rule downloads",
    "general.py": "Output and file handling",
    "main.py": "General defaults",
    "date.py": "Dates",
    "time.py": "Expiry and timeouts",
    "dynamic.py": "Dynamic rules",
    "list.py": "List names",
    "live.py": "Progress display",
    "logger.py": "Logging",
    "system.py": "Subprocess log levels and free-space check",
    "prompts.py": "Menu choices",
    "path/files.py": "File paths",
    "path/general.py": "Filename generation and temp files",
    "path/length.py": "Name and path lengths",
    "path/bytes.py": "Character sizes",
    "url/url.py": "OnlyFans API addresses",
    "url/dynamic.py": "Dynamic rule addresses",
    "url/other_url.py": "Other addresses",
}

# Subsection titles taken from the source comments that read badly as headings.
# Anything not listed has a trailing " Configuration" removed.
ENV_SECTION_TITLES = {
    "Format String Defaults (These are often user-configurable, but have internal defaults)": "Format strings",
    "Complex Defaults (Better as Python Constants, not environment variables)": "Fixed values",
    "Force Key Configuration (Booleans)": "Forced keys",
    "Miscellaneous": "Other",
    "Proxy Configuration": "Proxies",
    "General Paths Configuration": "Temporary files",
    "General Application Defaults": "Application",
}

# options merged_settings reads but that don't actually override the config
# value, so they aren't listed as overrides or fallbacks
NOT_MERGED = {"env_files"}

# descriptions for keys whose source has no comment naming them
ENV = {
    "ALT_FORCE_KEY": "When on, the `metadata` command fetches a fresh DRM key for protected (MPD) media instead of reusing one (`commands/metadata/manager.py`).",
    "KEY_OPTIONS": "The allowed `cdm_options.key-mode-default` values, taken from `ofscraper/utils/const.py`. Not read from the environment.",
    "SSL_VALIDATION_DEFAULT": "The default for `advanced_options.ssl_verify`, used when the config has no usable value.",
    "mainPromptChoices": "Menu entries of the interactive main menu. Not read from the environment.",
    "configPromptChoices": "Menu entries of the interactive config editor. Not read from the environment.",
    "actionPromptChoices": "Menu entries for picking actions interactively. Not read from the environment.",
    "usernameOrListChoices": "Menu entries for picking creators interactively. Not read from the environment.",
    "profilesPromptChoices": "Menu entries of the interactive profile menu. Not read from the environment.",
    "modelPrompt": "Menu entries for filtering and sorting the creator list interactively. Not read from the environment.",
    "LOG_SUBPROCESS_LEVEL": "Log level for subprocess output that has no more specific setting. `OFSC_LOG_SUBPROCESS_LEVELL` is the old misspelled name, and it is still read.",
    "MPD_SESSION_SLEEP_INIT": "Defined but not read anywhere. MPD requests use the standard `SESSION_*` values.",
    "DISK_SPACE_CHECK_PATH": "The path whose disk free space is compared with `download_options.system_free_min` (`ofscraper/utils/system/free.py`). It is not the save location unless you set it to be.",
}

# the four SUPRESS_*_DISPLAY switches have no default to take a type from
_SUPRESS = "Hides the {what} display when on. The value is read as on/off: `true` or `1` (any case) is on, and anything else is off, which shows the display. This holds for the bare name too, which has no default to take a type from. It applies only while that screen is up. Unset, the display follows `--output` and `--no-rich`."
ENV.update({
    "SUPRESS_API_DISPLAY": _SUPRESS.format(what="API progress"),
    "SUPRESS_DOWNLOAD_DISPLAY": _SUPRESS.format(what="download progress"),
    "SUPRESS_SUBSCRIPTION_DISPLAY": _SUPRESS.format(what="subscription progress"),
    "SUPRESS_LIKE_DISPLAY": _SUPRESS.format(what="like progress"),
})

# variables read with os.getenv outside ofscraper/utils/of_env/values
ENV_DIRECT = {
    "DISPLAY": "Check table, Linux only: with neither this nor `WAYLAND_DISPLAY` set there's no desktop, so Open Download Folder and `o` show the folder's path instead of running `xdg-open`.",
    "WAYLAND_DISPLAY": "Check table, Linux only: see `DISPLAY`.",
    "OFSC_FANSLY_API_BASE": "Base URL of the Fansly API that Fansly requests go to.",
    "OFSC_FANSLY_AUTH_FILE_NAME": "Name of the Fansly credentials file in the profile folder.",
    "STASH_API_KEY": "`stash_sync` only: the Stash API key, for a Stash with a password. `--api-key` overrides it.",
    "STASH_URL": "`stash_sync` only: Stash's GraphQL URL. `--url` overrides it.",
}

# (regular expression for the key, description); the first match is used
ENV_PATTERNS = [
    (r"[A-Z_]*SESSION(_403)?_SLEEP_INIT", "The wait the first error of this kind sets when `*_MIN_SLEEP` is 0 (0 means 1 second). Not used when `*_MIN_SLEEP` is above 0."),
    (r"[A-Z_]*SESSION(_403)?_SLEEP_INCREASE_TIME_DIFF", "Seconds that must pass since the last change before another error raises the wait."),
    (r"[A-Z_]*SESSION(_403)?_SLEEP_MAX", "The longest backoff wait, in seconds."),
    (r"[A-Z_]*SESSION(_403)?_SLEEP_INCREASE_FACTOR", "Each further error multiplies the wait by this."),
    (r"[A-Z_]*SESSION(_403)?_SLEEP_DECAY_THRESHOLD", "Seconds without a change after which the wait shrinks."),
    (r"[A-Z_]*SESSION(_403)?_SLEEP_DECAY_FACTOR", "The wait is divided by this when it shrinks."),
    (r"[A-Z_]*SESSION(_403)?_MIN_SLEEP", "The smallest wait, and the minimum gap kept between requests, in seconds. The wait starts here."),
    (r"[A-Z_]+_SUBPROCESS_LEVEL", "Log level for the output of this subprocess (the user script, ffmpeg or ffprobe named in the key). 0 turns that output off."),
]

# --------------------------------------------------------------------------
# output templates
# --------------------------------------------------------------------------

PLACEHOLDER_INTRO = """
These are the names you can use in braces in the `file_options.dir_format`, `file_options.file_format` and `metadata` templates, and in text file names (`ofscraper/classes/placeholder.py`). Each column says which template gets the name.

Templates are filled with Python's `str.format`, so object values allow attribute or key access. Examples are `{modelObj.name}` and `{args.posts}`. Because `config` is a plain dict, `{config[file_options][date]}` also works.

- Profile media (avatar, header) ignore `file_format`. They are saved as `<file_name>.<ext>`.
- When `FILE_COUNT_PLACEHOLDER` is on (the default) and `file_format` uses none of `filename`, `only_file_name`, `original_filename` or `media_id`, `_<count>` is added before the extension. This applies to a post with several media, and to a story or highlight.
- On Fansly, if the `metadata` template uses none of `save_location`, `root`, `site_name` or `model_id` (or their aliases), the site name is added as a subfolder. This keeps Fansly rows out of an OnlyFans `user_data.db`.
- The validators in `ofscraper/prompts/prompt_validators.py` are not called anywhere. They accept only some of these names.
"""

PLACEHOLDERS = {
    "config_path": "The config home folder, from `common_paths.get_config_home()` (for example `{home_directory}/.config/ofscraper`). It is usually written `{configpath}`, and the default `metadata` path uses it that way.",
    "profile": "The name of the active profile, for example `main_profile`.",
    "site_name": "The name of the site being scraped, from `sites.site_name()`. On Fansly runs this is the Fansly name. It is usually written `{sitename}`.",
    "save_location": "The configured save location. On Fansly runs it is `<save location>/Fansly`. It has the same value as `{root}`, but as the configured string.",
    "my_id": "The numeric id of the logged-in account. It is `anon` in anonymous mode.",
    "my_username": "The username of the logged-in account. It is `anon` in anonymous mode.",
    "root": "A `pathlib.Path` of `{save_location}`: the media root, with the Fansly subfolder included.",
    "username": "The creator's username. In `dir_format`, `file_format` and text files it is also the underscore-free alias of `{user_name}`, with the same value.",
    "model_username": "The creator's username. The media and post objects lower-case it for dir and file names.",
    "model_id": "The creator's numeric account id. OnlyFans ids are short, and Fansly ids are 18-digit snowflakes. The default `metadata` path is `{configpath}/{profile}/.data/{model_id}`.",
    "first_letter": "The first letter of the creator's username, upper-cased, for example `A`.",
    "user_name": "The creator's username, the same as `{model_username}`. Its alias `{username}` also works.",
    "post_id": "The id of the post or message the media belongs to. For text files, it is the post's own id.",
    "media_id": "The id of the media item. Including it (or a filename field) in `file_format` stops the automatic `_<count>` suffix.",
    "media_type": "The capitalised media kind: `Images`, `Videos` (gifs count as `Videos`), `Audios`, `Forced_skipped`, or `Text` for text files. It is usually written `{mediatype}`.",
    "value": "`Free` or `Paid`, from the post's price. A price of 0 means `Free`.",
    "date": "The post's date (`postedAt`, else `createdAt`), formatted with the `file_options.date` config value (arrow tokens, default `MM-DD-YYYY`).",
    "response_type": "The display name of the content area, from the `responsetype` config map. The defaults are Posts, Messages, Archived, Stories, Profile and Streams. Timeline and pinned map to Posts, paid maps to Messages, and highlights map to Stories. Archived posts use the configured Archived name. It is usually written `{responsetype}`.",
    "label": "The post's label name (on Fansly, the wall name), or the string `None` when it has no label. Only posts found through the Labels area carry one. Files go into a folder per label only when `dir_format` uses `{label}`. With the default `dir_format`, labelled posts are saved with the timeline and the labels are recorded only in the `labels` table. A post in both the timeline and a label is downloaded once; with `{label}` in `dir_format`, its folder depends on which area returned it first. A file that an earlier run already downloaded (for example from the timeline) stays where it is: it isn't moved, or downloaded again, into the label folder (unless `--force-all` re-downloads it).",
    "download_type": "`Protected` for DRM (MPD) media, `Normal` otherwise.",
    "modelObj": "An object: the creator's model (`ofscraper/classes/of/models.py`) from the model manager. Use attribute access, for example `{modelObj.name}`, `{modelObj.id}` or `{modelObj.final_current_price}`. It is `None` if the creator isn't loaded, so attribute access then fails.",
    "quality": "The selected video quality, such as `1080`, `720`, `240` or `source`. Non-videos and text files are `source` (`QUALITY_UNKNOWN_DEFAULT` when the quality is unknown).",
    "file_name": "The final media file name without the extension. It is the name from the media URL, or the media id if there is none. Videos get `_<quality>` appended. The name is cleaned and spaces are replaced by `space_replacer`. For text files it is the sanitised, truncated post text. It is usually written `{filename}`, and the default `file_format` is `{filename}.{ext}`.",
    "original_filename": "The file name taken from the media URL (the raw media filename, `None` when the media has no URL). For text files it is the sanitised post text.",
    "only_file_name": "Like `{file_name}`, but without the video quality suffix. For text files it is the sanitised post text.",
    "only_filename": "The same value as `{only_file_name}`.",
    "text": "For media: the post text, cleaned and truncated to `textlength`. It falls back to the file name, the date, or the media id. For text files: the sanitised, truncated post text.",
    "config": "An object: the parsed `config.json` as a dict. Use item syntax, for example `{config[file_options][date]}`. Attribute access does not work.",
    "args": "An object: the parsed command-line arguments (an `AutoDotDict`). Use attribute access, for example `{args.posts}`. A missing name gives `None`.",
    "ext": "The file extension without the dot, for example `mp4` or `jpg`. It is `txt` for text files.",
    "current_price": "`Free` if the creator's final current price is 0, else `Paid`. It is `MODEL_PRICE_PLACEHOLDER` (`Unknown_Price` by default) when the model isn't loaded.",
    "regular_price": "`Free` or `Paid`, from the creator's final regular price, or `MODEL_PRICE_PLACEHOLDER`.",
    "promo_price": "`Free` or `Paid`, from the creator's final promo price, or `MODEL_PRICE_PLACEHOLDER`.",
    "renewal_price": "`Free` or `Paid`, from the creator's final renewal price, or `MODEL_PRICE_PLACEHOLDER`.",
}

ACTIONS = {
    "download": "Scrapes the selected areas (`--posts`) for each selected creator. It downloads the media that pass the filters into `save_location`, using `dir_format` and `file_format`, and records them in the creator's `user_data.db`. With `--text` (or `--text-only`) it also writes post text to `.txt` files. It runs `downloader()` in `commands/scraper/actions/download`, then the after-download action script.",
    "like": "Likes (favorites) posts in the selected like areas that aren't liked yet. It sends one request at a time, with a random sleep between requests (`MIN/MAX_SLEEP_DURATION_LIKE`). A post that toggles the wrong way is toggled again. It runs `like.process_like`, then the after-like action script. The code warns that OnlyFans allows about 1000 likes per hour.",
    "unlike": "Removes likes from already-liked posts in the selected like areas, the same way as `like`. It runs `like.process_unlike`. It can't be combined with `like`.",
}

COMMANDS = {
    "(main)": "Runs when no subcommand is given. The entry point is `ofscraper/__main__.py`. Then `Manager.pick()` calls `commands/scraper/scraper.main()`, which cleans temp files and the database and checks the CDM. After that, the run goes one of these ways:\n\n- With `--daemon`, it prompts for actions if none were given, then reruns on a schedule.\n- With `--action` or `--scrape-paid`, it runs those actions once. It repeats with prompts if the infinite-loop config is on.\n- With only Fansly `--live` or `--live-watch`, it records livestreams.\n- Otherwise it opens the interactive menu: Action, Auth (edit `auth.json`), Config (edit `config.json`), Profile, Merge databases and Quit.\n\nThe run reads `auth.json` and `config.json` from the profile. It writes media under `save_location` and rows to each creator's `user_data.db`.",
    "manual": "`ofscraper manual -u URL...` or `-f FILE` (one is required). Downloads specific posts, given as OnlyFans URLs (post, chat message, story, highlight) or bare post ids. A bare id is looked up on the timeline, then in that creator's purchases. It forces `force_all`, so existing files are downloaded again. It writes posts and media to the creator's `user_data.db` and media under `save_location`, then runs the after-download script.",
    "msg_check": "`ofscraper msg_check -u ITEM...` or `-f FILE`. Each item is a creator username, a model id, or a chat URL (`onlyfans.com/my/chats/chat/<id>` or `onlyfans.com/my/chats/<id>/?id=<message id>`), whose number is taken as the model id. Any other item is skipped with a warning. It fetches the creator's messages and purchases, writes them to `user_data.db`, and opens an interactive table of the media. Unlocked rows in the table can be queued for download, and a background thread downloads them. The messages and purchases come from the check cache unless you pass `--force`. The cache expires after 3 days.",
    "story_check": "`ofscraper story_check -u USERNAME...` (or `-f`). Fetches the creators' stories and highlights from the API, without the check cache. It writes them to `user_data.db` and opens the same downloadable media table.",
    "paid_check": "`ofscraper paid_check -u USERNAME_OR_ID...` (or `-f`). Fetches each creator's purchased content, writes it to `user_data.db` and opens the media table. The content comes from the check cache unless you pass `--force`. A deleted creator, named `DELETED_MODEL_PLACEHOLDER`, is read from all purchases.",
    "post_check": "`ofscraper post_check -u URL_OR_USERNAME...` or `-f FILE`. Takes `onlyfans.com/<username>` URLs or bare usernames. It fetches the areas in `--check-area` (default Timeline, Pinned, Archived and Streams; Labels is also available), writes them to `user_data.db` and opens the media table. The areas come from the check cache unless you pass `--force`. All check commands set `force_all` and `after=0`.",
    "metadata": "`ofscraper metadata --metadata check|update|complete`, with the usual user and area options (`--scrape-paid` takes a mode too). It uses the API to update the creators' `user_data.db` without downloading. The modes differ as follows:\n\n- `check` refreshes metadata fields only.\n- `update` also sets download status and file names from the files actually on disk.\n- `complete` marks media downloaded and takes a new filename if there is one.\n\n`--mark-stray` marks database media that are missing from the scrape (within `--after` and `--before`) as locked. `--anon` uses anonymous credentials.",
    "db": "`ofscraper db`, with user selection, area (`-o`) and media filters (type, size, length, downloaded, locked, preview, protected, post and media ids, dates), sorting and a hard limit. `--post-id` and `--media-id` take one id, or several separated by commas or spaces. An id is decimal digits, from any script. A value with no id in it, or with anything else (such as `²` or `-4`), is a usage error. It reads media rows from each selected creator's `user_data.db` and prints them as a table. `-ep`/`--export PATH` also writes a `.csv`. It makes no API calls for the media itself. With several creators, every selected creator's rows go into the one CSV. `--unmark-permanent-skips` narrows the rows to the permanent `skip_download_script` skips and sets them back to not downloaded after printing them.",
    "recover_collisions": "`python -m ofscraper.commands.recover_collisions DB [--apply] [--undo FILE] [--path-root DIR]`. It uses argparse and is not part of the CLI (see `COLLISION_RECOVERY.md`). It works offline on one creator's `user_data.db` and finds recorded paths that different media share. It prints a JSON report. `--apply` resets `downloaded=0` for those media and writes a JSON undo file beside the database. `--undo FILE` previews the restore of those flags, or with `--apply` performs it. It never touches media files and doesn't contact OnlyFans.",
    "stash_sync": "`python -m ofscraper.commands.stash_sync PATH... [--apply] [--scan] [--path-map LOCAL=STASH]`. It uses argparse and is not part of the CLI (see `STASH.md`). It reads creators' `user_data.db` files offline (a folder such as `<profile>/.data` is searched for them) and, over Stash's GraphQL API, fills empty fields of each downloaded file's scene or image: performer, studio, date, title, details, code, URL and source tags. A Fansly database (`schema_flags` `site=fansly`) gets the `Fansly` studio and links, @mentioned creators as performers, the media ID as code, a preview tag, hashtags as tags, and a gallery per post or message. It never overwrites a value already in Stash, and without `--apply` it only prints a JSON report. It doesn't contact OnlyFans or Fansly.",
    "scripts/creator_names.py": "`python scripts/creator_names.py [--all | --find NAME | --add MODEL_ID NAME [--force] | --csv FILE] [--data-dir DIR]`. Lists the usernames each creator account has had, from the `profiles` table of every `<data-dir>/<model_id>/user_data.db` (default: the main profile's `.data` folder). `--add` appends a name. It works on OnlyFans databases only.",
    "scripts/commit_version.sh": "CI helper. Works out the commit-based version string, hashes and push type from git for the build workflows.",
    "scripts/determine_docker_stable_dev_tags.py": "CI helper. Asks the GitHub API for commit timestamps to decide the stable and dev Docker image tags.",
    "scripts/retry_action.sh": "CI helper. Retries a command up to N times, with a sleep between attempts.",
    "scripts/entry/": "Docker internals. `entrypoint.sh`, `lib_user_setup.sh`, `lib_paths.sh` and `lib_permissions.sh` set up the container user, the data and config paths and the permissions, then start the app.",
}

# --------------------------------------------------------------------------
# config.json
# --------------------------------------------------------------------------

CONFIG_SECTIONS = {
    "responsetype": "These values are the folder names that fill `{responsetype}` in `dir_format`. For each post, the app lowercases the post's own type, looks it up here, and capitalises the result with `str.capitalize()` (`Post.modified_responsetype` in `ofscraper/classes/of/posts.py`). Only the first letter stays uppercase. An empty or missing entry falls back to the type's own name. Archived posts always use `responsetype.archived`.",
}

_RESPONSETYPE_TAIL = "The value is capitalised, so only its first letter stays uppercase. An empty value falls back to the type name."

CONFIG = {
    "main_profile": "The name of the profile folder in the config directory. The folder holds `auth.json`, the cache and (by default) the per-creator databases. The name also appears in log file names. The `--profile` option overrides it for one run.",
    "metadata": "The folder pattern for each creator's `user_data.db`. It uses placeholders such as `{configpath}`, `{profile}`, `{model_id}` and `{model_username}`. On Fansly runs a site subfolder is appended unless the pattern already contains a site-specific placeholder, so the two sites never share a database.",
    "discord": "The Discord webhook URL that log messages are posted to. Nothing is sent unless the run's Discord log level is raised with `-dc`/`--discord` set to `LOW` or `NORMAL`. The option defaults to `OFF`.",
    "file_options.save_location": "The root folder for downloads. `dir_format` is resolved under it. It is also the temp-file root when `temp_dir` is unset. Fansly runs save to a `Fansly` subfolder of it. Surrounding quotes from the Windows \"Copy as path\" command are stripped.",
    "file_options.dir_format": "The folder pattern for each downloaded file, relative to `save_location`. It is built from placeholders such as `{model_username}`, `{responsetype}` and `{mediatype}`. It is ignored for a file when `naming_script` returns a path.",
    "file_options.file_format": "The file name pattern for each download. It is built from placeholders such as `{filename}`, `{ext}`, `{date}`, `{text}` and `{media_id}`. It is ignored for a file when `naming_script` returns a path.",
    "file_options.textlength": "The maximum length of post text used in names (the `{text}` placeholder and text-based file names). It is counted in letters or words, according to `text_type_default`. 0 means no limit. The `-tl`/`--textlength` option overrides it.",
    "file_options.space_replacer": "The character that replaces spaces in post text used for file and folder names. In word mode it also serves as the word separator. An empty value falls back to a space. The `-sr`/`--space-replacer` option overrides it.",
    "file_options.date": "An arrow date-format string (for example `MM-DD-YYYY`). It formats the `{date}` placeholder in `dir_format`, `file_format` and naming-script payloads.",
    "file_options.text_type_default": "Whether `textlength` counts `letter`s or `word`s. Any other value falls back to the default. The `-tt`/`--text-type` option overrides it.",
    "file_options.truncation_default": "When true, final file paths longer than the operating system's limit are shortened to fit. The `-g`/`--original` flag turns truncation off for one run.",
    "file_options.filename_collision": "What happens when a download's target path already holds a different file. `overwrite` keeps the old behaviour: the larger file wins. Any other value saves the new file as `name_<media_id>`, then `name_<media_id>_2` and so on. An existing file with identical content is kept.",
    "download_options.filter": "The media types to process: a list or comma-separated string of Images, Audios and Videos (case-insensitive). An empty list processes all types. The `-mt`/`--mediatype` option overrides it.",
    "download_options.auto_resume": "When true, a leftover `.part` file is resumed with an HTTP range request. When false, partial files are deleted and downloads restart. The `-ar`/`--no-auto-resume` flag forces it off for one run.",
    "download_options.system_free_min": "The minimum free disk space. Once free space drops below it, scraping of further post areas stops with the message \"Space min has been reached\". It accepts bytes or a size string such as `10GB`. 0 disables the check. Space is measured on `OFSC_DISK_SPACE_CHECK_PATH` (default `/`), not on `save_location`. There is no CLI option for it.",
    "download_options.max_post_count": "The most media items (not posts) to download or process per creator, after all other filters. 0 means no cap. The `-xc`/`--max-post-count` and `-mxc`/`--max-media-count` options both override it, and they set the same value.",
    "download_options.verify_all_integrity": "When true, `ffprobe` checks ordinary (non-DRM) video and audio downloads and Fansly streams against the expected duration. A truncated file is deleted and reported as failed. It requires `ffprobe`. There is no CLI option for it.",
    "binary_options.ffmpeg": "The path to the ffmpeg executable. It is needed for DRM decryption and merging and for Fansly streams (version 6 or newer for DRM). If the path is empty or invalid, the app tries `OFSC_FFMPEG_DEFAULT`, then the pyffmpeg bundle, then `PATH`. Surrounding quotes are stripped.",
    "cdm_options.private-key": "The path to the Widevine CDM private key file (`private_key.pem`). It is read when key-mode is `manual`. The `-pk`/`--private-key` option overrides it. Surrounding quotes are stripped.",
    "cdm_options.client-id": "The path to the Widevine CDM client ID blob (`client_id.bin`). It is read when key-mode is `manual`. The `-ci`/`--client-id` option overrides it. Surrounding quotes are stripped.",
    "cdm_options.key-mode-default": "How DRM content keys are obtained. `manual` uses the local CDM files in `private-key` and `client-id`. `cdrm` asks cdrm-project.com and sends it the request headers, cookies included. Other values fall back to the default. The `-k`/`--key-mode` option overrides it.",
    "performance_options.download_sems": "The number of downloads that run at the same time. The worker thread pool is twice this size. It must be at least 1, and 0 or a negative number falls back to the default. The `--sem`/`-sd` option overrides it.",
    "performance_options.download_limit": "The maximum download speed in bytes per second, shared across downloads. It accepts a size string such as `10MB`. 0 means unlimited, and any non-zero value below 1024 is raised to 1024. The `-dl`/`--download-limit` option overrides it.",
    "content_filter_options.block_ads": "When true, posts whose text matches a built-in advertising regex (#ad, giveaway, shoutout, promo and similar) are excluded. This is added on top of any `--neg-filter` patterns. The `-ba`/`--block-ads` flag turns it on for one run.",
    "content_filter_options.file_size_max": "Media larger than this are skipped at download time. The `db` command and the table view also apply it. It accepts bytes or a size string such as `500MB`. 0 means no limit, and an unparseable value is treated as 0. The `-sx`/`--size-max` option overrides it.",
    "content_filter_options.file_size_min": "Media smaller than this are skipped at download time. The `db` command and the table view also apply it. It accepts bytes or a size string. 0 means no limit, and an unparseable value is treated as 0. The `-sm`/`--size-min` option overrides it.",
    "content_filter_options.length_max": "The maximum duration in seconds. Longer videos are filtered out. Only videos with a known duration are affected, not audio or images. 0 means no limit. The `-lx`/`--length-max` option overrides it.",
    "content_filter_options.length_min": "The minimum duration in seconds. Shorter videos are filtered out. Only videos with a known duration are affected, not audio or images. 0 means no limit. The `-lm`/`--length-min` option overrides it.",
    "advanced_options.dynamic-mode-default": "Which source of OnlyFans request-signing rules to use. The values are `datawhores`, `xagler`, `rafa`, `digitalcriminals` (aliases `dc`, `digital`, `digitals`, `digitalcriminal`; the config menu lists and saves it as `digital`), `generic` (needs `OFSC_DYNAMIC_GENERIC_URL`) and `manual` (needs `OFSC_DYNAMIC_RULE_MANUAL`). An unknown value falls back to the default and logs a warning. Anything that yields no rule falls back to `datawhores`. The `-dr`/`--dynamic-rules` option overrides it.",
    "advanced_options.skip_unavailable_content": "When true, timeline, pinned, archived, stories and highlights are not scraped for creators whose subscription has expired. Profile, purchased content and messages are still scraped. Labels and streams are scraped only for active subscriptions, whatever this setting says.",
    "advanced_options.downloadbars": "When true, the app shows a progress bar for each file being downloaded, in addition to the overall progress. The `-db`/`--downloadbars` flag can turn it on but not off.",
    "advanced_options.cache-mode": "The storage backend for the on-disk cache. `sqlite` stores pickled values in the `cache_sql` folder. `json` stores JSON values in the `cache_json` folder. `disabled` turns off the cache, the API cache and incremental downloads, like `--no-cache`. `api_disabled` turns off only the API response cache, like `--no-api-cache`, and keeps sqlite storage. Other values fall back to the default.",
    "advanced_options.rotate_logs": "When true, each run writes its own log file in a per-day folder under the logging directory. When false, all runs of a day append to one file. It must be true for `logs_expire_time` to delete old logs.",
    "advanced_options.sanitize_text": "When true, post and message text is stored in the database with HTML tags removed and whitespace collapsed. When false, the raw API text is stored. It does not affect file names.",
    "advanced_options.temp_dir": "The root folder for in-progress (`.part`) downloads. It is laid out with `dir_format`, like the final location. When unset, temp files are written under `save_location`. Surrounding quotes are stripped.",
    "advanced_options.remove_hash_match": "`true` hashes every download and deletes later files whose hash matches an earlier one for the same creator and media type. `false` only records hashes. `null` skips hashing.",
    "advanced_options.infinite_loop_action_mode": "When true, action mode (`--action`) asks after each run whether to continue, and offers another action instead of exiting.",
    "advanced_options.incremental_downloads": "When true and no `--after` is given, each area is scanned only from the newest previously scanned post, instead of from the start. Like and unlike actions and forced full scans still scan everything. `--no-cache` or cache-mode `disabled` turns it off for the run. The legacy key `advanced_options.enable_auto_after` is read when this key is missing.",
    "advanced_options.default_user_list": "The OnlyFans user lists to select creators from when `-ul`/`--user-list` is not given. It is a list or a comma-separated string. The reserved names `ofscraper.main`, `ofscraper.active` and `ofscraper.expired` mean all, active and expired subscriptions. Names are matched case-insensitively.",
    "advanced_options.default_black_list": "The OnlyFans user lists whose members are excluded from selection when `-bl`/`--black-list` is not given. It is a list or a comma-separated string. Names are matched case-insensitively.",
    "advanced_options.logs_expire_time": "The age in hours after which `.log` files in the logging directory are deleted at cleanup, along with empty log folders. 0 disables it. Nothing is deleted unless `rotate_logs` is true.",
    "advanced_options.ssl_verify": "The TLS mode for HTTP sessions. `false` (also `0`, `none` or empty) turns certificate verification off. `default` uses Python's standard SSL context. Any other value (normally `custom`) uses the hardened custom context in `cert.py`, which shapes the TLS fingerprint. A legacy JSON boolean (`true` or `false`) is read as `custom`.",
    "advanced_options.env_files": "A list of `.env`, `.yaml`/`.yml` or `.json` files whose values are loaded as environment variables (`OFSC_*` overrides) before settings are built. Later files override earlier ones. Before them, the app loads a `.env` file found by python-dotenv. It searches upward from `ofscraper/utils/of_env/`, and from the working folder only in the standalone binaries, the REPL or a debugger. The `--env-files` option replaces this list for one run.",
    "script_options.after_action_script": "An executable that runs after each user is processed by the like, unlike or download actions. It also runs after scrape-paid, check and manual downloads. It receives JSON with the username, media and posts on stdin. The `-aas`/`--after-action-script` option overrides it.",
    "script_options.post_script": "An executable that runs once when the program finishes. It receives JSON on stdin that lists processed and unprocessed users for the like, unlike, download and scrape-paid activities. The `-ps`/`--post-script` option overrides it.",
    "script_options.naming_script": "An executable that runs for each download to choose its path. It receives JSON about the media, post and current formats on stdin. Non-empty stdout is used as the full file path, in place of `dir_format` and `file_format`. Programs the script starts are stopped once it exits, times out or is cancelled, and when ofscraper exits (a warning is logged when the script exits and leaves any running). `nohup` and `&` don't keep a program running. On Linux and macOS, a program started in its own session (for example with `setsid`) is left running; on Windows, none is. The `-ns`/`--naming-script` option overrides it.",
    "script_options.after_download_script": "An executable that runs after each file is downloaded (text files included). It receives the final file path on stdin. Programs the script starts are stopped once it exits, times out or is cancelled, and when ofscraper exits (a warning is logged when the script exits and leaves any running). `nohup` and `&` don't keep a program running. On Linux and macOS, a program started in its own session (for example with `setsid`) is left running; on Windows, none is. The `-adl`/`--after-download-script` option overrides it.",
    "script_options.skip_download_script": "An executable that runs before each download. It receives JSON about the media, post and total size on stdin. It's asked once per file (per track for a DRM video) per run. If it prints `false` or nothing, the file is skipped in this run only: it's counted as skipped, not saved as downloaded, and the script is asked about it again on the next run. If it prints `skip-permanent` (any case), the file is skipped for good: counted as skipped and saved as downloaded with no file, so it isn't asked about again. To undo that, run with `--retry-permanent-skips`, or un-mark the files with `ofscraper db --unmark-permanent-skips`. Any other output, or a script that fails, lets the download proceed. Until #351, `false` and nothing also saved the file as downloaded; to keep that, print `skip-permanent`. Programs the script starts are stopped once it exits, times out or is cancelled, and when ofscraper exits (a warning is logged when the script exits and leaves any running). `nohup` and `&` don't keep a program running. On Linux and macOS, a program started in its own session (for example with `setsid`) is left running; on Windows, none is. The `-sdl`/`--skip-download-script` option overrides it.",
    "responsetype.timeline": "The folder name used for `{responsetype}` for timeline posts. " + _RESPONSETYPE_TAIL,
    "responsetype.message": "The folder name used for `{responsetype}` for messages. " + _RESPONSETYPE_TAIL,
    "responsetype.archived": "The folder name used for `{responsetype}` for archived posts. It takes precedence over pinned and other types. " + _RESPONSETYPE_TAIL,
    "responsetype.paid": "The folder name used for `{responsetype}` for purchased (paid) content found by `--scrape-paid` or the purchased area. " + _RESPONSETYPE_TAIL,
    "responsetype.stories": "The folder name used for `{responsetype}` for stories. " + _RESPONSETYPE_TAIL,
    "responsetype.highlights": "The folder name used for `{responsetype}` for story highlights. " + _RESPONSETYPE_TAIL,
    "responsetype.profile": "The folder name used for `{responsetype}` for profile media (avatar and header images). " + _RESPONSETYPE_TAIL,
    "responsetype.pinned": "The folder name used for `{responsetype}` for pinned posts. " + _RESPONSETYPE_TAIL,
    "responsetype.streams": "The folder name used for `{responsetype}` for streams. " + _RESPONSETYPE_TAIL,
}

# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------

DATABASE_NOTES = """
Each creator has one SQLite file, `user_data.db`. It sits in the folder given by the `metadata` config value (default `{configpath}/{profile}/.data/{model_id}`). `databasePlaceholder.databasePathHelper` in `ofscraper/classes/placeholder.py` fills in the placeholders (`username`, `model_username`, `first_letter`, `model_id`, plus the common ones) and appends `user_data.db`.

- **Connections:** `ofscraper/db/operations_/wrapper.py` opens a connection for each operation, in WAL mode, so `user_data.db-wal` and `-shm` files sit next to the database. Writes go through one worker thread and are retried on "database is locked".
- **Backups:** they go to a `backup` folder beside the database (`ofscraper/db/backup.py`).
  - At the start of a per-creator run, `table_init_create` copies the database to `backup/user_data_copy_N.db`, with N rotating through 1 to 5. It copies when the `DBINTERVAL` setting (default 86400 seconds) has passed since the last copy, or when the backup folder is empty. It makes no copy of a database created in that run.
  - Before any pending schema migration, it also writes `backup/old_schema_{model_id}_{timestamp}_db_backup.db`. The name is `old_schema_db_backup.db` when there is no model id. It checks that the copy has the same size, and restores it if the migration raises. A database created in that run (a first scrape, or a new Merge Databases target) gets no `old_schema_*` backup.
- **Merging:** the Merge Databases menu option (`ofscraper/db/merge.py`) creates and migrates a target `user_data.db`. It then copies in rows from every `user_data.db` found under a chosen folder, skipping rows whose key is already present. Each source must contain exactly one numeric model id in `profiles`.
- **Fansly:** Fansly runs use separate files. When the `metadata` template has no site-specific field (`save_location`, `root`, `site_name`, `model_id` and their aliases), a `Fansly` subfolder is added before `user_data.db`, so Fansly rows don't land in the OnlyFans file. Fansly databases carry a `schema_flags` row `site=fansly`.
- **Read-only users:** the `db` command and the hash-based duplicate checks only read the database. The exception is `db --unmark-permanent-skips`, which un-marks the selected permanent skips.
"""

TABLES = {
    "medias": {
        "summary": "One row per media item (image, video, audio) seen in a post, message, story or other area. It holds the item's API metadata and, once handled, where it was saved and whether it counts as downloaded.",
        "written_by": "Scraping calls `batch_mediainsert` (`ofscraper/db/operations_/media.py`). Scraping means any action-mode run (download, like, unlike), the `metadata` command, manual/url mode and the check/table mode. The callers are `ofscraper/data/posts/post.py`, `commands/manual.py` and `commands/check.py`.\n\n- **New and existing rows:** `(media_id, post_id)` pairs not yet in the table are inserted with API fields only. Pairs already present get their API fields (`link`, `linked`, `api_type`, `media_type`, `preview`, `created_at`, `posted_at`, `duration`, `unlocked`) updated on every scrape, not only in metadata mode.\n- **After a download:** once a file is written, `mark_media_as_downloaded` applies the API fields again and sets `directory`, `filename`, `size`, `downloaded`, `hash` and `skip_permanent`. The callers are `main_download.py`, `alt_download.py` (for DRM), `fansly_stream_download.py` and `downloadmanager._force_download` (for zero-size or known-bad URLs). This update matches on `media_id` and `model_id` only, so every row for that media under the creator is updated.\n- **Metadata command:** `commands/metadata/manager.py` uses the same function to set download status and filename from files on disk, without downloading.\n- **Stray media:** `batch_set_media_downloaded` sets `unlocked=0`. Despite its name, it does not touch `downloaded`. `clean_stray_media` in `post.py` calls it on every scrape for not-yet-downloaded unlocked rows. These are rows whose post was just scraped but whose media id was not returned. The `metadata` command calls it for strays when `mark_stray` is on.\n- **Permanent skips undone:** `unmark_permanent_skips` sets `downloaded` and `skip_permanent` back to `NULL` on rows with `skip_permanent = 1` only. `ofscraper db --unmark-permanent-skips` calls it for the rows it selects, and a `--retry-permanent-skips` run calls it when the script no longer skips a file for good.\n- **Collision recovery:** the offline tool `python -m ofscraper.commands.recover_collisions` sets `downloaded=0` for rows that share one file path, and writes an undo file.\n- **Migration and merge:** migration rebuilds the table once (`rebuild_media_table`). It copies every row into the new table in one transaction before the old table is dropped. The Merge Databases menu copies rows in.\n- **Deletes:** nothing in the app deletes rows.\n- **Unique key:** `UNIQUE (media_id, model_id, post_id)`. There is no `ON CONFLICT` clause. The code reads the existing `(media_id, post_id)` pairs and chooses insert or update itself. Merge dedupes on `(media_id, model_id)` only.",
        "columns": {
            "id": "Row id (`INTEGER PRIMARY KEY`), internal only.",
            "media_id": "The site media id.",
            "post_id": "The id of the post, message or story the media belongs to.",
            "link": "The download URL, or the MPD manifest URL for DRM video. `NULL` when the API gave neither.",
            "directory": "The folder the file was saved to. Set on download or by the `metadata` command.",
            "filename": "The file name the media was saved under.",
            "size": "The saved file size in bytes.",
            "api_type": "The area the media came from, as a capitalised response type (Timeline, Archived, Pinned, Streams, Messages, Stories, Highlights, Paid, Profile and so on).",
            "media_type": "The capitalised media type (Images, Videos, Audios and so on).",
            "preview": "1 if the media is a preview, else 0. On OnlyFans, the post carries preview media. On Fansly, the item is flagged `isPreview`.",
            "linked": "1 if the API gave a URL or MPD for the media, else 0.",
            "downloaded": "1 once the media counts as downloaded (file saved, forced, or marked by the `metadata` command). Otherwise 0 or `NULL`. Used to skip already-downloaded media.",
            "created_at": "The media creation time from the API (`createdAt`, else `postedAt`, else the post date).",
            "posted_at": "The date of the parent post or message.",
            "duration": "The media duration as a formatted string. `NULL` when unknown.",
            "unlocked": "1 if the account can view the media (API `canView` and a link exists). Set to 0 when stray-media cleanup decides the item is gone.",
            "hash": "The file hash recorded at download, when hashing is enabled. Used to find duplicate files.",
            "model_id": "The creator account id the row belongs to.",
            "skip_permanent": "1 when `skip_download_script` printed `skip-permanent`: the item is saved as downloaded with no file and isn't asked about again. `NULL` for every other row, including real downloads, other items saved as downloaded with no file, and rows saved before the column existed. A later download write clears it; the `metadata` command keeps it while the item stays downloaded with no file on disk. `--retry-permanent-skips` and `ofscraper db --unmark-permanent-skips` undo it.",
        },
    },
    "posts": {
        "summary": "One row per timeline, pinned, archived, streams, paid or label post seen for the creator.",
        "written_by": "`make_post_table_changes` (`ofscraper/db/operations_/posts.py`) runs on every scrape from `ofscraper/data/posts/post.py`. It covers the timeline, pinned, archived, streams and paid areas, and the posts inside labels via `make_label_table_changes`. Manual/url mode and the check command reach it through `make_changes_to_content_tables`.\n\n- **New and existing rows:** new post ids are inserted. Existing rows are updated (and `is_deleted` reset to 0) only when a metadata mode is set, that is, under the `metadata` command. On every scan, an existing row whose `purchase_type` or `mentions` is still `NULL` gets the value the scan found; a scan without one leaves the stored value alone. The metadata update also replaces `mentions` with the scan's list when it has one, and never changes `purchase_type`.\n- **Deleted posts:** `mark_post_as_deleted` sets `is_deleted=1` for posts that the timeline, archived and streams scanners (`ofscraper/data/api/`) expected from the database but the API skipped past.\n- **Migration and merge:** migration rebuilds the table once. It copies every row into the new table in one transaction before the old table is dropped. The Merge Databases menu copies rows in.\n- **Deletes:** the app never deletes rows.\n- **Unique key:** `UNIQUE (post_id, model_id)`. The code looks up existing post ids (across all `model_id`s in the file) and chooses insert or update itself.",
        "columns": {
            "id": "Row id (`INTEGER PRIMARY KEY`), internal only.",
            "post_id": "The site post id.",
            "text": "The post text. It is sanitised first when the `sanitize-db-text` option is on.",
            "price": "The post price (0 when free).",
            "paid": "Truthy when the post is open or opened, has viewable media, or has a price.",
            "archived": "1 if the API marks the post archived.",
            "pinned": "1 if the API marks the post pinned.",
            "stream": "1 if the post has a stream id (a streams post).",
            "opened": "1 if the API marks the post opened.",
            "created_at": "The post date (`postedAt`, else `createdAt`).",
            "model_id": "The creator account id the row belongs to.",
            "is_deleted": "1 when a scan decided the post no longer exists on the site. Such posts are left out of the date lookups that drive later scans. Default 0.",
            "purchase_type": "For an OnlyFans purchase, whether the bought item was a `post` or a `message` (the purchase's `responseType`). `NULL` for rows not saved from a purchases list (the Purchased area, `paid_check`, or the purchases `msg_check` fetches); a bought message saved by those two commands goes to `messages` as before, without a purchase type, for Fansly purchases, and for rows saved before the column existed. A later timeline or messages scan never clears it, and a purchase scan fills it in for a row that already exists. `stash_sync` links a bought post's file to its page when this is `post`.",
            "mentions": "Fansly only: the post's `accountMentions` list as JSON text, exactly as the API sent it (`[]` when the post tags nobody). `NULL` for OnlyFans posts, Fansly purchases, and rows saved before the column existed; the next scan that sees the post fills it in.",
        },
    },
    "messages": {
        "summary": "One row per direct message seen in the chat with the creator, from either side.",
        "written_by": "`make_messages_table_changes` (`ofscraper/db/operations_/messages.py`) runs when the Messages area is scraped (`process_messages` in `ofscraper/data/posts/post.py`). Manual/url mode and the check command also run it.\n\n- **New and existing rows:** new message ids are inserted. Existing rows are updated (and `is_deleted` reset to 0) only under the `metadata` command. On every scan, an existing row whose `group_id` is still `NULL` gets the value the scan found; the metadata update doesn't change it.\n- **Deleted messages:** the messages scanner (`ofscraper/data/api/messages.py`) sets `is_deleted=1` for messages it expected but the API skipped past.\n- **Migration and merge:** migration rebuilds the table once, in one transaction, and keeps every column including `is_deleted`. The Merge Databases menu copies rows in, `is_deleted` included.\n- **Deletes:** the app never deletes rows.\n- **Unique key:** `UNIQUE (post_id, model_id)`. The application chooses insert or update based on the existing message ids.",
        "columns": {
            "id": "Row id (`INTEGER PRIMARY KEY`), internal only.",
            "post_id": "The site message id.",
            "text": "The message text. It is sanitised first when the `sanitize-db-text` option is on.",
            "price": "The message price (0 when free).",
            "paid": "Truthy when the message is open or opened, has viewable media, or has a price.",
            "archived": "1 if the API marks the message archived (normally 0).",
            "created_at": "The message date.",
            "user_id": "The id of the sender (`fromUser`). It lets you tell the creator's messages from the account's own.",
            "model_id": "The creator account id the chat belongs to.",
            "is_deleted": "1 when a scan decided the message no longer exists. Default 0.",
            "group_id": "Fansly only: the conversation id (`groupId`), so a message's page is its conversation's, `https://fansly.com/messages/<group_id>`. `NULL` for OnlyFans messages and for rows saved before the column existed; the next messages scan that sees the message fills it in. `stash_sync` uses it for a Fansly message's link.",
        },
    },
    "stories": {
        "summary": "One row per story or highlight story seen for the creator.",
        "written_by": "`make_stories_table_changes` (`ofscraper/db/operations_/stories.py`) runs when the Stories or Highlights areas are scraped (`ofscraper/data/posts/post.py`). Manual/url mode and the check command also run it.\n\n- **New and existing rows:** new ids are inserted. Existing rows are updated only under the `metadata` command.\n- **Migration and merge:** migration rebuilds the table once. It copies every row into the new table in one transaction before the old table is dropped. The Merge Databases menu copies rows in.\n- **Deletes:** the app never deletes rows.\n- **Unique key:** `UNIQUE (post_id, model_id)`. The application inserts ids that are not already present.",
        "columns": {
            "id": "Row id (`INTEGER PRIMARY KEY`), internal only.",
            "post_id": "The site story id.",
            "text": "The story text, else its title, else an empty string.",
            "price": "The price (normally 0).",
            "paid": "The paid/open flag, computed as for posts.",
            "archived": "The archived flag from the API (normally 0).",
            "created_at": "The story date.",
            "model_id": "The creator account id the row belongs to.",
        },
    },
    "labels": {
        "summary": "Links the creator's post labels (collections) to posts. One row per (label, post) pair. On Fansly a label is a wall, a named tab on the creator's profile. The main \"Posts\" wall holds the whole timeline, so it isn't a label.",
        "written_by": "`make_label_table_changes` (`ofscraper/db/operations_/labels.py`) runs when the Labels area is scraped (`process_labels` in `ofscraper/data/posts/post.py`). The check command also runs it.\n\n- **New and existing rows:** for each label, posts not yet recorded under it are inserted. Existing pairs are updated only under the `metadata` command.\n- **Repeat scans:** a label whose last scan finished is paged only until a page whose posts are all recorded. An older post added to a label longer than one page can be missed this way; a full scan (`--after`, or incremental downloads off) picks it up. This applies to OnlyFans labels and Fansly walls alike.\n- **Posts table:** the function then passes the labelled posts to `make_post_table_changes`, so they also land in `posts`.\n- **Migration and merge:** migration rebuilds the table once. It copies every row into the new table in one transaction before the old table is dropped. The Merge Databases menu copies rows in.\n- **Deletes:** the app never deletes rows.\n- **Unique key:** `UNIQUE (post_id, label_id, model_id)`. The application chooses insert or update for each label.",
        "columns": {
            "id": "Row id (`INTEGER PRIMARY KEY`), internal only.",
            "label_id": "The site label id. On Fansly, the wall id.",
            "name": "The label name. On Fansly, the wall name without trailing spaces.",
            "type": "The label type from the API. `wall` for Fansly walls.",
            "post_id": "The id of a post carrying the label.",
            "model_id": "The creator account id the row belongs to.",
        },
    },
    "profiles": {
        "summary": "The usernames the creator account has been seen under in this database.",
        "written_by": "`write_profile_table` (`ofscraper/db/operations_/profile.py`) adds a row each time the account is seen under a new username. `table_init_create` in `ofscraper/db/operations.py` calls it at the start of every per-creator run (action mode, `metadata` command, manual/url mode, check command).\n\n- **Repeat runs:** the insert uses `WHERE NOT EXISTS`, so repeat runs under the same name add nothing.\n- **Migration and merge:** migration rebuilds the table once (`rebuild_profiles_table`, flag `profile_username_constraint_modified`). It copies every row into the new table in one transaction before the old table is dropped. The Merge Databases menu copies rows in. Merge and migration use this table to find the single model id of an old database.\n- **Unique key:** `UNIQUE (user_id, username)`.",
        "columns": {
            "id": "Row id (`INTEGER PRIMARY KEY`), internal only.",
            "user_id": "The creator account id. It has the same value as `model_id` elsewhere, and is named `user_id` for legacy reasons.",
            "username": "The username the account had when it was seen.",
        },
    },
    "models": {
        "summary": "The creator account ids whose data is stored in this database.",
        "written_by": "`write_models_table` (`ofscraper/db/operations_/profile.py`) inserts the model id if it is not already present. `table_init_create` calls it on every per-creator run. The Merge Databases menu adds the model id of each merged database. The insert uses `WHERE NOT EXISTS`. Unique key: `UNIQUE (model_id)`.",
        "columns": {
            "id": "Row id (`INTEGER PRIMARY KEY`), internal only.",
            "model_id": "The creator account id.",
        },
    },
    "products": {
        "summary": "A legacy table for paid products. It is created and migrated, but no current code path writes rows to it.",
        "written_by": "The table is only created (`create_products_table`), rebuilt once by migration (`rebuild_products_table`) and copied by the Merge Databases menu (`ofscraper/db/operations_/others.py`, `ofscraper/db/merge.py`). No scrape, download or command inserts rows, so it is normally empty. The rebuild copies every row into the new table in one transaction before the old table is dropped. Unique key: `UNIQUE (post_id, model_id)`.",
        "columns": {
            "id": "Row id (`INTEGER PRIMARY KEY`), internal only.",
            "post_id": "The id of the product or its post.",
            "text": "The product text.",
            "price": "The price.",
            "paid": "The paid flag.",
            "archived": "The archived flag.",
            "created_at": "The creation date.",
            "title": "The product title.",
            "model_id": "The creator account id the row belongs to.",
        },
    },
    "others": {
        "summary": "A legacy table for content outside the main areas. It is created and migrated, but no current code path writes rows to it.",
        "written_by": "The table is only created (`create_others_table`), rebuilt once by migration (`rebuild_others_table`) and copied by the Merge Databases menu. No scrape, download or command inserts rows, so it is normally empty. As with `products`, the rebuild copies every row into the new table in one transaction before the old table is dropped. Unique key: `UNIQUE (post_id, model_id)`.",
        "columns": {
            "id": "Row id (`INTEGER PRIMARY KEY`), internal only.",
            "post_id": "The id of the item.",
            "text": "The text.",
            "price": "The price.",
            "paid": "The paid flag.",
            "archived": "The archived flag.",
            "created_at": "The creation date.",
            "model_id": "The creator account id the row belongs to.",
        },
    },
    "schema_flags": {
        "summary": "Key/value markers that record which schema migrations have run on this file, plus the site the database belongs to.",
        "written_by": "`modify_tables` in `ofscraper/db/transition.py` compares the flags with the list in `ofscraper/db/difference.py`. `table_init_create` calls it on every per-creator run, and merge calls it too. For each missing flag, it runs the matching change, and then `add_flag_schema` writes `flag_name=<flag>` and `flag_value=1`. A brand-new database has no flags, so it goes through every rebuild once too.\n\n`write_site_flag` writes `flag_name='site'` and `flag_value='fansly'` on each Fansly run. OnlyFans databases get no site row.\n\nUnique key: `flag_name` is the `PRIMARY KEY`, and writes use `INSERT OR REPLACE`.\n\nFlag names:\n\n- `media_hash`: `medias.hash` column added.\n- `media_model_id`: `medias.model_id` column added.\n- `media_posted_at`: `medias.posted_at` column added.\n- `media_duration`: `medias.duration` column added.\n- `media_unlocked`: `medias.unlocked` column added.\n- `posts_model_id`: `posts.model_id` column added.\n- `posts_pinned`: `posts.pinned` column added.\n- `posts_stream`: `posts.stream` column added.\n- `posts_opened`: `posts.opened` column added.\n- `posts_is_deleted`: `posts.is_deleted` column added.\n- `messages_model_id`: `messages.model_id` column added.\n- `messages_is_deleted`: `messages.is_deleted` column added.\n- `posts_purchase_type`: `posts.purchase_type` column added.\n- `posts_mentions`: `posts.mentions` column added.\n- `messages_group_id`: `messages.group_id` column added.\n- `media_skip_permanent`: `medias.skip_permanent` column added.\n- `stories_model_id`: `stories.model_id` column added.\n- `labels_model_id`: `labels.model_id` column added.\n- `products_model_id`: `products.model_id` column added.\n- `other_model_id`: `others.model_id` column added.\n- `profile_username_constraint_modified`: `profiles` rebuilt with `UNIQUE (user_id, username)`.\n- `stories_model_id_constraint_added`: `stories` rebuilt with `UNIQUE (post_id, model_id)`.\n- `posts_model_id_constraint_added`: `posts` rebuilt with `UNIQUE (post_id, model_id)`.\n- `messages_model_id_constraint_added`: `messages` rebuilt with `UNIQUE (post_id, model_id)`.\n- `labels_model_id_constraint_added`: `labels` rebuilt with `UNIQUE (post_id, label_id, model_id)`.\n- `others_model_id_constraint_added`: `others` rebuilt with `UNIQUE (post_id, model_id)`.\n- `products_model_id_constraint_added`: `products` rebuilt with `UNIQUE (post_id, model_id)`.\n- `media_post_id_constraint_added`: `medias` rebuilt with `UNIQUE (media_id, model_id, post_id)`. Written together with `media_bool_changes`.\n- `media_bool_changes`: `medias` rebuilt with its boolean columns. Written together with `media_post_id_constraint_added`. If either flag is missing, the one rebuild runs.\n- `media_size_skip_repaired`: a one-time repair, run after the changes above (`repair_tables`). Before #326 a file skipped by a size limit was saved as downloaded with no file, and its row got the media type `Forced_skippeds`. The repair sets `downloaded` back to NULL on the rows of that media (same `media_id` and `model_id`, any post) that are downloaded with no `directory`, `filename`, `size` or `hash`. It finds the media by that label in `medias`, and in the `user_data_copy_N.db` and `old_schema_*` backups, which it opens read-only and reads before the run writes any backup (a new copy can replace the one that still has the label). Media with a file recorded in any of its rows, or with a permanent `skip_download_script` skip (`skip_permanent = 1`), is left alone, and so is every other row downloaded with no file. The `old_schema_*` backup taken first holds the rows as they were. The flag is written in the same transaction.\n- `site`: not a migration flag. The value is the site name (`fansly`) for a Fansly database. The row is absent for OnlyFans.",
        "columns": {
            "flag_name": "The migration flag name (see the flag list above) or `site`.",
            "flag_value": "1 for a completed migration step (only rows with value 1 count as done). For the `site` row, the site name.",
        },
    },
}
