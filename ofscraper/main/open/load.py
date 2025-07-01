import logging
import os
import platform
import traceback

import ofscraper.main.open.run as run
import ofscraper.utils.config.config as config_
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.globals as log_globals
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.paths.manage as paths_manage
import ofscraper.utils.system.system as system
import ofscraper.utils.settings as settings



def main():
    try:
        systemSet()
        settings_loader()
        setdate()
        readConfig()
        setLogger()
        make_folder()
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


def settings_loader():
    settings.get_settings()


def setdate():
    dates.resetLogDateVManager()


def setLogger():
    log_globals.init_values()
    logger.get_shared_logger()
    logs.discord_warning()
    paths_manage.cleanup_logs()

def systemSet():
    system.setName()
    system.set_eventloop()
    if platform.system() == "Windows":
        os.system("color")


def readConfig():
    config_.read_config()


def make_folder():
    paths_manage.make_folders()

