
import sys
import os
import time
import ssl
import platform
import certifi
import multiprocessing
from threading import Event
import ofscraper.utils.logger as logger
import ofscraper.utils.args as args_
import ofscraper.commands.scraper as scraper
import ofscraper.commands.check as check
import ofscraper.commands.manual as manual
import ofscraper.utils.config as config_
import ofscraper.utils.profiles as profiles_
import ofscraper.utils.paths as paths_
import ofscraper.utils.console as console_
import ofscraper.utils.exit as exit
import ofscraper.utils.misc as misc



def main():
    main_log_thread=None
    other_log_process=None
    #only use if <2 threads
    other_log_thread=None
   
    try:
        main_event = Event()
        other_event = Event()
        main_log_thread=logger.start_stdout_logthread(event=main_event)
        #start other log consumer, only if more then 3 process
        if misc.getcpu_count()>2:other_log_process=logger.start_other_process()
        else: other_log_thread=logger.start_other_thread(event=other_event)
        #allow background processes to start
        time.sleep(3)

        args=args_.getargs()
        if vars(args).get("help"):
            sys.exit()
    

        make_folders()
        if args.command=="post_check":
            check.post_checker()
        elif args.command=="msg_check":
            check.message_checker()
        elif args.command=="paid_check":
            check.purchase_checker()
        elif args.command=="story_check":
            check.stories_checker()
        elif args.command=="manual":
            manual.manual_download()
        else:
            scraper.main()
        logger.get_shared_logger().critical(None)
        main_log_thread.join()
        if other_log_process:other_log_process.join()
        if other_log_thread:other_log_thread.join()
    except KeyboardInterrupt as E:
            print("Force closing script")
            try:
                with exit.DelayedKeyboardInterrupt():
                    main_event.set()
                    if other_log_process:other_log_process.join(timeout=1);other_log_process.terminate()
                    if other_log_thread:other_event.set()
                   
            except KeyboardInterrupt:
                    main_event.set()
                    if other_log_process:other_log_process.join(timeout=1);other_log_process.terminate()
                    if other_log_thread:other_event.set()

    

def make_folders():
    config_.get_config_folder()
    profiles_.create_profile_path()

def startvalues():
    args=args_.getargs()
    log=logger.get_shared_logger()
    logger.updateSenstiveDict(f"/{paths_.get_username()}/","/your_username/")
    logger.updateSenstiveDict(f"\\{paths_.get_username()}\\","\\\\your_username\\\\")

    #print info
    log.debug(args)
    log.debug(platform.platform())
    log.debug(config_.read_config())
    log.info(f"config path: {str(paths_.get_config_path())}")
    log.info(f"profile path: {str(paths_.get_profile_path())}")
    log.info(f"log folder: {str(paths_.get_config_home()/'logging')}")
    log.debug(f"ssl {ssl.get_default_verify_paths()}")
    log.debug(f"python version {platform. python_version()}" )
    log.debug(f"certifi {certifi.where()}")

def discord_warning():
    if args_.getargs().discord=="DEBUG":
        console_.get_shared_console().print("[bold red]Warning Discord with DEBUG is not recommended\nAs processing messages is much slower compared to other[/bold red]")


def set_mulitproc_start_type():
    plat=platform.system()
    if plat == "Darwin" or plat=="Windows":
        multiprocessing.set_start_method('spawn')
        os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
        os.environ['no_proxy'] = '*'
    else:
        multiprocessing.set_start_method('fork')