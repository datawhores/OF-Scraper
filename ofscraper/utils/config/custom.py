import json

import ofscraper.utils.config.context as config_context
import ofscraper.utils.config.file as config_file


def get_custom(config=None):
    with config_context.config_context():
        if config == False:
            return None
        config = config or config_file.open_config()
        value = config.get("custom") or config.get("advanced_options", {}).get(
            "custom_values"
        )
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value
