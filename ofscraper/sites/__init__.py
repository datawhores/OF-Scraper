"""Which site a run talks to.

A profile belongs to one site. The site is read from ``site.json`` in the
profile folder (``{"site": "fansly"}``); without that file the profile is an
OnlyFans profile, exactly as before. ``--site`` overrides it for one run.
"""

import json
import logging
import pathlib

import ofscraper.utils.const as const

ONLYFANS = "onlyfans"
FANSLY = "fansly"
DEFAULT_SITE = ONLYFANS
SITE_FILE = "site.json"

# display name used for the {site_name} placeholder
SITE_NAMES = {ONLYFANS: "Onlyfans", FANSLY: "Fansly"}
SITES = tuple(SITE_NAMES)
_SITE_CAPABILITIES = {
    ONLYFANS: {
        "post_areas": const.ALL_POST_AREAS,
        "like_areas": const.TIMELINE_POST_AREAS,
        "anon_areas": ("Profile", *const.TIMELINE_POST_AREAS),
        "db_areas": const.ALL_POST_AREAS,
        "scrape_paid": True,
    },
    FANSLY: {
        "post_areas": ("Timeline", "Messages", "Purchased"),
        "like_areas": ("Timeline",),
        "anon_areas": ("Timeline",),
        "db_areas": ("Timeline", "Messages", "Purchased", "Labels"),
        "scrape_paid": False,
    },
}
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


def _resolve_profile_name(args=None) -> str | None:
    try:
        import ofscraper.utils.config.data as config_data
        import ofscraper.utils.profiles.tools as profile_tools

        if args is None:
            import ofscraper.utils.settings as settings

            args = settings.get_args()
        profile = (getattr(args, "profile", None) if args is not None else None) or (
            config_data.get_main_profile()
        )
        return profile_tools.profile_name_fixer(profile)
    except Exception as e:
        log.debug(f"could not resolve the active profile name: {e}")
        return None


def clear_session_site() -> None:
    """Clear the session-only site override and its bound profile."""
    global _session_site, _session_profile
    _session_site = None
    _session_profile = None


def set_active_site(site: str | None) -> str | None:
    """Set (or clear) the active site for the current interactive session."""
    global _session_site, _session_profile
    normalized = normalize(site) if site is not None else None
    if normalized is None:
        clear_session_site()
        return None
    _session_site = normalized
    _session_profile = _resolve_profile_name()
    return _session_site


def rename_session_profile(old_name: str, new_name: str) -> None:
    """Keep a session-only site override attached when its profile is renamed."""
    global _session_profile
    if _session_profile is None:
        return
    import ofscraper.utils.profiles.tools as profile_tools

    if _session_profile == profile_tools.profile_name_fixer(old_name):
        _session_profile = profile_tools.profile_name_fixer(new_name)


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
        profile = profile_tools.profile_name_fixer(profile)
        if _session_site and _session_profile is not None and profile == _session_profile:
            return _session_site
        profile_dir = common_paths.get_config_home() / profile
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


def _capabilities(site=None) -> dict:
    resolved = normalize(site) if site is not None else (FANSLY if is_fansly() else ONLYFANS)
    return _SITE_CAPABILITIES[resolved or DEFAULT_SITE]


def post_areas(site=None) -> tuple[str, ...]:
    """Post areas available for download/metadata on ``site``."""
    return _capabilities(site)["post_areas"]


def like_areas(site=None) -> tuple[str, ...]:
    """Post areas that support like/unlike on ``site``."""
    return _capabilities(site)["like_areas"]


def anon_areas(site=None) -> tuple[str, ...]:
    """Post areas available for anonymous metadata scraping on ``site``."""
    return _capabilities(site)["anon_areas"]


def db_areas(site=None) -> tuple[str, ...]:
    """Post areas selectable in the DB prompt on ``site``."""
    return _capabilities(site)["db_areas"]


def supports_scrape_paid(site=None) -> bool:
    """Whether ``site`` has a separate paid-posts page to scrape."""
    return _capabilities(site)["scrape_paid"]
