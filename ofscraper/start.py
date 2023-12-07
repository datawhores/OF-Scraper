import logging
import platform
import ssl
import time
import traceback

import certifi
from diskcache import Cache

import ofscraper.commands.picker as picker
import ofscraper.utils.args as args_
import ofscraper.utils.config as config_
import ofscraper.utils.exit as exit
import ofscraper.utils.logger as logger
import ofscraper.utils.manager as manager
import ofscraper.utils.paths as paths_
import ofscraper.utils.paths as paths
import ofscraper.utils.system as system


def main():
    try:
        system.set_mulitproc_start_type()
        logger.init_values()
        system.set_eventloop()
        startvalues()
        logger.discord_warning()

        logger.init_parent_logger()
        args = args_.getargs()
        if vars(args).get("help"):
            return
        main_logger_thread = logger.start_stdout_logthread()
        if system.getcpu_count() >= 2:
            other_logger = logger.start_other_process()
        else:
            other_logger = logger.start_other_thread()
        # allow background processes to start
        time.sleep(3)

        paths.make_folders()
        picker.pick()

        logger.gracefulClose(other_logger, main_logger_thread)
        manager.shutdown()

    except KeyboardInterrupt as E:
        print("Force closing script")
        try:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose(other_logger, main_logger_thread)
                manager.shutdown()
                try:
                    cache = Cache(
                        paths.getcachepath(),
                        disk=config_.get_cache_mode(config_.read_config()),
                    )
                    cache.close()
                    raise E
                except Exception as E:
                    with exit.DelayedKeyboardInterrupt():
                        raise E

        except KeyboardInterrupt as E:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose(other_logger, main_logger_thread)
                manager.shutdown()
                raise E
    except Exception as E:
        logging.getLogger("shared").traceback_(traceback.format_exc())
        logging.getLogger("shared").traceback_(E)
        try:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose(other_logger, main_logger_thread)
                manager.shutdown()
                try:
                    cache = Cache(
                        paths.getcachepath(),
                        disk=config_.get_cache_mode(config_.read_config()),
                    )
                    cache.close()

                    raise E
                except Exception as E:
                    with exit.DelayedKeyboardInterrupt():
                        raise E

        except KeyboardInterrupt as E:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose(other_logger, main_logger_thread)
                if logger.queue_:
                    logger.queue_.close()
                    logger.queue_.cancel_join_thread()
                manager.shutdown()
                raise


def startvalues():
    args = args_.getargs()
    log = logger.get_shared_logger()
    logger.updateSenstiveDict(f"/{paths_.get_username()}/", "/your_username/")
    logger.updateSenstiveDict(f"\\{paths_.get_username()}\\", "\\\\your_username\\\\")

    # print info
    log.debug(args)
    log.debug(platform.platform())
    log.debug(config_.read_config())
    log.info(f"config path: {str(paths_.get_config_path())}")
    log.info(f"profile path: {str(paths_.get_profile_path())}")
    log.info(f"log folder: {str(paths_.get_config_home()/'logging')}")
    log.debug(f"ssl {ssl.get_default_verify_paths()}")
    log.debug(f"python version {platform. python_version()}")
    log.debug(f"certifi {certifi.where()}")
    log.debug(f"number of threads available on system {system.getcpu_count()}")
