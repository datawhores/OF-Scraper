"""
Checks of the file_options values that names are built from, for a
hand-edited config.json: each problem is logged once, naming the setting,
before downloads start, instead of failing or changing every file quietly.
"""

import json
import logging
import platform
import re
import string

log = logging.getLogger("shared")

# can't be in a file name on Windows; a slash would add a folder
NOT_IN_A_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')

TEXT_TYPES = ("letter", "word")


def _with_aliases(names):
    """each name and its underscore-free alias, as add_no_underline adds"""
    return frozenset(names) | frozenset(name.replace("_", "") for name in names)


# what dir_format can use: the names Placeholders.getmediadir formats with
DIR_PLACEHOLDERS = _with_aliases(
    {
        "config_path", "profile", "site_name", "save_location", "my_id",
        "my_username", "root", "user_name", "model_id", "post_id", "media_id",
        "first_letter", "media_type", "value", "date", "year", "month", "day",
        "model_username", "response_type", "label", "download_type",
        "modelObj", "quality", "file_name", "original_filename",
        "only_file_name", "only_filename", "text", "config", "args",
        "current_price", "regular_price", "promo_price", "renewal_price",
    }
)
# file_format has {ext} too
FILE_PLACEHOLDERS = DIR_PLACEHOLDERS | {"ext"}

# the type_options names livestream recordings use
LIVE_TYPE_KEYS = ("livestreams", "live")
# what livestream templates can use: the names placeholder._live_path fills
LIVE_PLACEHOLDERS = _with_aliases(
    {
        "config_path", "profile", "site_name", "save_location", "my_id",
        "my_username", "root", "user_name", "username", "model_username",
        "model_id", "first_letter", "response_type", "media_type", "date",
        "timestamp", "year", "month", "day", "ext", "config", "args",
    }
)


def text_type(value):
    """letter or word, matched without regard to case; None for anything else"""
    if isinstance(value, str) and value.strip().lower() in TEXT_TYPES:
        return value.strip().lower()
    return None


# outside Windows a name can hold all but "/" (it adds a folder) and NUL
NOT_IN_A_POSIX_NAME = re.compile(r"[/\x00]")


def on_windows():
    return platform.system() == "Windows"


def name_safe(text):
    """text without the characters a file name can't hold on this system:
    on Windows NOT_IN_A_NAME; elsewhere only "/" and NUL, so a ":" from
    HH:mm in the date setting stays, as in names made before"""
    banned = NOT_IN_A_NAME if on_windows() else NOT_IN_A_POSIX_NAME
    return banned.sub("", str(text))


# "/x", "\x", "C:", "C:/x" or "~/x": dir_format is placed under save_location
# anyway, so such a path doesn't choose where downloads go
FULL_PATH = re.compile(r"[/\\~]|[A-Za-z]:")


def space_replacer_ok(value):
    # JSON can hold a number or a list there, which can't replace a space
    return isinstance(value, str) and not NOT_IN_A_NAME.search(value)


DOWNLOAD_EFFECT = "Each file will fail to download until it's fixed"
LIVE_EFFECT = "Livestreams are recorded under the default name until it's fixed"


def template_problem(template, known, effect=DOWNLOAD_EFFECT):
    """why a dir_format or file_format template can't be used, or None"""
    try:
        fields = [
            field for _, field, _, _ in string.Formatter().parse(template)
            if field is not None
        ]
    except ValueError as E:
        return f"isn't a valid template ({E})"
    if "" in fields or any(field.isdigit() for field in fields):
        return "isn't a valid template ({} needs a placeholder name)"
    unknown = []
    for field in fields:
        # {modelObj.name} and {config[file_options][date]} use their first name
        name = re.match(r"[^.\[]*", field).group(0)
        if name not in known and f"{{{name}}}" not in unknown:
            unknown.append(f"{{{name}}}")
    if unknown:
        return (
            f"has {'unknown placeholders' if len(unknown) > 1 else 'an unknown placeholder'}:"
            f" {', '.join(unknown)}. {effect}"
        )
    return None


def templates():
    """(setting, template, placeholders it can use, what happens when it
    can't be filled in) for every folder and file name template: the
    file_options ones, the live_options ones and each type_options one set"""
    import ofscraper.utils.config.data as data

    out = [
        ("file_options.dir_format", data.get_dirformat(), DIR_PLACEHOLDERS, DOWNLOAD_EFFECT),
        ("file_options.file_format", data.get_fileformat(), FILE_PLACEHOLDERS, DOWNLOAD_EFFECT),
        ("live_options.dir_format", data.get_live_dirformat(), LIVE_PLACEHOLDERS, LIVE_EFFECT),
        ("live_options.file_format", data.get_live_fileformat(), LIVE_PLACEHOLDERS, LIVE_EFFECT),
    ]
    for name, section in data.get_type_options().items():
        live = name.strip().lower() in LIVE_TYPE_KEYS
        for key, known in (("dir_format", DIR_PLACEHOLDERS), ("file_format", FILE_PLACEHOLDERS)):
            if section.get(key):
                out.append((
                    f"type_options.{name}.{key}", section[key],
                    LIVE_PLACEHOLDERS if live else known, LIVE_EFFECT if live else DOWNLOAD_EFFECT,
                ))
    return out


def problems():
    """one line for each file_options value that's used differently from
    what it says, or that will fail"""
    import ofscraper.utils.config.data as data
    import ofscraper.utils.settings as settings

    # an unknown text_type_default isn't here: get_textType falls back to the
    # default, so the startup rewrite of config.json replaces it, and that
    # rewrite is what reports a replaced value
    out = []
    merged = settings.get_settings()
    args = settings.get_args()
    if isinstance(merged.text_length, int) and merged.text_length < 0:
        setting = (
            "--textlength" if args.textlength is not None else "file_options.textlength"
        )
        out.append(
            f"{setting} is {merged.text_length}; a negative length is"
            " read as 0, no limit"
        )
    chosen = args.space_replacer or data.get_spacereplacer()
    if not space_replacer_ok(chosen):
        setting = (
            "--space-replacer" if args.space_replacer else "file_options.space_replacer"
        )
        why = (
            "has characters a file name can't hold"
            if isinstance(chosen, str)
            else "isn't text"
        )
        out.append(
            f"{setting} is {json.dumps(chosen)}, which {why},"
            " so a space is used"
        )
    dated = False
    for setting, template, known, effect in templates():
        problem = template_problem(str(template), known, effect)
        if problem:
            out.append(f"{setting} {json.dumps(template)} {problem}")
        if not setting.endswith(".dir_format") or not isinstance(template, str):
            continue
        if FULL_PATH.match(template):
            section = setting.rsplit(".", 1)[0]
            where = "save_location" if section == "file_options" else f"{section}.save_location"
            out.append(
                f"{setting} {json.dumps(template)} is a full path, but"
                f" dir_format is always placed under save_location. Set {where}"
                " to choose where downloads go"
            )
        # livestream folders take the start time, not the date setting
        if known is not LIVE_PLACEHOLDERS and re.search(r"\{date[}:!]", template):
            dated = True
    # before, a "/" in the date (and "\" on Windows) made nested folders
    date = data.get_date()
    separators = "/\\" if on_windows() else "/"
    if dated and isinstance(date, str) and any(sep in date for sep in separators):
        out.append(
            f"file_options.date {json.dumps(date)} has a folder separator, but {{date}}"
            " in dir_format now fills one folder, so dates no longer nest. Use"
            " {year}/{month}/{day} in dir_format for nested date folders"
        )
    names = _type_names()
    for name in data.get_type_options():
        if name.strip().lower() not in names:
            out.append(
                f"type_options.{name} isn't a post area, media type or livestreams,"
                " so it's never used"
            )
    return out


# what a type_options entry can be named: a post's area as Post.responsetype
# gives it (and its older spellings), a media type, or livestreams
POST_AREAS = {
    "timeline", "post", "posts", "pinned", "archived", "message", "messages",
    "paid", "purchased", "stories", "highlights", "profile", "streams", "labels",
}
MEDIA_TYPES = {"images", "videos", "audios", "text"}


def _type_names():
    """the names a type_options entry can match, lowercased: also the folder
    names the responsetype section gives each area"""
    import ofscraper.utils.config.file as config_file
    import ofscraper.utils.config.schema as schema

    folders = schema.get_current_config_schema(config_file.open_config())["responsetype"]
    return (
        POST_AREAS | MEDIA_TYPES | set(LIVE_TYPE_KEYS)
        | {str(folder).strip().lower() for folder in folders.values() if folder}
    )


def report():
    try:
        lines = problems()
    except Exception as E:
        # a check must never stop the run
        log.debug(f"file_options check failed: {E}")
        return
    for line in lines:
        log.warning(line)
