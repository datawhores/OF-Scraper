import json
import logging
import pathlib
import re

from humanfriendly import InvalidSize, parse_size

from ofscraper.utils.markup import escape_text

import ofscraper.utils.config.data as data
import ofscraper.utils.config.schema as schema
import ofscraper.utils.console as console_
import ofscraper.utils.encoding as encoding
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths

console = console_.get_shared_console()
log = logging.getLogger("shared")


def make_config(config=False):
    if config is False:
        # a new file holds the built-in defaults, not environment values
        with of_env.builtin_defaults():
            config = schema.get_current_config_schema(config=config)
    else:
        config = schema.get_current_config_schema(config=config)
    if isinstance(config, str):
        config = json_loads(config)

    p = pathlib.Path(common_paths.get_config_path())
    if not p.parent.is_dir():
        p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(config, indent=4))
    console.print(f"config file created at {escape_text(p)}")


def make_config_original():
    make_config(config=False)


class NotAnObjectError(ValueError):
    """config.json is valid JSON but doesn't hold an object of settings"""


def _json_type(value):
    if isinstance(value, bool):
        return "true or false"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, (int, float)):
        return "a number"
    return type(value).__name__


def unwrap(config):
    """
    The settings in a parsed config.json: the object itself, or the one under
    "config" in the older {"config": {...}} form (an empty "config" is
    ignored, as before). Raises NotAnObjectError when either isn't an object.
    """
    if not isinstance(config, dict):
        raise NotAnObjectError(
            f"config.json holds {_json_type(config)}, not an object of settings"
        )
    wrapped = config.get("config")
    if not wrapped:
        return config
    if not isinstance(wrapped, dict):
        raise NotAnObjectError(
            f'"config" in config.json holds {_json_type(wrapped)}, '
            "not an object of settings"
        )
    return wrapped


def checked(configText):
    """The settings in config.json's text, as the run accepts them: strict
    JSON holding an object of settings. Raises json.JSONDecodeError or
    NotAnObjectError for a file the run stops at and asks to be fixed
    (config_context); json_loads's repair of backslashes is not applied."""
    return unwrap(json.loads(configText))


def open_config():
    import ofscraper.utils.config.utils.context as config_context

    with config_context.config_context():
        configText = config_string()
        return unwrap(json_loads(configText))


def config_string():
    p = pathlib.Path(common_paths.get_config_path())
    return encoding.read_text_file(p)


def write_config(updated_config):
    if isinstance(updated_config, str):
        updated_config = json_loads(updated_config)
    updated_config = unwrap(updated_config)
    p = common_paths.get_config_path()
    if not p.parent.is_dir():
        p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(updated_config, indent=4))


# where database_url has been written: its older top-level name, then its own
DATABASE_URL_PATHS = ("database_url", "advanced_options.database_url")


def _database_url_written(config):
    """The path of what a config.json holds other than the note where the
    note goes: an address someone wrote there, which isn't read. Else None."""
    config = config.get("config") or config
    for path in DATABASE_URL_PATHS:
        written = data._lookup(config, path)
        if written:
            return path if written != data.DATABASE_URL_NOTE else None
    return None


def auto_update_config(config: dict) -> dict:
    log.info("Auto updating config...")
    written = _database_url_written(config)
    if written:
        # said without the value: it may hold a password
        _notes.append(
            f"{written} in config.json is not read, and"
            " what was written there has been replaced by a note. To use"
            " PostgreSQL, set the OFSC_DATABASE_URL environment variable"
            " (see POSTGRESQL.md)."
        )
    # keys missing from the file get the built-in defaults, not environment
    # values; the environment still applies at runtime
    with of_env.builtin_defaults():
        with data._recording_reads() as reads:
            new_config = schema.get_current_config_schema(config)
        defaults = schema.get_current_config_schema(config=False)
    _notes.extend(rewrite_notes(unwrap(config), new_config, defaults, reads))
    if log.handlers:
        log_notes()
    write_config(new_config)
    return new_config


# what auto_update_config dropped or replaced, kept until the shared log is
# set up: the config is first read before it is, and a warning then reaches
# only the console, never the log file people send when asking for help
_notes = []


def log_notes():
    while _notes:
        log.warning(_notes.pop(0))


def _leaves(config):
    """{"key" or "section.key": value} for a config's settings"""
    out = {}
    for key, value in config.items():
        # an empty section is kept, so one nothing reads is named too
        if isinstance(value, dict) and value:
            out.update({f"{key}.{sub}": v for sub, v in value.items()})
        else:
            out[key] = value
    return out


def rewrite_notes(old, new, defaults, reads):
    """
    One line for each key of old that the rewrite to new drops without any
    getter reading it, and each value it replaces with the default. The old
    values aren't repeated, only their type: they can be auth values pasted in.
    """
    notes = []
    new_leaves, default_leaves = _leaves(new), _leaves(defaults)
    for path, value in _leaves(old).items():
        # has its own warning, without the address (it holds a password)
        if path in DATABASE_URL_PATHS:
            continue
        if isinstance(new.get(path), dict):
            if value == {}:
                continue  # an empty section, filled in with the defaults
            notes.append(
                f'config.json: "{path}" should hold settings but holds'
                f" {_json_type(value)}, so its settings were reset to the defaults"
            )
        elif path not in new_leaves:
            if path not in reads:
                notes.append(
                    f'config.json: "{path}" isn\'t read (not a setting, or an older'
                    " name for one that's set under its current name), so it was"
                    " removed from the file"
                )
        elif path not in reads:
            notes.append(
                f'config.json: "{path}" isn\'t read, because an older name for the'
                " same setting is also set and is used instead. The older name was"
                f" removed from the file, and its value saved here"
            )
        elif _replaced(value, new_leaves[path], default_leaves.get(path)):
            notes.append(
                # the type, not the value: it can be an auth value pasted in
                f'config.json: "{path}" held {_json_type(value)} it doesn\'t take,'
                f" so the default {json.dumps(new_leaves[path])} is used and saved"
            )
    return notes


def _replaced(old, new, default):
    """old was swapped for the default, not unset or saved in another form"""
    if old in (None, "") or old == new or new != default:
        return False
    return not _same_setting(old, new)


def _same_setting(old, new):
    """whether old is new written another way: "Images,Audios,Videos" for a
    list, "0GB" for a size, "Manual" for "manual"
    """
    if isinstance(new, list):
        items = old.split(",") if isinstance(old, str) else old
        if not isinstance(items, list):
            return False
        return [str(x).strip().lower() for x in items] == [str(x).lower() for x in new]
    if isinstance(new, (int, float)) and not isinstance(new, bool):
        try:
            return parse_size(str(old)) == new
        except (ValueError, TypeError, InvalidSize):
            pass  # compared as text below
    return str(old).strip().lower() == str(new).lower()


def json_loads(configText):
    try:
        config = json.loads(configText)
    except json.JSONDecodeError:
        configText = re.sub("\\\\+", "/", configText)
        config = json.loads(configText)
    return config
