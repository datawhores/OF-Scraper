import json
import logging
import pathlib
import re

import ofscraper.utils.config.schema as schema
import ofscraper.utils.console as console_
import ofscraper.utils.paths.common as common_paths

console = console_.get_shared_console()
log = logging.getLogger("shared")


def make_config(config=False):
    config = schema.get_current_config_schema(config=config)
    if isinstance(config, str):
        config = json_loads(config)

    p = pathlib.Path(common_paths.get_config_path())
    if not p.parent.is_dir():
        p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w") as f:
        f.write(json.dumps(config, indent=4))
    console.print(f"config file created at {p}")


def make_config_original():
    make_config(config=False)


def open_config():
    import ofscraper.utils.config.utils.context as config_context
    with config_context.config_context():
        configText = config_string()
        config = json_loads(configText)
        if config.get("config"):
            return config.get("config")
        return config


def config_string():
    p = pathlib.Path(common_paths.get_config_path())
    with open(p, "r") as f:
        configText = f.read()
    return configText


def write_config(updated_config):
    if isinstance(updated_config, str):
        updated_config = json_loads(updated_config)
    if updated_config.get("config"):
        updated_config = updated_config["config"]
    p = common_paths.get_config_path()
    if not p.parent.is_dir():
        p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        f.write(json.dumps(updated_config, indent=4))


def auto_update_config(config: dict) -> dict:
    log.warning("Auto updating config...")
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
