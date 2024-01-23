import ofscraper.utils.config.context as config_context
import ofscraper.utils.config.file as config_file


def get_custom():
    with config_context.config_context():
        config = config_file.open_config()
        if config == None:
            return None
        return config.get("custom") or config.get("advanced_options", {}).get(
            "custom_values"
        )
