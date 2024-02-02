import logging
import platform
import ssl
import sys

import certifi

import ofscraper.utils.args.read as read_args
import ofscraper.utils.config.file as config_file
import ofscraper.utils.console as console
import ofscraper.utils.logs.helpers as log_helpers
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.system.system as system


def printStartValues():
    args = read_args.retriveArgs()
    log = logging.getLogger("shared")
    log_helpers.updateSenstiveDict(
        f"/{common_paths.get_username()}/", "/your_username/"
    )
    log_helpers.updateSenstiveDict(
        f"\\{common_paths.get_username()}\\", "\\\\your_username\\\\"
    )

    # print info
    log.debug(args)
    log.debug(sys.argv[1:]) if len(sys.argv) > 1 else None
    log.debug(platform.platform())
    log.debug(config_file.open_config())
    log.info(f"config path: {str(common_paths.get_config_path())}")
    log.info(f"profile path: {str(common_paths.get_profile_path())}")
    log.info(f"log folder: {str(common_paths.get_config_home()/'logging')}")
    log.debug(f"ssl {ssl.get_default_verify_paths()}")
    log.debug(f"python version {platform. python_version()}")
    log.debug(f"certifi {certifi.where()}")
    log.debug(f"number of threads available on system {system.getcpu_count()}")


def discord_warning():
    if read_args.retriveArgs().discord == "DEBUG":
        console.get_shared_console().print(
            "[bold red]Warning Discord with DEBUG is not recommended\nAs processing messages is much slower compared to other[/bold red]"
        )
