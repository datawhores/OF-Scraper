import json
import logging
import pathlib

from humanfriendly import parse_size

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.binaries as binaries
import ofscraper.utils.config.schema as schema
import ofscraper.utils.console as console_
import ofscraper.utils.paths.common as common_paths

console = console_.get_shared_console()
log = logging.getLogger("shared")


def make_config(config=None):
    config = config or schema.get_current_config_schema()

    if isinstance(config, str):
        config = json.loads(config)

    p = pathlib.Path(common_paths.get_config_path())
    if not p.parent.is_dir():
        p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w") as f:
        f.write(json.dumps(config, indent=4))
    console.print(f"config file created at {p}")


def open_config():
    p = pathlib.Path(common_paths.get_config_path())
    if not p.parent.is_dir():
        p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "r") as f:
        configText = f.read()
        config = json.loads(configText)
        return config["config"]


def auto_update_config(config: dict) -> dict:
    log.warning("Auto updating config...")
    new_config = schema.get_current_config_schema(config)

    p = pathlib.Path(common_paths.get_config_path())
    if not p.parent.is_dir():
        p.parent.mkdir(parents=True, exist_ok=True)

    with open(p, "w") as f:
        f.write(json.dumps(new_config, indent=4))

    return new_config
