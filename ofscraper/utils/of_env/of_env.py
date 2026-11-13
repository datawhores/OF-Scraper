from ofscraper.utils.of_env import get_all_configs
import os


from ofscraper.utils.of_env.values.live import OPTIONAL_BOOLS
import contextlib
import json
import logging

log = logging.getLogger("shared")
# (key, value) pairs already warned about
_warned = set()


def _as_type_of(text, current):
    """
    Convert an environment variable's text to the type of the configured
    value, the way the loaders in values/ convert their own variables.
    """
    if isinstance(current, bool):
        return text.strip().lower() in ("true", "1")
    if isinstance(current, (int, float)):
        return type(current)(text)
    if isinstance(current, (list, tuple, set, frozenset)):
        # A JSON array, or comma-separated text. Env files (load.py) write
        # lists as Python text, e.g. ['a', 'b'], which isn't read: that needs
        # #168, which makes them write JSON
        if text.strip().startswith("["):
            items = json.loads(text)
        else:
            items = [s.strip() for s in text.split(",") if s.strip()]
        return type(current)(items)
    if isinstance(current, dict):
        # JSON only; from an env file this also needs #168
        return json.loads(text)
    return text


def getattr(val, default=None):
    """
    Retrieves a configuration value.
    Order of precedence: Environment Variable > Custom Config > Default Config.
    Returns default if the key isn't set anywhere.
    """
    # Load all settings if not already loaded
    config_dict = get_all_configs()
    # 1. Check Environment Variable
    env_val = os.environ.get(val)
    if env_val is not None:
        if val not in config_dict:
            return env_val
        current = config_dict[val]
        if current is None and val in OPTIONAL_BOOLS:
            current = False  # a switch with no default: convert as a bool
        try:
            return _as_type_of(env_val, current)
        except (TypeError, ValueError) as E:
            # once per key and value: settings are read again and again
            if (val, env_val) not in _warned:
                _warned.add((val, env_val))
                log.warning(
                    f"{val}: can't use the environment value {env_val!r} ({E}), "
                    f"using {config_dict[val]!r}"
                )
            return config_dict[val]
    if val in config_dict:  # Check if key exists in the aggregated settings
        return config_dict.get(val)
    return default


@contextlib.contextmanager
def builtin_defaults():
    """
    While the block runs, hide OFSC_* variables and variables named after a
    setting, so getattr returns the built-in defaults. A new config.json is
    written inside this, so environment values aren't saved as the user's
    settings; they still apply at runtime once the block ends.
    """
    keys = set(get_all_configs())
    hidden = {
        name: value
        for name, value in os.environ.items()
        if name.startswith("OFSC_") or name in keys
    }
    for name in hidden:
        del os.environ[name]
    get_all_configs(forced=True)
    try:
        yield
    finally:
        os.environ.update(hidden)
        get_all_configs(forced=True)


def getkeys(forced=False):
    return get_all_configs(forced=forced)
