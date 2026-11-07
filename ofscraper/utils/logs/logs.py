import logging
import time
import traceback
import re
import platform
import ssl
import sys

import certifi

import ofscraper.utils.config.file as config_file
import ofscraper.utils.console as console
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
from ofscraper.__version__ import __version__
import ofscraper.utils.cache.cache as cache
from ofscraper.managers.sessionmanager.sessionmanager import BareSession


def printStartValues():
    print_system_log()
    print_args()
    print_config()
    log = logging.getLogger("shared")
    try:
        print_start_message()
        print_latest_version()
    except Exception as e:
        log.debug(f"Error while printing start values: {e}")
        log.debug(traceback.format_exc())
    time.sleep(3)


def printEndValues():
    print_system_log()
    print_start_message()
    print_latest_version()


def print_system_log():
    log = logging.getLogger("shared")
    # print info
    log.info(f"Log Level: {settings.get_settings().log_level}")
    log.info(f"Output Level: {settings.get_settings().output_level}")
    log.info(f"Discord Level: {settings.get_settings().discord_level}")
    log.info(f"version: {__version__}")
    log.debug(platform.platform())
    log.info(f"config path: {str(common_paths.get_config_path())}")
    log.info(f"profile path: {str(common_paths.get_profile_path())}")
    log.info(f"log folder: {str(common_paths.get_config_home()/'logging')}")
    log.debug(f"ssl {ssl.get_default_verify_paths()}")
    log.debug(f"python version {platform. python_version()}")
    log.debug(f"certifi {certifi.where()}")
    log.debug(f"number of threads available on system {system.getcpu_count()}")


def print_args():
    args = settings.get_args()
    log = logging.getLogger("shared")
    log.debug(args)
    log.debug(f"sys argv:{sys.argv[1:]}") if len(sys.argv) > 1 else None


def print_config():
    log = logging.getLogger("shared")
    log.debug(config_file.open_config())


def print_start_message():
    log = logging.getLogger("shared")
    message = cache.get("OFSCRAPER_MESSAGE")
    if message:
        return message
    with BareSession.get_bare_session(
        url="https://raw.githubusercontent.com/datawhores/messages/main/ofscraper.MD",
        method="get",
    ) as sess:
        data = re.sub("\n", "", sess.text)
        if not data:
            return
        cache.set("OFSCRAPER_MESSAGE", data)
        log.error(f"{data}")


def _release(version):
    match = re.match(r"\d+(?:\.\d+)*", version)
    return tuple(int(x) for x in match.group().split(".")) if match else ()


def is_newer(new_version, current_version):
    # compare release numbers only: a build's version can be ahead of PyPI's,
    # and its local part (+g<hash>) doesn't make it older
    return _release(new_version) > _release(current_version)


PYPI_URL = "https://pypi.org/pypi/ofscraper-community/json"


def print_latest_version():
    log = logging.getLogger("shared")
    # runs at the end of every run too, so a failed check (offline, or not on
    # PyPI yet) must not stop it
    try:
        with BareSession.get_bare_session(url=PYPI_URL, method="get") as sess:
            data = sess.json()
    except Exception as e:
        log.debug(f"Couldn't check PyPI for a newer version: {e}")
        return
    if not data:
        return
    new_version = data["info"]["version"]
    url = data["info"]["project_url"]

    if __version__ == "0.0.0":
        log.warning(
            "[bold yellow]OF-Scraper can't check version (probably from zip)[/bold yellow]"
        )
    elif ".dev" in __version__ or not is_newer(new_version, __version__):
        log.warning("[bold yellow]OF-Scraper up to date[/bold yellow]")
    else:
        log.warning(
            f"[bold yellow]new version of OF-Scraper available[/bold yellow]: [bold]{new_version}[/bold]"
        )
        log.warning(f"[bold yellow]project url: {url}[/bold yellow]")


def discord_warning():
    if settings.get_settings().discord_level == "DEBUG":
        console.get_console().print(
            "[bold red]Warning Discord with DEBUG is not recommended\nAs processing messages is much slower compared to other[/bold red]"
        )
