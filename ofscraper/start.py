import asyncio
import logging
import multiprocessing
import os
import platform
import ssl
import time
import traceback
from threading import Event

import certifi
from diskcache import Cache

import ofscraper.commands.check as check
import ofscraper.commands.manual as manual
import ofscraper.commands.scraper as scraper
import ofscraper.utils.args as args_
import ofscraper.utils.config as config_
import ofscraper.utils.console as console_
import ofscraper.utils.exit as exit
import ofscraper.utils.logger as logger
import ofscraper.utils.manager as manager
import ofscraper.utils.paths as paths_
import ofscraper.utils.paths as paths
import ofscraper.utils.profiles as profiles_
import ofscraper.utils.system as system


def main():
    try:
        logger.init_parent_logger()
        args = args_.getargs()
        if vars(args).get("help"):
            return
        main_event = Event()
        other_event = Event()
        main_logger_thread = logger.start_stdout_logthread(event=main_event)
        if system.getcpu_count() >= 20000:
            other_logger = logger.start_other_process()
        else:
            other_logger = logger.start_other_thread(event=other_event)
        # allow background processes to start
        time.sleep(3)

        make_folders()

        if args.command == "post_check":
            check.post_checker()
        elif args.command == "msg_check":
            check.message_checker()
        elif args.command == "paid_check":
            check.purchase_checker()
        elif args.command == "story_check":
            check.stories_checker()
        elif args.command == "manual":
            manual.manual_download()
        else:
            scraper.main()
        logger.closeNormal(other_logger, main_logger_thread)
        manager.shutdown()

    except KeyboardInterrupt as E:
        print("Force closing script")
        try:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose(
                    other_logger, main_logger_thread, main_event, other_event
                )
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
                logger.forcedClose(
                    other_logger, main_logger_thread, main_event, other_event
                )
                manager.shutdown()
                raise E
    except Exception as E:
        logging.getLogger("shared").traceback(traceback.format_exc())
        logging.getLogger("shared").traceback(E)
        try:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose(
                    other_logger, main_logger_thread, main_event, other_event
                )
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

        except KeyboardInterrupt:
            with exit.DelayedKeyboardInterrupt():
                logger.forcedClose(
                    other_logger, main_logger_thread, main_event, other_event
                )
                if logger.queue_:
                    logger.queue_.close()
                    logger.queue_.cancel_join_thread()
                manager.shutdown()
                raise


def make_folders():
    config_.get_config_folder()
    profiles_.create_profile_path()


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


def discord_warning():
    if args_.getargs().discord == "DEBUG":
        console_.get_shared_console().print(
            "[bold red]Warning Discord with DEBUG is not recommended\nAs processing messages is much slower compared to other[/bold red]"
        )


def set_mulitproc_start_type():
    plat = platform.system()
    if plat == "Darwin":
        multiprocessing.set_start_method("spawn")
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
        os.environ["no_proxy"] = "*"
    elif plat == "Windows":
        multiprocessing.set_start_method("spawn")
    else:
        multiprocessing.set_start_method("forkserver")


def set_eventloop():
    plat = platform.system()
    if plat == "Linux":
        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
