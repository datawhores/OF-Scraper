"""Which site a run talks to.

A profile belongs to one site. The site is read from ``site.json`` in the
profile folder (``{"site": "fansly"}``); without that file the profile is an
OnlyFans profile, exactly as before. ``--site`` overrides it for one run.
"""

import json
import logging
import pathlib

ONLYFANS = "onlyfans"
FANSLY = "fansly"
DEFAULT_SITE = ONLYFANS
SITE_FILE = "site.json"

# display name used for the {site_name} placeholder
SITE_NAMES = {ONLYFANS: "Onlyfans", FANSLY: "Fansly"}
SITES = tuple(SITE_NAMES)

log = logging.getLogger("shared")


def normalize(value):
    if value is None:
        return None
    value = str(value).strip().lower()
    return value if value in SITE_NAMES else None


def read_profile_site(profile_dir) -> str:
    """Site stored in a profile folder, or the default when none is stored."""
    path = pathlib.Path(profile_dir) / SITE_FILE
    try:
        with open(path, encoding="utf-8") as f:
            value = normalize(json.load(f).get("site"))
    except FileNotFoundError:
        return DEFAULT_SITE
    except (OSError, ValueError, AttributeError) as e:
        log.warning(f"Ignoring unreadable {SITE_FILE} in the profile folder: {e}")
        return DEFAULT_SITE
    return value or DEFAULT_SITE


def write_profile_site(profile_dir, site: str) -> pathlib.Path:
    site = normalize(site)
    if not site:
        raise ValueError(f"unknown site, expected one of {', '.join(SITES)}")
    path = pathlib.Path(profile_dir) / SITE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"site": site}, indent=4), encoding="utf-8")
    return path


def resolve_site(args) -> str:
    """``--site`` if given, else the profile's stored site, else OnlyFans."""
    override = normalize(getattr(args, "site", None) if args is not None else None)
    if override:
        return override
    try:
        import ofscraper.utils.config.data as config_data
        import ofscraper.utils.paths.common as common_paths
        import ofscraper.utils.profiles.tools as profile_tools

        profile = (getattr(args, "profile", None) if args is not None else None) or (
            config_data.get_main_profile()
        )
        profile_dir = common_paths.get_config_home() / profile_tools.profile_name_fixer(
            profile
        )
    except Exception as e:
        log.debug(f"could not locate the profile folder to read its site: {e}")
        return DEFAULT_SITE
    return read_profile_site(profile_dir)


def current_site() -> str:
    import ofscraper.utils.settings as settings

    return normalize(getattr(settings.get_settings(), "site", None)) or DEFAULT_SITE


def is_fansly() -> bool:
    return current_site() == FANSLY


def site_name(site=None) -> str:
    return SITE_NAMES[normalize(site) or current_site()]
