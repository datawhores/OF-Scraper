import logging
import os
import platform
import traceback

import ofscraper.runner.open.run as run
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.checkers as checkers
import ofscraper.utils.config.config as config_
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.globals as log_globals
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.paths.manage as paths_manage
import ofscraper.utils.system.system as system


def main():
    try:
        systemSet()
        args_loader()
        setdate()
        readConfig()
        setLogger()
        make_folder()
        check()
        run.main()
    except Exception as E:
        print(E)
        print(traceback.format_exc())
        try:
            logging.getLogger("shared").debug(traceback.format_exc())
            logging.getLogger("shared").debug(E)
        except Exception as E:
            print(E)
            print(traceback.format_exc())


def args_loader():
    read_args.retriveArgs()


def setdate():
    dates.resetLogDateVManager()


def setLogger():
    log_globals.init_values()
    logger.get_shared_logger()
    logs.discord_warning()
    logger.start_threads()


def systemSet():
    system.setName()
    system.set_eventloop()
    if platform.system() == "Windows":
        os.system("color")


def readConfig():
    config_.read_config()


def make_folder():
    paths_manage.make_folders()


def check():
    checkers.check_config()
    checkers.check_config_key_mode()
