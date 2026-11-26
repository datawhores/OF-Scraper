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
_session_site = None
_session_profile = None

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


def set_active_site(site: str | None) -> str | None:
    """Set (or clear) the active site for the current interactive session."""
    global _session_site
    _session_site = normalize(site) if site is not None else None
    return _session_site


def init_session_site() -> str:
    """Capture the initial site (including ``--site``) so prompt mode can switch later."""
    import ofscraper.utils.settings as settings

    site = current_site()
    set_active_site(site)
    args = settings.get_args()
    if args is not None and getattr(args, "site", None):
        args.site = None
        settings.update_args(args)
    return site


def resolve_site(args) -> str:
    """``--site`` if given, else the profile's stored site, else OnlyFans."""
    global _session_site, _session_profile
    override = normalize(getattr(args, "site", None) if args is not None else None)
    if override:
        return override
    profile = None
    try:
        import ofscraper.utils.config.data as config_data
        import ofscraper.utils.paths.common as common_paths
        import ofscraper.utils.profiles.tools as profile_tools

        profile = (getattr(args, "profile", None) if args is not None else None) or (
            config_data.get_main_profile()
        )
        profile = profile_tools.profile_name_fixer(profile)
        if _session_profile is not None and profile != _session_profile:
            _session_site = None
        _session_profile = profile
        if _session_site:
            return _session_site
        profile_dir = common_paths.get_config_home() / profile_tools.profile_name_fixer(
            profile
        )
    except Exception as e:
        log.debug(f"could not locate the profile folder to read its site: {e}")
        if _session_site:
            return _session_site
        return DEFAULT_SITE
    return read_profile_site(profile_dir)


def current_site() -> str:
    import ofscraper.utils.settings as settings

    return normalize(getattr(settings.get_settings(), "site", None)) or DEFAULT_SITE


def is_fansly() -> bool:
    return current_site() == FANSLY


def site_name(site=None) -> str:
    return SITE_NAMES[normalize(site) or current_site()]
