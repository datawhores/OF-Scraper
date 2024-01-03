import logging
import platform
import ssl
import sys

import certifi

import ofscraper.utils.args as args_
import ofscraper.utils.config as config_
import ofscraper.utils.logger as logger
import ofscraper.utils.paths as paths_
import ofscraper.utils.system as system


def printStartValues():
    args = args_.getargs()
    log = logging.getLogger("shared")
    logger.updateSenstiveDict(f"/{paths_.get_username()}/", "/your_username/")
    logger.updateSenstiveDict(f"\\{paths_.get_username()}\\", "\\\\your_username\\\\")

    # print info
    log.debug(args)
    log.debug(sys.argv[1:]) if len(sys.argv) > 1 else None
    log.debug(platform.platform())
    log.debug(config_.read_config())
    log.info(f"config path: {str(paths_.get_config_path())}")
    log.info(f"profile path: {str(paths_.get_profile_path())}")
    log.info(f"log folder: {str(paths_.get_config_home()/'logging')}")
    log.debug(f"ssl {ssl.get_default_verify_paths()}")
    log.debug(f"python version {platform. python_version()}")
    log.debug(f"certifi {certifi.where()}")
    log.debug(f"number of threads available on system {system.getcpu_count()}")
