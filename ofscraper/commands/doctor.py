"""Check the setup without running a scrape: config, logins on file, ffmpeg,
key files, folders, free space and the database setting.

It reads config.json as it is, changes nothing, makes no connection and
never asks a question. Each line is PASS, WARN, FAIL or SKIP; the exit status
is 1 when anything fails. No login value, password or key is printed.

--online also connects: to PostgreSQL, to the site to check the login (with
the scraper's own session), to the signing rule sources and to Stash. It
isn't read-only: it starts the scraper as a run does, which may rewrite
config.json and create folders, and the signing rule and Fansly's device id
are kept as a run keeps them. It is skipped where the offline checks found
something that would make the start ask a question.
"""

import argparse
import contextlib
import getpass
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.parse

import ofscraper.utils.of_env.of_env as of_env

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
OF_AUTH_KEYS = ["sess", "auth_id", "user_agent", "x-bc"]


def _homes():
    """The home folder as it may be written in a path: as given and with
    links followed, each also with forward slashes; longest first."""
    home = pathlib.Path.home()
    found = {str(home)}
    with contextlib.suppress(OSError, RuntimeError):
        found.add(str(home.resolve()))
    found |= {h.replace("\\", "/") for h in found}
    return sorted((h.rstrip("\\/") for h in found if len(h.rstrip("\\/")) > 1), key=len, reverse=True)


def redact(text):
    """text with the home folder written as ~ and the login name, where it
    is a folder name elsewhere, as <user>: the output is meant for public
    issues."""
    flags = re.IGNORECASE if os.name == "nt" else 0
    for home in _homes():
        text = re.sub(re.escape(home) + r"(?=$|[\\/])", "~", text, flags=flags)
    try:
        user = getpass.getuser()
    except Exception:
        user = None
    if user:
        text = re.sub(r"(?<=[\\/])" + re.escape(user) + r"(?=$|[\\/])", "<user>", text, flags=flags)
    return text


class Report:
    def __init__(self):
        self.results = []

    def add(self, status, check, detail=""):
        self.results.append({"status": status, "check": check, "detail": redact(str(detail))})

    @property
    def failed(self):
        return any(r["status"] == FAIL for r in self.results)

    def text(self):
        width = max(len(r["check"]) for r in self.results)
        return "\n".join(
            f"{r['status']:<5} {r['check']:<{width}}  {r['detail']}".rstrip()
            for r in self.results
        )


def config_path(given=None):
    """Where config.json is, by get_config_path's rule (utils/paths/common.py),
    without reading settings or creating anything."""
    home = pathlib.Path.home() / of_env.getattr("configPath")
    name = of_env.getattr("configFile")
    if not given:
        return home / name
    path = pathlib.Path(given)
    if path.is_file():
        return path
    if path.is_dir() or path.suffix == "":
        return path / name
    if str(path.parent) == ".":
        return home / path
    return path


def read_config(path, report):
    """The settings in config.json, or None for the built-in defaults."""
    import ofscraper.utils.config.file as config_file
    import ofscraper.utils.encoding as encoding

    if not path.exists():
        report.add(WARN, "config file", f"{path} isn't there: a run makes one with the defaults")
        return None
    try:
        text = encoding.read_text_file(path)
    except (OSError, UnicodeDecodeError) as error:
        report.add(FAIL, "config file", f"{path} can't be read: {error}")
        return None
    try:
        # the run's own check (config_context), which doesn't repair
        # unescaped backslashes the way json_loads does
        config = config_file.checked(text)
    except json.JSONDecodeError as error:
        report.add(FAIL, "config file",
                   f"{path} isn't valid JSON: {error.msg} at line {error.lineno}, column {error.colno}."
                   " The rest is checked with the defaults")
        return None
    except config_file.NotAnObjectError as error:
        report.add(FAIL, "config file", f"{path}: {error}. The rest is checked with the defaults")
        return None
    report.add(PASS, "config file", str(path))
    return config


def _config(config):
    """What a config getter is given: the settings, or False for the
    defaults. An empty {} is the defaults too: the getters would open
    config.json through the settings for it."""
    return config or False


def _get(getter, config):
    """A config getter's value for this config, or the default."""
    return getter(config=_config(config))


def profile_folder(config, profile, path):
    import ofscraper.utils.config.data as data
    import ofscraper.utils.profiles.tools as profile_tools

    name = profile or _get(data.get_main_profile, config)
    return path.parent / profile_tools.profile_name_fixer(name)


def check_onlyfans_auth(folder, report):
    import ofscraper.utils.auth.utils.dict as auth_dict
    import ofscraper.utils.encoding as encoding

    path = folder / of_env.getattr("authFile")
    if not path.exists():
        # a run asks for the login and writes the file
        report.add(WARN, "OnlyFans auth", f"{path} isn't there: a run asks for the login and makes it")
        return
    try:
        text = encoding.read_text_file(path)
        # get_auth_dict reads the profile's file through the settings for ""
        if not text.strip():
            report.add(FAIL, "OnlyFans auth", f"{path} is empty")
            return
        auth = auth_dict.get_auth_dict(text)
    except (OSError, ValueError, AttributeError, TypeError) as error:
        # TypeError: JSON null, a number or true/false, which get_auth_dict can't look in
        report.add(FAIL, "OnlyFans auth", f"{path} can't be read: {type(error).__name__}")
        return
    if not isinstance(auth, dict):
        report.add(FAIL, "OnlyFans auth", f"{path} doesn't hold the auth fields")
        return
    # a run strips each value (auth/data.py fix_val), which fails on a
    # number or true/false, and asks for one that is only spaces
    not_text = [k for k in OF_AUTH_KEYS if auth.get(k) is not None and not isinstance(auth.get(k), str)]
    blank = [k for k in OF_AUTH_KEYS if k not in not_text and not (auth.get(k) or "").strip()]
    if not_text:
        report.add(FAIL, "OnlyFans auth", f"not text in {path} (put the value in quotes): {', '.join(not_text)}")
    elif blank:
        report.add(FAIL, "OnlyFans auth", f"blank in {path}: {', '.join(blank)}")
    else:
        report.add(PASS, "OnlyFans auth", f"{path} (every field set; the login itself is checked with --online)")


def check_fansly_auth(folder, report):
    import ofscraper.sites.fansly.auth as fansly_auth
    import ofscraper.sites.fansly.constants as fansly_constants

    path = folder / fansly_constants.AUTH_FILE
    if not path.exists():
        report.add(WARN, "Fansly auth", f"{path} isn't there: a run asks for the login and makes it")
        return
    try:
        auth = fansly_auth.read_auth(path)
    except (OSError, ValueError, AttributeError) as error:
        report.add(FAIL, "Fansly auth", f"{path} can't be read: {type(error).__name__}")
        return
    problems = fansly_auth.problems(auth)
    if problems:
        report.add(FAIL, "Fansly auth", f"{path}: {'; '.join(problems)}")
    else:
        report.add(PASS, "Fansly auth", f"{path} (the login itself is checked with --online)")


def check_auth(config, folder, site, report):
    import ofscraper.sites as sites

    for name, check in ((sites.ONLYFANS, check_onlyfans_auth), (sites.FANSLY, check_fansly_auth)):
        label = "OnlyFans auth" if name == sites.ONLYFANS else "Fansly auth"
        if name == site:
            check(folder, report)
        else:
            report.add(SKIP, label, f"not used: the profile is for {sites.SITE_NAMES[site]}")


def check_ffmpeg(config, report):
    import ofscraper.utils.config.data as data
    import ofscraper.utils.system.ffmpeg as ffmpeg

    configured = _get(data.get_ffmpeg, config) or of_env.getattr("FFMPEG_DEFAULT")
    if configured:
        try:
            is_ffmpeg, version, major = ffmpeg.ffmpeg_version(configured) if shutil.which(configured) else (None, None, None)
        except (OSError, subprocess.SubprocessError):
            is_ffmpeg, version, major = None, None, None
        if is_ffmpeg and major is not None and major < 6:
            report.add(FAIL, "ffmpeg", f"{configured} is version {version}; protected videos need 6 or newer")
            return None
        if not is_ffmpeg:
            report.add(FAIL, "ffmpeg", f"the configured ffmpeg {configured} isn't there or isn't ffmpeg")
            return None
    path, source, version = ffmpeg.find_ffmpeg(configured)
    if not path:
        report.add(FAIL, "ffmpeg", "no ffmpeg 6 or newer found in the config, pyffmpeg or PATH")
        return None
    report.add(PASS, "ffmpeg", f"{version or 'version unknown'} (from {source}): {path}")
    return path


def check_ffprobe(ffmpeg_path, report):
    if not ffmpeg_path:
        report.add(SKIP, "ffprobe", "no ffmpeg to look beside")
        return
    name = "ffprobe.exe" if ffmpeg_path.lower().endswith(".exe") else "ffprobe"
    beside = os.path.join(os.path.dirname(ffmpeg_path), name)
    found = beside if os.path.exists(beside) else shutil.which("ffprobe")
    if found:
        report.add(PASS, "ffprobe", found)
    else:
        report.add(WARN, "ffprobe", "not found beside ffmpeg or in PATH: media lengths come from ffmpeg instead")


def check_keys(config, site, report):
    import ofscraper.sites as sites
    import ofscraper.utils.config.data as data
    from ofscraper.commands.scraper.actions.download.utils import keyhelpers

    if site == sites.FANSLY:
        # as at a run's start (system/network.py): Fansly video has no DRM
        report.add(SKIP, "key files", "not used: Fansly videos aren't protected")
        return
    mode = _get(data.get_key_mode, config)
    client_id = _get(data.get_client_id, config) if config else None
    private_key = _get(data.get_private_key, config) if config else None
    if mode == "cdrm":
        if keyhelpers.cdm_key_problems("manual", client_id, private_key):
            fix = "then set client-id and private-key to your key files"
        else:
            fix = "client-id and private-key are already set, so that switch is the whole fix"
        url = str(of_env.getattr("CDRM") or "").strip()
        try:
            retired = keyhelpers.cdrm_retired(url)
            host = urllib.parse.urlsplit(url).hostname
        except ValueError:  # a malformed address, e.g. an unclosed IPv6 bracket
            retired, host = False, None
        if url and not retired:
            # a server of the user's own (#677): only its host is shown, as
            # the address can hold a login
            host = host or "an unreadable address"
            report.add(WARN, "key files",
                       f"key mode cdrm: keys are asked from the server in OFSC_CDRM_URL ({host}), which is sent"
                       " your OnlyFans cookies, so use only a server you run (not contacted by this check)."
                       f" The cdrm mode is deprecated: to stop using it, set key-mode-default to manual; {fix}")
            return
        report.add(WARN, "key files",
                   "key mode cdrm: the cdrm service doesn't work, so protected videos will fail"
                   f" (not contacted by this check). Set key-mode-default to manual; {fix}")
        return
    if mode != "manual":
        report.add(PASS, "key files", f"key mode {mode}: no key files needed")
        return
    if not str(client_id or "").strip() and not str(private_key or "").strip():
        # the default on a fresh install: a run goes on without them
        report.add(WARN, "key files", "no key files set up yet: protected (DRM) videos are skipped until client-id and private-key are set")
        return
    problem = keyhelpers.cdm_key_problems(mode, client_id, private_key)
    if problem:
        report.add(FAIL, "key files", problem)
        return
    try:
        keyhelpers.load_device(private_key, client_id)
    except Exception as error:
        report.add(FAIL, "key files", f"the key files can't be loaded: {type(error).__name__}")
        return
    report.add(PASS, "key files", f"client-id {client_id}, private-key {private_key}")


def _free(path):
    try:
        gib = shutil.disk_usage(path).free / 2**30
    except OSError as error:
        return f"free space can't be read: {error.strerror or type(error).__name__}"
    return f"{gib:.1f} GiB free"


def _device(path):
    try:
        return os.stat(path).st_dev
    except OSError:
        return None


def _check_path(save):
    """The folder the free-space limit is measured at: OFSC_DISK_SPACE_CHECK_PATH,
    or when that is empty the disk that holds the save folder, measured at
    its nearest folder that is there, a link followed first
    (free.get_check_path's rule)."""
    measured = of_env.getattr("DISK_SPACE_CHECK_PATH")
    if measured:
        return measured
    path = save.resolve()
    while not path.exists() and path.parent != path:
        path = path.parent
    return path


# where Linux and macOS mount drives and shares; a missing save folder whose
# nearest folder that is there is one of these is on a drive not mounted
MOUNT_PARENTS = ("/", "/mnt", "/media", "/Volumes", "/net")
# this holds a folder per user, which holds the mounts (/run/media/<user>)
USER_MOUNT_PARENTS = ("/run/media",)


def _windows():
    return os.name == "nt"


def _unmounted(save):
    """The save folder isn't there and nothing is above it up to a place
    drives are mounted: its drive or share likely isn't mounted."""
    here = save.absolute()
    while not here.exists() and here.parent != here:
        here = here.parent
    return here in {pathlib.Path(p) for p in MOUNT_PARENTS} or here.parent in {
        pathlib.Path(p) for p in USER_MOUNT_PARENTS
    }


def check_folders(config, report):
    import ofscraper.utils.config.data as data
    import ofscraper.utils.paths.common as common_paths

    save = pathlib.Path(os.path.expanduser(common_paths.get_save_location(_config(config))))
    if save.is_dir():
        report.add(PASS, "save folder", f"{save}, {_free(save)}")
    elif not _windows() and _unmounted(save):
        report.add(FAIL, "save folder", f"{save} isn't there: is the drive or share mounted?")
    elif pathlib.Path(save.anchor or ".").is_dir():
        # the download makes it, parents included
        report.add(WARN, "save folder", f"{save} isn't there yet: a run makes it")
    else:
        report.add(FAIL, "save folder", f"{save} isn't there, nor is its drive {save.anchor}")
    temp = _get(data.get_TempDir, config)
    if temp:
        temp = pathlib.Path(os.path.expanduser(temp))
        if temp.is_dir():
            report.add(PASS, "temp folder", f"{temp}, {_free(temp)}")
        else:
            report.add(FAIL, "temp folder", f"{temp} isn't there")
    else:
        report.add(PASS, "temp folder", "not set: files are written beside their final place")

    limit = _get(data.get_system_freesize, config) or 0
    if not limit:
        report.add(PASS, "free-space limit", "off")
        return
    measured = _check_path(save)
    if _device(measured) is None:
        report.add(FAIL, "free-space limit", f"measures {measured}, which isn't there (set OFSC_DISK_SPACE_CHECK_PATH)")
    elif save.is_dir() and _device(measured) != _device(save):
        report.add(WARN, "free-space limit",
                   f"measures {measured}, but downloads go to another disk ({save}); set OFSC_DISK_SPACE_CHECK_PATH")
    else:
        report.add(PASS, "free-space limit", f"{limit} bytes, measured at {measured}, {_free(measured)}")


def check_database(report):
    import ofscraper.db.postgres as postgres

    url = postgres.url()
    if not url:
        report.add(PASS, "database", "SQLite, one user_data.db per creator")
        return
    where = postgres.describe(url)
    try:
        import psycopg  # noqa: F401
        import psycopg_pool  # noqa: F401
    except ImportError:
        report.add(FAIL, "database", f"PostgreSQL at {where} is set, but its driver isn't installed")
        return
    report.add(PASS, "database", f"PostgreSQL at {where}; the connection is checked with --online")


def _status(report, check):
    found = [r for r in report.results if r["check"] == check]
    return found[0]["status"] if found else None


def check_postgres(report, site):
    import ofscraper.db.postgres as postgres

    if not postgres.url():
        return
    if _status(report, "database") == FAIL:
        report.add(SKIP, "PostgreSQL", "the database setting failed above")
        return
    try:
        # the site is given: the settings would parse doctor's own
        # command line, as the start hasn't set it yet
        version = postgres.POSTGRES.check(site)
    except Exception as error:
        report.add(FAIL, "PostgreSQL", str(error))
        return
    report.add(PASS, "PostgreSQL", f"{postgres.describe()}, server version {version}")


def start(config, profile, site):
    """The normal start up to where a run would begin, without running one."""
    import ofscraper.main.open.load as load
    import ofscraper.managers.manager as manager

    argv = ["ofscraper"]
    for flag, value in (("--config", config), ("--profile", profile), ("--site", site)):
        if value:
            argv += [flag, value]
    sys.argv = argv
    load.settings_loader()
    load.setdate()
    load.readConfig()
    load.setLogger()
    load.make_folder()
    if not isinstance(manager.Manager, manager.mainManager):
        manager.Manager = manager.mainManager()


def check_login(report, site_name):
    import ofscraper.data.api.init as init

    status, message = init.auth_status()
    if status == "UP":
        report.add(PASS, f"{site_name} login", "logged in")
    elif status == "DOWN":
        report.add(FAIL, f"{site_name} login", "the site rejected the login: update the auth file")
    else:
        report.add(WARN, f"{site_name} login", f"couldn't be checked: {message}")


def check_signing_rules(report):
    import ofscraper.utils.auth.request as request

    used, failed = request.last_attempt["used"], request.last_attempt["failed"]
    detail = "; ".join(f"{source}: {reason}" for source, reason in failed)
    if used and not failed:
        report.add(PASS, "signing rules", f"from {used}")
    elif used:
        report.add(WARN, "signing rules", f"from {used}, after others gave none ({detail})")
    elif failed:
        report.add(FAIL, "signing rules", f"no source gave a rule ({detail})")
    else:
        report.add(SKIP, "signing rules", "not fetched")


def check_stash(report):
    from ofscraper.commands.stash_sync import API_KEY_ENV, URL_ENV, StashClient, StashError

    url = os.environ.get(URL_ENV, "").strip()
    if not url:
        return
    try:
        data = StashClient(url, os.environ.get(API_KEY_ENV), timeout=15).call(
            "query { version { version } }", retries=0
        )
        version = ((data or {}).get("version") or {}).get("version") or "version unknown"
    except (StashError, OSError, ValueError) as error:
        report.add(FAIL, "Stash", str(error))
        return
    except (KeyError, AttributeError, TypeError) as error:
        # JSON that isn't a GraphQL reply: not Stash, or a proxy's page
        report.add(FAIL, "Stash", f"{url}: unexpected reply ({type(error).__name__})")
        return
    report.add(PASS, "Stash", f"{url}, {version}")


def run_online(report, config=None, profile=None, site=None):
    """--online: the checks that connect, each skipped with its reason when
    an offline check found what it needs broken."""
    import ofscraper.sites as sites

    check_postgres(report, site)
    site_name = sites.SITE_NAMES[site]
    auth_check = "OnlyFans auth" if site == sites.ONLYFANS else "Fansly auth"
    login = f"{site_name} login"
    if _status(report, "config file") == FAIL:
        report.add(SKIP, login, "the config file failed above: a run would stop to ask about it")
    elif _status(report, auth_check) == FAIL:
        report.add(SKIP, login, "the auth file failed above: a run would stop to ask for it")
    elif _status(report, auth_check) == WARN:
        report.add(SKIP, login, "there's no auth file yet: a run would stop to ask for the login")
    else:
        try:
            start(config, profile, site)
            check_login(report, site_name)
        except (Exception, SystemExit) as error:
            report.add(FAIL, login, f"the start failed: {error}")
        if site == sites.ONLYFANS:
            check_signing_rules(report)
    check_stash(report)


def run(config=None, profile=None, site=None, online=False):
    """Every offline check, and with online the ones that connect; the Report."""
    import ofscraper.sites as sites

    report = Report()
    path = config_path(config)
    settings = read_config(path, report)
    folder = profile_folder(settings, profile, path)
    site = sites.normalize(site) or sites.read_profile_site(folder)
    report.add(PASS, "profile", f"{folder.name} ({sites.SITE_NAMES[site]})" + ("" if folder.is_dir() else ", folder isn't there yet"))
    check_auth(settings, folder, site, report)
    ffmpeg_path = check_ffmpeg(settings, report)
    check_ffprobe(ffmpeg_path, report)
    check_keys(settings, site, report)
    check_folders(settings, report)
    check_database(report)
    if online:
        run_online(report, config, profile, site)
    else:
        report.add(SKIP, "login", "run with --online to check the login, PostgreSQL and Stash")
    return report


def main(argv=None):
    import ofscraper.sites as sites

    parser = argparse.ArgumentParser(prog="ofscraper doctor", description=__doc__)
    parser.add_argument("--config", metavar="PATH", help="The config file or folder, as for a run's --config")
    parser.add_argument("--profile", metavar="NAME", help="The profile to check (default: the config's main profile)")
    parser.add_argument("--site", choices=list(sites.SITES), help="Check this site's auth file, not the profile's site")
    parser.add_argument("--json", action="store_true", help="Print the results as JSON")
    parser.add_argument("--online", action="store_true", help="Also connect: PostgreSQL, the login, the signing rules and Stash. Not read-only: it starts the scraper as a run does")
    args = parser.parse_args(argv)
    # with --json, what the start prints (a config made, log lines) goes to
    # stderr, so stdout is only the JSON
    quiet = contextlib.redirect_stdout(sys.stderr) if args.json else contextlib.nullcontext()
    try:
        with quiet:
            report = run(args.config, args.profile, args.site, online=args.online)
    except KeyboardInterrupt:
        parser.exit(130, "Stopped\n")
    if args.json:
        print(json.dumps({"ok": not report.failed, "results": report.results}, indent=2))
    else:
        print(report.text())
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
