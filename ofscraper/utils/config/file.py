import json
import logging
import pathlib
import re

from ofscraper.utils.markup import escape_text

import ofscraper.utils.config.schema as schema
import ofscraper.utils.console as console_
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

    with open(p, "w") as f:
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


def open_config():
    import ofscraper.utils.config.utils.context as config_context

    with config_context.config_context():
        configText = config_string()
        return unwrap(json_loads(configText))


def config_string():
    p = pathlib.Path(common_paths.get_config_path())
    with open(p, "r") as f:
        configText = f.read()
    return configText


def write_config(updated_config):
    if isinstance(updated_config, str):
        updated_config = json_loads(updated_config)
    updated_config = unwrap(updated_config)
    p = common_paths.get_config_path()
    if not p.parent.is_dir():
        p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        f.write(json.dumps(updated_config, indent=4))


def auto_update_config(config: dict) -> dict:
    log.info("Auto updating config...")
    # keys missing from the file get the built-in defaults, not environment
    # values; the environment still applies at runtime
    with of_env.builtin_defaults():
        new_config = schema.get_current_config_schema(config)
    write_config(new_config)
    return new_config


def json_loads(configText):
    try:
        config = json.loads(configText)
    except json.JSONDecodeError:
        configText = re.sub("\\\\+", "/", configText)
        config = json.loads(configText)
    return config
