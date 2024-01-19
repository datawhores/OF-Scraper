import logging
import platform
import ssl
import sys

import certifi

import ofscraper.utils.args.globals as global_args
import ofscraper.utils.config.file as config_file
import ofscraper.utils.logger as logger
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.system.system as system


def printStartValues():
    args = global_args.getArgs()
    log = logging.getLogger("shared")
    logger.updateSenstiveDict(f"/{common_paths.get_username()}/", "/your_username/")
    logger.updateSenstiveDict(
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
