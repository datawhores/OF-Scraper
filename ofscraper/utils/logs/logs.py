import logging
import time
import traceback
import re
import platform
import ssl
import sys

import certifi

import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.config.file as config_file
import ofscraper.utils.console as console
import ofscraper.utils.logs.utils.level as log_helpers
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
from ofscraper.__version__ import __version__
import  ofscraper.runner.manager as manager


def printStartValues():
    print_system_log()
    print_args()
    print_config()
    log = logging.getLogger("shared")
    try:
        print_start_message()
        print_latest_version()
    except Exception as e:
        log.error(f"Error while printing start values: {e}")
        log.error(traceback.format_exc())
    time.sleep(3)

def printEndValues():
    print_system_log()
    print_start_message()
    print_latest_version()
        


def print_system_log():
    log = logging.getLogger("shared")
    log_helpers.updateSenstiveDict(
        f"/{common_paths.get_username()}/", "/your_username/"
    )
    log_helpers.updateSenstiveDict(
        f"\\{common_paths.get_username()}\\", "\\\\your_username\\\\"
    )

    # print info
    log.info(f"Log Level: {settings.get_log_level()}")
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
    args = read_args.retriveArgs()
    log = logging.getLogger("shared")
    log.debug(args)
    log.debug(f"sys argv:{sys.argv[1:]}")   if len(sys.argv) > 1 else None

def print_config():
    log = logging.getLogger("shared")
    log.debug(config_file.open_config())



def print_start_message():
    log = logging.getLogger("shared")
    with manager.Manager.get_session(backend="httpx") as  sess:
        with sess.requests(url="https://raw.githubusercontent.com/datawhores/messages/main/ofscraper.MD") as j:
            data=re.sub("\n","",j.text_())
            if not data:
                return     
            log.error(f"[bold yellow]{data}[/bold yellow]")
def print_latest_version():
    log = logging.getLogger("shared")
    with manager.Manager.get_session(backend="httpx") as  sess:
        with sess.requests(url="https://pypi.org/pypi/ofscraper/json") as j:
            data=j.json()
            if not data:
                return
            new_version=data["info"]["version"]
            url=data["info"]["project_url"]

            if re.search(new_version,__version__):  
                log.error("[bold yellow]OF-Scraper up to date[/bold yellow]")
            elif __version__ =="0.0.0":
                log.error("[bold yellow]OF-Scraper can't check version (probably from zip)[/bold yellow]")
            elif ".dev" in __version__:
                log.error("OF-Scraper up to date[/bold yellow]")
            else:
                log.error(f"[bold yellow]new version of OF-Scraper available[/bold yellow]: [bold]{new_version}[/bold]")
                log.error(f"[bold yellow]project url: {url}[/bold yellow]")
                




def discord_warning():
    if read_args.retriveArgs().discord == "DEBUG":
        console.get_shared_console().print(
            "[bold red]Warning Discord with DEBUG is not recommended\nAs processing messages is much slower compared to other[/bold red]"
        )
