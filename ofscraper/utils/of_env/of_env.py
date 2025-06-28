from ofscraper.utils.of_env import get_all_configs
import os


def getattr(val):
    """
    Retrieves a configuration value.
    Order of precedence: Environment Variable > Custom Config > Default Config.
    """
    # Load all settings if not already loaded
    settings = get_all_configs()

    # 1. Check Environment Variable
    env_val = os.environ.get(val)
    if env_val is not None:
        return env_val
    if val in settings:  # Check if key exists in the aggregated settings
        return settings.get(val)
    return None  # Or raise KeyError(f"Configuration key '{val}' not found.")


def getkeys():
    return get_all_configs()
