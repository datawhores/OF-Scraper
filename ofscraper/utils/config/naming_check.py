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


def template_problem(template, known):
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
            f" {', '.join(unknown)}. Each file will fail to download until it's fixed"
        )
    return None


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
    for key, template, known in (
        ("dir_format", data.get_dirformat(), DIR_PLACEHOLDERS),
        ("file_format", data.get_fileformat(), FILE_PLACEHOLDERS),
    ):
        problem = template_problem(str(template), known)
        if problem:
            out.append(f"file_options.{key} {json.dumps(template)} {problem}")
    dir_format = data.get_dirformat()
    if isinstance(dir_format, str) and FULL_PATH.match(dir_format):
        out.append(
            f"file_options.dir_format {json.dumps(dir_format)} is a full path, but"
            " dir_format is always placed under save_location. Set save_location"
            " to choose where downloads go"
        )
    # before, a "/" in the date (and "\" on Windows) made nested folders
    date = data.get_date()
    separators = "/\\" if on_windows() else "/"
    if (
        isinstance(dir_format, str)
        and isinstance(date, str)
        and re.search(r"\{date[}:!]", dir_format)
        and any(sep in date for sep in separators)
    ):
        out.append(
            f"file_options.date {json.dumps(date)} has a folder separator, but {{date}}"
            " in dir_format now fills one folder, so dates no longer nest. Use"
            " {year}/{month}/{day} in dir_format for nested date folders"
        )
    return out


def report():
    try:
        lines = problems()
    except Exception as E:
        # a check must never stop the run
        log.debug(f"file_options check failed: {E}")
        return
    for line in lines:
        log.warning(line)
