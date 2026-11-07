"""Descriptions the code doesn't carry, for scripts/reference/build_reference.py.

Every key here must name something that exists, and the things listed in
test/test_reference.py must all have an entry. Keep each description to one
to three plain sentences: what it does and how it interacts with other
settings. Defaults, types and names are generated; don't repeat them.
"""

# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------

# extra notes for options, keyed by the option's dest (the name in the args)
CLI = {
    "redownload": "Sets `force_all`, `--after 2000` and `--before` tomorrow for the run, so every item is scanned and downloaded again (`merged_settings`).",
    "text_only": "Also turns on `--text`: text files are written and media is skipped.",
    "original": "Turns off file name truncation for the run, whatever `file_options.truncation_default` says.",
    "no_auto_resume": "Overrides `download_options.auto_resume` to off for the run.",
    "no_cache": "Disables both the general cache and the API cache, and turns off incremental downloads. It's the only way to do so: `advanced_options.cache-mode` `disabled` doesn't work at present (#200).",
    "no_api_cache": "Disables only the API response cache.",
    "download_limit": "Values below 1024 bytes per second are raised to 1024. The limit is shared by all downloads in the run.",
    "key_mode": "`cdrm` posts request headers, cookies included, to cdrm-project.com; `manual` uses the local CDM files (`--private-key`, `--client-id`).",
    "quality": "The lowest video quality to accept: the smallest available quality at or above it is downloaded, and `source` when none matches (`ofscraper/utils/args/accessors/quality.py`, `classes/of/media.py`). Without it, `source` is used.",
    "env_files": "Not loaded at present: `setup_settings` loads only `advanced_options.env_files` and nothing reads the merged value of this option (#201).",
}

# --------------------------------------------------------------------------
# environment defaults
# --------------------------------------------------------------------------

ENV_INTRO = """
Built-in defaults the app reads with `of_env.getattr(KEY)`
(`ofscraper/utils/of_env/of_env.py`). They're loaded once from the files in
`ofscraper/utils/of_env/values/` and cached. Each value can be overridden two
ways: the listed `OFSC_*` environment variable, read when the defaults are
loaded, or an environment variable with the bare key name (e.g. `DATABASE_TIMEOUT`),
read on every lookup and converted to the default's type. A `.env` file found by python-dotenv, which searches upward from `ofscraper/utils/of_env/` (from the working folder only in the standalone binaries, the REPL or a debugger), then
the env files named in `advanced_options.env_files`, are loaded into the
environment first and override variables already set
(`ofscraper/utils/of_env/load.py`). Values shown are the defaults with no environment variables set; paths
under your home directory are shown as `{home_directory}`. Descriptions come
from the comment above each value in the source where there is one.
"""

ENV_SLEEPER = """
Requests back off when they get rate-limit (429/503/504) or 403 errors
(`ofscraper/managers/sessionmanager/sleepers.py`, `SessionSleep` in
`sessionmanager.py`). Each kind of request has its own set of values, named
`<KIND>_SESSION_*` for rate limits and `<KIND>_SESSION_403_*` for 403s; the
standard API uses `SESSION_*`. The wait starts at `*_MIN_SLEEP`. If that is 0,
the first error sets it to `*_SLEEP_INIT` seconds (or 1 if that is 0);
otherwise the first error already multiplies it. Each error multiplies the wait
by `*_SLEEP_INCREASE_FACTOR`, up to `*_SLEEP_MAX`, but only if
`*_SLEEP_INCREASE_TIME_DIFF` seconds have passed since the last change (or since the program started or
the last per-creator reset). After `*_SLEEP_DECAY_THRESHOLD` seconds without a change
the wait is divided by `*_SLEEP_DECAY_FACTOR`, down to `*_MIN_SLEEP`.
`*_MIN_SLEEP` is also the minimum gap kept between requests. Before each
request the rate-limit wait runs first, then the 403 backoff if one is running.
The 403 `*_MIN_SLEEP` gap is kept only when the rate-limit `*_MIN_SLEEP` is 0
and no rate-limit backoff is running.
"""

# options merged_settings reads but that don't actually override the config
# value, so they aren't listed as overrides or fallbacks
NOT_MERGED = {"env_files"}

# descriptions for keys whose source has no comment naming them
ENV = {
    "ALT_FORCE_KEY": "When on, the `metadata` command fetches a fresh DRM key for protected (MPD) media instead of reusing one (`commands/metadata/manager.py`).",
    "KEY_OPTIONS": "The allowed `cdm_options.key-mode-default` values, from `ofscraper/utils/const.py`; not read from the environment.",
    "SSL_VALIDATION_DEFAULT": "Default for `advanced_options.ssl_verify` when the config has no usable value.",
    "mainPromptChoices": "Menu entries of the interactive main menu; not read from the environment.",
    "configPromptChoices": "Menu entries of the interactive config editor; not read from the environment.",
    "actionPromptChoices": "Menu entries for picking actions interactively; not read from the environment.",
    "usernameOrListChoices": "Menu entries for picking creators interactively; not read from the environment.",
    "profilesPromptChoices": "Menu entries of the interactive profile menu; not read from the environment.",
    "modelPrompt": "Menu entries for filtering and sorting the creator list interactively; not read from the environment.",
    "LOG_SUBPROCESS_LEVEL": "Log level for subprocess output that has no more specific setting. `OFSC_LOG_SUBPROCESS_LEVELL` is the old misspelled name, still read.",
    "MPD_SESSION_SLEEP_INIT": "Defined but not read anywhere; MPD requests use the standard `SESSION_*` values.",
    "DISK_SPACE_CHECK_PATH": "Path whose disk's free space is compared with `download_options.system_free_min` (`ofscraper/utils/system/free.py`). It's not the save location unless you set it to be.",
}

# variables read with os.getenv outside ofscraper/utils/of_env/values
ENV_DIRECT = {
    "OFSC_FANSLY_API_BASE": "Base URL of the Fansly API that Fansly requests go to.",
    "OFSC_FANSLY_AUTH_FILE_NAME": "Name of the Fansly credentials file in the profile folder.",
}

# (regular expression for the key, description); the first match is used
ENV_PATTERNS = [
    (r"[A-Z_]*SESSION(_403)?_SLEEP_INIT", "Wait set by the first error of this kind when `*_MIN_SLEEP` is 0 (0 means 1 second); not used when `*_MIN_SLEEP` is above 0."),
    (r"[A-Z_]*SESSION(_403)?_SLEEP_INCREASE_TIME_DIFF", "Seconds that must pass since the last change before another error raises the wait."),
    (r"[A-Z_]*SESSION(_403)?_SLEEP_MAX", "Longest backoff wait, in seconds."),
    (r"[A-Z_]*SESSION(_403)?_SLEEP_INCREASE_FACTOR", "Each further error multiplies the wait by this."),
    (r"[A-Z_]*SESSION(_403)?_SLEEP_DECAY_THRESHOLD", "Seconds without a change after which the wait shrinks."),
    (r"[A-Z_]*SESSION(_403)?_SLEEP_DECAY_FACTOR", "The wait is divided by this when it shrinks."),
    (r"[A-Z_]*SESSION(_403)?_MIN_SLEEP", "Smallest wait, and the minimum gap kept between requests, in seconds. The wait starts here."),
    (r"[A-Z_]+_SUBPROCESS_LEVEL", "Log level for the output of this subprocess (the user script, ffmpeg or ffprobe named in the key); 0 turns that output off."),
]

# --------------------------------------------------------------------------
# output templates
# --------------------------------------------------------------------------

PLACEHOLDER_INTRO = """
Names usable in braces in the `file_options.dir_format`, `file_options.file_format`
and `metadata` templates, and in text file names
(`ofscraper/classes/placeholder.py`). Each column says which template gets the
name. Templates are filled with Python's `str.format`, so object values allow
attribute or key access: `{modelObj.name}`, `{args.posts}`, and, because
`config` is a plain dict, `{config[file_options][date]}`.

- Profile media (avatar, header) ignore `file_format` and are saved as
  `<file_name>.<ext>`.
- When `FILE_COUNT_PLACEHOLDER` is on (the default) and `file_format` uses none
  of `filename`, `only_file_name`, `original_filename` or `media_id`, a post
  with several media, or a story or highlight, gets `_<count>` before the
  extension.
- On Fansly, if the `metadata` template uses none of `save_location`, `root`,
  `site_name` or `model_id` (or their aliases), the site name is added as a
  subfolder so Fansly rows don't share an OnlyFans `user_data.db`.
- The validators in `ofscraper/prompts/prompt_validators.py` aren't called
  anywhere, and accept only some of these names.
"""

PLACEHOLDERS = {
    "config_path": "The config home folder (common_paths.get_config_home(), e.g. {home_directory}/.config/ofscraper); usually written {configpath}, which is how the default metadata path uses it.",
    "profile": "Name of the active profile, e.g. main_profile.",
    "site_name": "Name of the site being scraped (sites.site_name()), e.g. the Fansly name on Fansly runs; usually written {sitename}.",
    "save_location": "The configured save location; on Fansly runs it is '<save location>/Fansly'. Same value as {root} but as the configured string.",
    "my_id": "The logged-in account's numeric id; 'anon' in anonymous mode.",
    "my_username": "Username of the logged-in account; 'anon' in anonymous mode.",
    "root": "Pathlib.Path of {save_location} (the media root, Fansly subfolder included).",
    "username": "The creator's username. In dir_format, file_format and text files it also exists, as the underscore-free alias of {user_name} (same value).",
    "model_username": "The creator's username (lower-cased by the media/post objects for dir and file names).",
    "model_id": "The creator's numeric account id (OnlyFans ids are short; Fansly ids are 18-digit snowflakes). Default metadata path is {configpath}/{profile}/.data/{model_id}.",
    "first_letter": "First letter of the creator's username, upper-cased, e.g. 'A'.",
    "user_name": "The creator's username (same as {model_username}); its alias {username} also works.",
    "post_id": "Id of the post or message the media belongs to (for text files, the post's own id).",
    "media_id": "Id of the media item; including it (or a filename field) in file_format stops the automatic _<count> suffix.",
    "media_type": "Capitalised media kind: Images, Videos (gifs count as Videos), Audios, Forced_skipped, or 'Text' for text files; usually written {mediatype}.",
    "value": "'Free' or 'Paid', from the post's price (0 means Free).",
    "date": "The post's date (postedAt, else createdAt) formatted with the file_options.date config (arrow tokens, default MM-DD-YYYY).",
    "response_type": "Display name of the content area from the responsetype config map (defaults Posts, Messages, Archived, Stories, Profile, Streams; timeline and pinned map to Posts, paid to Messages, highlights to Stories); archived posts use the configured Archived name; usually written {responsetype}.",
    "label": "The post's label name, or the string 'None' when it has no label.",
    "download_type": "'Protected' for DRM (MPD) media, 'Normal' otherwise.",
    "modelObj": "Object: the creator's model (ofscraper/classes/of/models.py) from the model manager, used with attribute access, e.g. {modelObj.name}, {modelObj.id}, {modelObj.final_current_price}; None if the creator isn't loaded, so attribute access then fails.",
    "quality": "Selected video quality such as 1080, 720, 240 or 'source'; non-videos and text files are 'source' (QUALITY_UNKNOWN_DEFAULT when unknown).",
    "file_name": "Final media file name without extension: the name from the media URL, the media id if none, videos with _<quality> appended, cleaned and with spaces replaced by space_replacer; for text files the sanitised, truncated post text. Usually written {filename} (the default file_format is {filename}.{ext}).",
    "original_filename": "File name taken from the media URL (the raw media filename, None when the media has no URL); for text files the sanitised post text.",
    "only_file_name": "Like {file_name} but without the video quality suffix; for text files the sanitised post text.",
    "only_filename": "Same value as {only_file_name}.",
    "text": "For media: the post text cleaned and truncated to textlength (falls back to the file name, the date, or the media id). For text files: the sanitised, truncated post text.",
    "config": "Object: the parsed config.json as a dict, so use item syntax, e.g. {config[file_options][date]}; attribute access does not work.",
    "args": "Object: the parsed command-line arguments (an AutoDotDict), usable with attribute access, e.g. {args.posts}; a missing name gives None.",
    "ext": "The file extension without the dot, e.g. mp4, jpg; 'txt' for text files.",
    "current_price": "'Free' if the creator's final current price is 0, else 'Paid'; MODEL_PRICE_PLACEHOLDER ('Unknown_Price' by default) when the model isn't loaded.",
    "regular_price": "'Free' or 'Paid' from the creator's final regular price, or MODEL_PRICE_PLACEHOLDER.",
    "promo_price": "'Free' or 'Paid' from the creator's final promo price, or MODEL_PRICE_PLACEHOLDER.",
    "renewal_price": "'Free' or 'Paid' from the creator's final renewal price, or MODEL_PRICE_PLACEHOLDER.",
}

ACTIONS = {
    "download": "Scrapes the selected areas (--posts) for each selected creator and downloads the media that pass the filters into save_location using dir_format and file_format, recording them in the creator's user_data.db; with --text (or --text-only) it also writes post text to .txt files. Runs downloader() in commands/scraper/actions/download, then the after-download action script.",
    "like": "Likes (favorites) posts in the selected like areas that aren't liked yet, one request at a time with a random sleep between requests (MIN/MAX_SLEEP_DURATION_LIKE); a post that toggles the wrong way is toggled again. Runs like.process_like, then the after-like action script; the code warns that OnlyFans allows about 1000 likes per hour.",
    "unlike": "Removes likes from already-liked posts in the selected like areas, the same way as like. Runs like.process_unlike; can't be combined with like.",
}

COMMANDS = {
    "(main)": "No subcommand. Entry is ofscraper/__main__.py, then Manager.pick() calls commands/scraper/scraper.main(): it cleans temp files and the DB, checks the CDM, then: with --daemon, prompts for actions if none were given and reruns on a schedule; with --action or --scrape-paid, runs those actions once (repeating with prompts if the infinite-loop config is on); with only Fansly --live/--live-watch, records livestreams; otherwise opens the interactive menu (Action, Auth (edit auth.json), Config (edit config.json), Profile, Merge databases, Quit). Reads auth.json and config.json from the profile, writes media under save_location and rows to each creator's user_data.db.",
    "manual": "ofscraper manual -u URL... or -f FILE (one is required). Downloads specific posts given as OnlyFans URLs (post, chat message, story, highlight) or bare post ids; a bare id is looked up on the timeline, then in that creator's purchases. Forces force_all, so existing files are downloaded again; writes posts and media to the creator's user_data.db and media under save_location, then runs the after-download script.",
    "msg_check": "ofscraper msg_check -u ITEM... or -f FILE. Each item is a creator username, or any text containing a number, which is taken as the model id (e.g. a chat URL). Fetches the creator's messages and purchases (from the check cache unless --force; the cache expires after 3 days), writes them to user_data.db, and opens an interactive table of the media where unlocked rows can be queued for download; a background thread downloads them.",
    "story_check": "ofscraper story_check -u USERNAME... (or -f). Fetches the creators' stories and highlights from the API (no check cache), writes them to user_data.db and opens the same downloadable media table.",
    "paid_check": "ofscraper paid_check -u USERNAME_OR_ID... (or -f). Fetches each creator's purchased content (check cache unless --force; a deleted creator, named DELETED_MODEL_PLACEHOLDER, is read from all purchases), writes it to user_data.db and opens the media table.",
    "post_check": "ofscraper post_check -u URL_OR_USERNAME... or -f FILE. Takes onlyfans.com/<username> URLs or bare usernames, fetches the areas in --check-area (default Timeline, Pinned, Archived, Streams; Labels also available) from the check cache unless --force, writes them to user_data.db and opens the media table. All check commands set force_all and after=0.",
    "metadata": "ofscraper metadata --metadata check|update|complete with the usual user and area options (--scrape-paid takes a mode too). Uses the API to update the creators' user_data.db without downloading: check refreshes metadata fields only; update also sets download status and file names from the files actually on disk; complete marks media downloaded and takes a new filename if there is one. --mark-stray marks DB media missing from the scrape (within --after/--before) as locked; --anon uses anonymous credentials.",
    "db": "ofscraper db with user selection, area (-o) and media filters (type, size, length, downloaded, locked, preview, protected, post/media ids, dates), sorting and a hard limit. Reads media rows from each selected creator's user_data.db and prints them as a table; -ep/--export PATH also writes a .csv. Makes no API calls for the media itself. With several creators each one rewrites the same CSV path, so only the last creator's rows remain.",
    "recover_collisions": "python -m ofscraper.commands.recover_collisions DB [--apply] [--undo FILE] [--path-root DIR] (argparse, not part of the CLI; see COLLISION_RECOVERY.md). Offline, for one creator's user_data.db: finds recorded paths shared by different media and prints a JSON report; --apply resets downloaded=0 for those media and writes a JSON undo file beside the database; --undo FILE previews or, with --apply, restores those flags. Never touches media files and doesn't contact OnlyFans.",
    "scripts/creator_names.py": "python scripts/creator_names.py [--all | --find NAME | --add MODEL_ID NAME [--force] | --csv FILE] [--data-dir DIR]: lists the usernames each creator account has had, from the profiles table of every <data-dir>/<model_id>/user_data.db (default the main profile's .data folder); --add appends a name. OnlyFans databases only.",
    "scripts/commit_version.sh": "CI helper: works out the commit-based version string, hashes and push type from git for the build workflows.",
    "scripts/release_version.sh": "CI helper: works out the release version from INPUT_VERSION or git tags and whether it is a stable or dev release.",
    "scripts/determine_docker_stable_dev_tags.py": "CI helper: asks the GitHub API for commit timestamps to decide the stable and dev Docker image tags.",
    "scripts/retry_action.sh": "CI helper: retries a command up to N times with a sleep between attempts.",
    "scripts/entry/": "Docker internals: entrypoint.sh, lib_user_setup.sh, lib_paths.sh and lib_permissions.sh set up the container user, data and config paths and permissions, then start the app.",
}

# --------------------------------------------------------------------------
# config.json
# --------------------------------------------------------------------------

CONFIG_SECTIONS = {
    "responsetype": "These values are the folder names that fill `{responsetype}` in `dir_format`. Each post's own type is lowercased, looked up here and the result capitalised with `str.capitalize()` (`Post.modified_responsetype` in `ofscraper/classes/of/posts.py`), so only the first letter stays uppercase. An empty or missing entry falls back to the type's own name, and archived posts always use `responsetype.archived`.",
}

CONFIG = {
    "main_profile": "Name of the profile folder in the config directory that holds auth.json, the cache and (by default) the per-creator databases; it also appears in log file names. The --profile option overrides it for one run.",
    "metadata": "Folder pattern for each creator's user_data.db, using placeholders such as {configpath}, {profile}, {model_id} and {model_username}. On Fansly runs a site subfolder is appended unless the pattern already contains a site-specific placeholder, so the two sites never share a database.",
    "discord": "Discord webhook URL that log messages are posted to. Nothing is sent unless the run's Discord log level is raised with -dc/--discord LOW or NORMAL (the option defaults to OFF).",
    "file_options.save_location": "Root folder for downloads; dir_format is resolved under it, and it is also the temp-file root when temp_dir is unset. Fansly runs save to a Fansly subfolder of it. Surrounding quotes from Windows 'Copy as path' are stripped.",
    "file_options.dir_format": "Folder pattern, relative to save_location, for each downloaded file, built from placeholders such as {model_username}, {responsetype} and {mediatype}. Ignored for a file when naming_script returns a path.",
    "file_options.file_format": "File-name pattern for each download, built from placeholders such as {filename}, {ext}, {date}, {text} and {media_id}. Ignored for a file when naming_script returns a path.",
    "file_options.textlength": "Maximum length of post text used in names (the {text} placeholder and text-based file names), counted in letters or words according to text_type_default; 0 means no limit. The -tl/--textlength option overrides it.",
    "file_options.space_replacer": "Character that replaces spaces in post text used for file and folder names; in word mode it is also treated as the word separator. An empty value falls back to a space. The -sr/--space-replacer option overrides it.",
    "file_options.date": "Arrow date-format string (e.g. MM-DD-YYYY) used for the {date} placeholder in dir_format, file_format and naming-script payloads.",
    "file_options.text_type_default": "Whether textlength counts 'letter's or 'word's; any other value falls back to the default. The -tt/--text-type option overrides it.",
    "file_options.truncation_default": "When true, final file paths longer than the operating system's limit are shortened to fit. The -g/--original flag turns truncation off for a run.",
    "file_options.filename_collision": "What to do when a download's target path already holds a different file. 'overwrite' keeps the old behaviour (the larger file wins); any other value saves the new file as name_<media_id>, then name_<media_id>_2 and so on, and keeps an existing file whose content is identical.",
    "download_options.filter": "Media types to process: a list or comma-separated string of Images, Audios and Videos (case-insensitive). An empty list processes all types. The -mt/--mediatype option overrides it.",
    "download_options.auto_resume": "When true, a leftover .part file is resumed with an HTTP range request; when false, partial files are deleted and downloads restart. The -ar/--no-auto-resume flag forces it off for a run.",
    "download_options.system_free_min": "Minimum free disk space; once free space drops below it, scraping of further post areas stops with 'Space min has been reached'. Accepts bytes or a size string such as '10GB'; 0 disables the check. Space is measured on OFSC_DISK_SPACE_CHECK_PATH (default '/'), not on save_location, and there is no CLI option for it.",
    "download_options.max_post_count": "Caps how many media items (not posts) are downloaded or processed per creator after all other filters; 0 means no cap. Overridden by -xc/--max-post-count or -mxc/--max-media-count, which set the same value.",
    "download_options.verify_all_integrity": "When true, ordinary (non-DRM) video and audio downloads and Fansly streams are checked with ffprobe against the expected duration, and a truncated file is deleted and reported as failed. Requires ffprobe; there is no CLI option for it.",
    "binary_options.ffmpeg": "Path to the ffmpeg executable, needed for DRM decryption and merging and for Fansly streams (version 6 or newer for DRM). If empty or invalid, OFSC_FFMPEG_DEFAULT, the pyffmpeg bundle and then PATH are tried. Surrounding quotes are stripped.",
    "cdm_options.private-key": "Path to the Widevine CDM private key file (private_key.pem), read when key-mode is 'manual'. The -pk/--private-key option overrides it. Surrounding quotes are stripped.",
    "cdm_options.client-id": "Path to the Widevine CDM client ID blob (client_id.bin), read when key-mode is 'manual'. The -ci/--client-id option overrides it. Surrounding quotes are stripped.",
    "cdm_options.key-mode-default": "How DRM content keys are obtained: 'manual' uses the local CDM files in private-key and client-id; 'cdrm' asks cdrm-project.com and sends it the request headers, cookies included. Other values fall back to the default. The -k/--key-mode option overrides it.",
    "performance_options.download_sems": "Number of downloads that run at the same time (the worker thread pool is twice this); must be at least 1. The --sem/-sd option overrides it.",
    "performance_options.download_limit": "Maximum download speed in bytes per second, shared across downloads; accepts a size string such as '10MB'. 0 means unlimited, and any non-zero value below 1024 is raised to 1024. The -dl/--download-limit option overrides it.",
    "content_filter_options.block_ads": "When true, posts whose text matches a built-in advertising regex (#ad, giveaway, shoutout, promo and similar) are excluded, added on top of any --neg-filter patterns. A -ba/--block-ads option is defined but not attached to any command, so the CLI rejects it (#201).",
    "content_filter_options.file_size_max": "Media larger than this are skipped at download time; also applied by the db command and the table view. Accepts bytes or a size string such as '500MB'; 0 means no limit, and an unparseable value is treated as 0. The -sx/--size-max option overrides it.",
    "content_filter_options.file_size_min": "Media smaller than this are skipped at download time; also applied by the db command and the table view. Accepts bytes or a size string; 0 means no limit, and an unparseable value is treated as 0. The -sm/--size-min option overrides it.",
    "content_filter_options.length_max": "Maximum duration in seconds; longer videos are filtered out. Only videos with a known duration are affected, not audio or images; 0 means no limit. The -lx/--length-max option overrides it.",
    "content_filter_options.length_min": "Minimum duration in seconds; shorter videos are filtered out. Only videos with a known duration are affected, not audio or images; 0 means no limit. The -lm/--length-min option overrides it.",
    "advanced_options.dynamic-mode-default": "Which source of OnlyFans request-signing rules to use: datawhores, xagler, rafa, digitalcriminals (aliases dc, digital), generic (needs OFSC_DYNAMIC_GENERIC_URL) or manual (needs OFSC_DYNAMIC_RULE_MANUAL). Unknown values fall back to the default, and anything that yields no rule falls back to datawhores. The -dr/--dynamic-rules option overrides it.",
    "advanced_options.skip_unavailable_content": "When true, timeline, pinned, archived, stories and highlights are not scraped for creators whose subscription has expired; profile, purchased content and messages are still scraped. Labels and streams are only scraped for active subscriptions regardless.",
    "advanced_options.downloadbars": "When true, shows a progress bar for each file being downloaded in addition to the overall progress. The -db/--downloadbars flag can turn it on but not off.",
    "advanced_options.cache-mode": "Storage backend for the on-disk cache: 'sqlite' (pickled values, cache_sql folder) or 'json' (JSON values, cache_json folder). 'disabled' is accepted but does not currently disable the cache (it selects JSON storage in the cache_sql folder); use --no-cache to disable caching (#200). Other values fall back to the default.",
    "advanced_options.rotate_logs": "When true, each run writes its own log file in a per-day folder under the logging directory; when false, all runs of a day append to one file. Must be true for logs_expire_time to delete old logs.",
    "advanced_options.sanitize_text": "When true, post and message text is stored in the database with HTML tags removed and whitespace collapsed; when false the raw API text is stored. Does not affect file names.",
    "advanced_options.temp_dir": "Root folder for in-progress (.part) downloads, laid out with dir_format like the final location; when unset, temp files are written under save_location. Surrounding quotes are stripped.",
    "advanced_options.remove_hash_match": "true hashes every download and deletes later files whose hash matches an earlier one for the same creator and media type; false only records hashes; null skips hashing.",
    "advanced_options.infinite_loop_action_mode": "When true, action mode (--action) asks after each run whether to continue and offers another action instead of exiting.",
    "advanced_options.incremental_downloads": "When true and no --after is given, each area is scanned only from the newest previously scanned post instead of from the start; like/unlike actions and forced full scans still scan everything. Turned off for the run by --no-cache. Setting it to false in config.json currently has no effect: the getter treats false as missing and uses the default (#200).",
    "advanced_options.default_user_list": "OnlyFans user lists to select creators from when -ul/--user-list is not given; a list or comma-separated string. The reserved names ofscraper.main, ofscraper.active and ofscraper.expired mean all, active and expired subscriptions. Names are matched against lowercased list names.",
    "advanced_options.default_black_list": "OnlyFans user lists whose members are excluded from selection when -bl/--black-list is not given; a list or comma-separated string. Names are matched against lowercased list names.",
    "advanced_options.logs_expire_time": "Age in hours after which .log files in the logging directory are deleted at cleanup, along with empty log folders. 0 disables it, and nothing is deleted unless rotate_logs is true.",
    "advanced_options.ssl_verify": "TLS mode for HTTP sessions: 'false' (also '0', 'none' or empty) turns certificate verification off, 'default' uses Python's standard SSL context, and any other value (normally 'custom') uses the hardened custom context in cert.py that shapes the TLS fingerprint. A legacy JSON boolean (true or false) is read as 'custom'.",
    "advanced_options.env_files": "List of .env, .yaml/.yml or .json files whose values are loaded as environment variables (OFSC_* overrides) before settings are built; later files override earlier ones. Before them, a .env file found by python-dotenv, which searches upward from `ofscraper/utils/of_env/` (from the working folder only in the standalone binaries, the REPL or a debugger), is loaded. The --env-files option isn't loaded at present (#201).",
    "script_options.after_action_script": "Executable run after each user is processed by the like, unlike or download actions (and after scrape-paid, check and manual downloads). It receives JSON with the username, media and posts on stdin. The -aas/--after-action-script option overrides it.",
    "script_options.post_script": "Executable run once when the program finishes. It receives JSON on stdin listing processed and unprocessed users for the like, unlike, download and scrape-paid activities. The -ps/--post-script option overrides it.",
    "script_options.naming_script": "Executable run for each download to choose its path. It receives JSON about the media, post and current formats on stdin; non-empty stdout is used as the full file path in place of dir_format and file_format. The -ns/--naming-script option overrides it.",
    "script_options.after_download_script": "Executable run after each file is downloaded (including text files), with the final file path on stdin. The -adl/--after-download-script option overrides it.",
    "script_options.skip_download_script": "Executable run before each download with JSON about the media, post and total size on stdin. If it prints 'false' or nothing, the download is skipped; any other output lets it proceed. The -sdl/--skip-download-script option overrides it.",
    "responsetype.timeline": "Folder name used for {responsetype} for timeline posts. The value is capitalized (only its first letter kept uppercase); empty falls back to the type name.",
    "responsetype.message": "Intended folder name for {responsetype} for messages; currently has no effect, because messages are looked up under the key 'messages' and so always get 'Messages' (#200).",
    "responsetype.archived": "Folder name used for {responsetype} for archived posts; it takes precedence over pinned and other types. The value is capitalized (only its first letter kept uppercase); empty falls back to the type name.",
    "responsetype.paid": "Folder name used for {responsetype} for purchased (paid) content found by --scrape-paid or the purchased area. The value is capitalized (only its first letter kept uppercase); empty falls back to the type name.",
    "responsetype.stories": "Folder name used for {responsetype} for stories. The value is capitalized (only its first letter kept uppercase); empty falls back to the type name.",
    "responsetype.highlights": "Folder name used for {responsetype} for story highlights. The value is capitalized (only its first letter kept uppercase); empty falls back to the type name.",
    "responsetype.profile": "Folder name used for {responsetype} for profile media (avatar and header images). The value is capitalized (only its first letter kept uppercase); empty falls back to the type name.",
    "responsetype.pinned": "Folder name used for {responsetype} for pinned posts. The value is capitalized (only its first letter kept uppercase); empty falls back to the type name.",
    "responsetype.streams": "Folder name used for {responsetype} for streams. The value is capitalized (only its first letter kept uppercase); empty falls back to the type name.",
}

# --------------------------------------------------------------------------
# database
# --------------------------------------------------------------------------

DATABASE_NOTES = "Each creator has one SQLite file, user_data.db, in the folder given by the metadata config value (default {configpath}/{profile}/.data/{model_id}); ofscraper/classes/placeholder.py databasePlaceholder.databasePathHelper fills in the placeholders (username, model_username, first_letter, model_id, plus the common ones) and appends user_data.db. Connections are opened per operation by ofscraper/db/operations_/wrapper.py in WAL mode (so user_data.db-wal and -shm files sit next to it), with writes serialised through one worker thread and retried on 'database is locked'. Backups go to a backup folder beside the database (ofscraper/db/backup.py): at the start of a per-creator run table_init_create copies it to backup/user_data_copy_N.db, rotating N through 1 to 5, when the DBINTERVAL setting (default 86400 seconds) has passed since the last copy or the backup folder is empty; before any pending schema migration it also writes backup/old_schema_{model_id}_{timestamp}_db_backup.db (old_schema_db_backup.db when there is no model id), checks the copy has the same size, and restores it if the migration raises. The Merge Databases menu option (ofscraper/db/merge.py) creates and migrates a target user_data.db, then copies in rows from every user_data.db found under a chosen folder, skipping rows whose key is already present; each source must contain exactly one numeric model id in profiles. Fansly runs use separate files: when the metadata template has no site-specific field (save_location, root, site_name, model_id and their aliases), a Fansly subfolder is added before user_data.db so Fansly rows do not land in the OnlyFans file, and Fansly databases carry a schema_flags row site=fansly. The db command and hash-based duplicate checks only read the database."

TABLES = {
    "medias": {
        "summary": "One row per media item (image, video, audio) seen in a post, message, story or other area, holding its API metadata and, once handled, where it was saved and whether it counts as downloaded.",
        "written_by": "Scraping (any action-mode run: download, like/unlike; plus the metadata command, manual/url mode and the check/table mode) calls batch_mediainsert (ofscraper/db/operations_/media.py) from ofscraper/data/posts/post.py, commands/manual.py and commands/check.py: (media_id, post_id) pairs not yet in the table are INSERTed with API fields only; pairs already present get their API fields (link, linked, api_type, media_type, preview, created_at, posted_at, duration, unlocked) UPDATEd on every scrape, not only in metadata mode. After a file is written, mark_media_as_downloaded (main_download.py, alt_download.py for DRM, fansly_stream_download.py, and downloadmanager._force_download for zero-size or known-bad URLs) re-applies the API fields and sets directory, filename, size, downloaded and hash; that download UPDATE matches on media_id and model_id only, so every row for that media under the creator is updated. The metadata command (commands/metadata/manager.py) uses the same function to set download status/filename from files on disk without downloading. batch_set_media_downloaded sets unlocked=0 (despite its name it does not touch downloaded): post.py clean_stray_media calls it on every scrape for not-yet-downloaded unlocked rows whose post was just scraped but whose media id was not returned, and the metadata command calls it for strays when mark_stray is on. The offline tool python -m ofscraper.commands.recover_collisions sets downloaded=0 for rows that share one file path, with an undo file. Migration rebuilds the table once (rebuild_media_table) and the Merge Databases menu copies rows in. Nothing in the app DELETEs rows. Unique key: UNIQUE (media_id, model_id, post_id). There is no ON CONFLICT clause: the code reads existing (media_id, post_id) pairs and chooses INSERT or UPDATE itself. Merge dedupes on (media_id, model_id) only.",
        "columns": {
            "id": "Row id (INTEGER PRIMARY KEY), internal only.",
            "media_id": "Site media id.",
            "post_id": "Id of the post, message or story the media belongs to.",
            "link": "Download URL, or the MPD manifest URL for DRM video; NULL when the API gave neither.",
            "directory": "Folder the file was saved to (set on download or by the metadata command).",
            "filename": "File name the media was saved under.",
            "size": "Saved file size in bytes.",
            "api_type": "Area the media came from, capitalised response type (Timeline, Archived, Pinned, Streams, Messages, Stories, Highlights, Paid, Profile, etc.).",
            "media_type": "Capitalised media type (Images, Videos, Audios, etc.).",
            "preview": "1 if the media is a preview (OnlyFans: the post carries preview media; Fansly: the item is flagged isPreview), else 0.",
            "linked": "1 if the API gave a URL or MPD for the media, else 0.",
            "downloaded": "1 once the media counts as downloaded (file saved, forced, or marked by the metadata command); 0 or NULL otherwise. Used to skip already-downloaded media.",
            "created_at": "Media creation time from the API (createdAt, else postedAt, else the post date).",
            "posted_at": "Date of the parent post or message.",
            "duration": "Media duration as a formatted string, NULL when unknown.",
            "unlocked": "1 if the account can view the media (API canView and a link exists); set to 0 when stray-media cleanup decides the item is gone.",
            "hash": "File hash recorded at download (when hashing is enabled); used to find duplicate files.",
            "model_id": "Creator account id the row belongs to.",
        },
    },
    "posts": {
        "summary": "One row per timeline, pinned, archived, streams, paid or label post seen for the creator.",
        "written_by": "make_post_table_changes (ofscraper/db/operations_/posts.py) runs on every scrape from ofscraper/data/posts/post.py (timeline, pinned, archived, streams and paid areas, and the posts inside labels via make_label_table_changes), from manual/url mode and from the check command via make_changes_to_content_tables. New post ids are INSERTed; existing rows are UPDATEd (and is_deleted reset to 0) only when a metadata mode is set, i.e. under the metadata command. mark_post_as_deleted sets is_deleted=1 for posts the timeline, archived and streams scanners (ofscraper/data/api/) expected from the database but the API skipped past. Migration rebuilds the table once; the Merge Databases menu copies rows in. No DELETEs. Unique key: UNIQUE (post_id, model_id). The code looks up existing post ids (across all model_ids in the file) and chooses INSERT or UPDATE itself.",
        "columns": {
            "id": "Row id (INTEGER PRIMARY KEY), internal only.",
            "post_id": "Site post id.",
            "text": "Post text, sanitised first when the sanitize-db-text option is on.",
            "price": "Post price (0 when free).",
            "paid": "Truthy when the post is open or opened, has viewable media, or has a price.",
            "archived": "1 if the API marks the post archived.",
            "pinned": "1 if the API marks the post pinned.",
            "stream": "1 if the post has a stream id (a streams post).",
            "opened": "1 if the API marks the post opened.",
            "created_at": "Post date (postedAt, else createdAt).",
            "model_id": "Creator account id the row belongs to.",
            "is_deleted": "1 when a scan decided the post no longer exists on the site; such posts are left out of the date lookups that drive later scans. Default 0.",
        },
    },
    "messages": {
        "summary": "One row per direct message seen in the chat with the creator, from either side.",
        "written_by": "make_messages_table_changes (ofscraper/db/operations_/messages.py) runs when the Messages area is scraped (ofscraper/data/posts/post.py process_messages), and from manual/url mode and the check command. New message ids are INSERTed; existing rows are UPDATEd (and is_deleted reset to 0) only under the metadata command. The messages scanner (ofscraper/data/api/messages.py) sets is_deleted=1 for messages it expected but the API skipped past. Migration rebuilds the table once, in one transaction that keeps every column including is_deleted; the Merge Databases menu copies rows in, is_deleted included. No DELETEs. Unique key: UNIQUE (post_id, model_id). Application-side INSERT-or-UPDATE based on existing message ids.",
        "columns": {
            "id": "Row id (INTEGER PRIMARY KEY), internal only.",
            "post_id": "Site message id.",
            "text": "Message text, sanitised first when the sanitize-db-text option is on.",
            "price": "Message price (0 when free).",
            "paid": "Truthy when the message is open or opened, has viewable media, or has a price.",
            "archived": "1 if the API marks the message archived (normally 0).",
            "created_at": "Message date.",
            "user_id": "Id of the sender (fromUser); lets you tell the creator's messages from the account's own.",
            "model_id": "Creator account id the chat belongs to.",
            "is_deleted": "1 when a scan decided the message no longer exists. Default 0.",
        },
    },
    "stories": {
        "summary": "One row per story or highlight story seen for the creator.",
        "written_by": "make_stories_table_changes (ofscraper/db/operations_/stories.py) runs when the Stories or Highlights areas are scraped (ofscraper/data/posts/post.py), and from manual/url mode and the check command. New ids are INSERTed; existing rows are UPDATEd only under the metadata command. Migration rebuilds the table once; the Merge Databases menu copies rows in. No DELETEs. Unique key: UNIQUE (post_id, model_id). Application-side insert of ids not already present.",
        "columns": {
            "id": "Row id (INTEGER PRIMARY KEY), internal only.",
            "post_id": "Site story id.",
            "text": "Story text, else its title, else an empty string.",
            "price": "Price (normally 0).",
            "paid": "Paid/open flag as computed for posts.",
            "archived": "Archived flag from the API (normally 0).",
            "created_at": "Story date.",
            "model_id": "Creator account id the row belongs to.",
        },
    },
    "labels": {
        "summary": "Links the creator's post labels (collections) to posts: one row per (label, post) pair.",
        "written_by": "make_label_table_changes (ofscraper/db/operations_/labels.py) runs when the Labels area is scraped (ofscraper/data/posts/post.py process_labels), and from the check command. For each label, posts not yet recorded under it are INSERTed; existing pairs are UPDATEd only under the metadata command. It then passes the labelled posts to make_post_table_changes, so they also land in posts. Migration rebuilds the table once; the Merge Databases menu copies rows in. No DELETEs. Unique key: UNIQUE (post_id, label_id, model_id). Application-side INSERT-or-UPDATE per label.",
        "columns": {
            "id": "Row id (INTEGER PRIMARY KEY), internal only.",
            "label_id": "Site label id.",
            "name": "Label name.",
            "type": "Label type from the API.",
            "post_id": "Id of a post carrying the label.",
            "model_id": "Creator account id the row belongs to.",
        },
    },
    "profiles": {
        "summary": "Usernames the creator account has been seen under in this database.",
        "written_by": "write_profile_table (ofscraper/db/operations_/profile.py), called from table_init_create in ofscraper/db/operations.py at the start of every per-creator run (action mode, metadata command, manual/url mode, check command), adds a row each time the account is seen under a new username. Migration rebuilds the table once (rebuild_profiles_table, flag profile_username_constraint_modified); the Merge Databases menu copies rows in. Merge and migration use it to find the single model id of an old database. Unique key: UNIQUE (user_id, username); the INSERT uses WHERE NOT EXISTS, so repeat runs under the same name add nothing.",
        "columns": {
            "id": "Row id (INTEGER PRIMARY KEY), internal only.",
            "user_id": "Creator account id (same value as model_id elsewhere; named user_id for legacy reasons).",
            "username": "Username the account had when seen.",
        },
    },
    "models": {
        "summary": "The creator account ids whose data is stored in this database.",
        "written_by": "write_models_table (ofscraper/db/operations_/profile.py), called from table_init_create on every per-creator run, inserts the model id if it is not already present. The Merge Databases menu adds the model id of each merged database. Unique key: UNIQUE (model_id); the INSERT uses WHERE NOT EXISTS.",
        "columns": {
            "id": "Row id (INTEGER PRIMARY KEY), internal only.",
            "model_id": "Creator account id.",
        },
    },
    "products": {
        "summary": "Legacy table for paid products; created and migrated, but no current code path writes rows to it.",
        "written_by": "Only created (create_products_table), rebuilt once by migration (rebuild_products_table) and copied by the Merge Databases menu (ofscraper/db/operations_/others.py, ofscraper/db/merge.py). No scrape, download or command inserts rows, so it is normally empty. The rebuild copies every row into the new table in one transaction before the old one is dropped. Unique key: UNIQUE (post_id, model_id).",
        "columns": {
            "id": "Row id (INTEGER PRIMARY KEY), internal only.",
            "post_id": "Id of the product or its post.",
            "text": "Product text.",
            "price": "Price.",
            "paid": "Paid flag.",
            "archived": "Archived flag.",
            "created_at": "Creation date.",
            "title": "Product title.",
            "model_id": "Creator account id the row belongs to.",
        },
    },
    "others": {
        "summary": "Legacy table for content outside the main areas; created and migrated, but no current code path writes rows to it.",
        "written_by": "Only created (create_others_table), rebuilt once by migration (rebuild_others_table) and copied by the Merge Databases menu. No scrape, download or command inserts rows, so it is normally empty. As with products, the rebuild copies every row into the new table in one transaction before the old one is dropped. Unique key: UNIQUE (post_id, model_id).",
        "columns": {
            "id": "Row id (INTEGER PRIMARY KEY), internal only.",
            "post_id": "Id of the item.",
            "text": "Text.",
            "price": "Price.",
            "paid": "Paid flag.",
            "archived": "Archived flag.",
            "created_at": "Creation date.",
            "model_id": "Creator account id the row belongs to.",
        },
    },
    "schema_flags": {
        "summary": "Key/value markers recording which schema migrations have run on this file, plus the site the database belongs to.",
        "written_by": "ofscraper/db/transition.py modify_tables (called from table_init_create on every per-creator run, and by merge) compares the flags with the list in ofscraper/db/difference.py; for each missing flag it runs the matching change and then add_flag_schema writes flag_name=<flag>, flag_value=1. A brand-new database has no flags, so it goes through every rebuild once too. write_site_flag writes flag_name='site', flag_value='fansly' on each Fansly run; OnlyFans databases get no site row. Unique key: flag_name is the PRIMARY KEY; writes use INSERT OR REPLACE. Flag names: media_hash = medias.hash column added.; media_model_id = medias.model_id column added.; media_posted_at = medias.posted_at column added.; media_duration = medias.duration column added.; media_unlocked = medias.unlocked column added.; posts_model_id = posts.model_id column added.; posts_pinned = posts.pinned column added.; posts_stream = posts.stream column added.; posts_opened = posts.opened column added.; posts_is_deleted = posts.is_deleted column added.; messages_model_id = messages.model_id column added.; messages_is_deleted = messages.is_deleted column added.; stories_model_id = stories.model_id column added.; labels_model_id = labels.model_id column added.; products_model_id = products.model_id column added.; other_model_id = others.model_id column added.; profile_username_constraint_modified = profiles rebuilt with UNIQUE (user_id, username).; stories_model_id_constraint_added = stories rebuilt with UNIQUE (post_id, model_id).; posts_model_id_constraint_added = posts rebuilt with UNIQUE (post_id, model_id).; messages_model_id_constraint_added = messages rebuilt with UNIQUE (post_id, model_id).; labels_model_id_constraint_added = labels rebuilt with UNIQUE (post_id, label_id, model_id).; others_model_id_constraint_added = others rebuilt with UNIQUE (post_id, model_id).; products_model_id_constraint_added = products rebuilt with UNIQUE (post_id, model_id).; media_post_id_constraint_added = medias rebuilt with UNIQUE (media_id, model_id, post_id); written together with media_bool_changes.; media_bool_changes = medias rebuilt with its boolean columns; written together with media_post_id_constraint_added (either missing triggers the one rebuild).; site = Not a migration flag: value is the site name ('fansly') for a Fansly database; absent for OnlyFans.",
        "columns": {
            "flag_name": "Migration flag name (see flags) or 'site'.",
            "flag_value": "1 for a completed migration step (only rows with value 1 count as done); the site name for the 'site' row.",
        },
    },
}
