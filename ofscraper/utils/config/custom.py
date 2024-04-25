import json

import ofscraper.utils.config.file as config_file


def get_custom(config=None):
    if config is False:
        return None
    config = config or config_file.open_config()
    value = (
        config.get("custom")
        or config.get("advanced_options", {}).get("custom_values")
        or config.get("advanced_options", {}).get("custom")
    )
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value
