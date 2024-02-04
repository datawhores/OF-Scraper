import logging
import traceback

import ofscraper.runner.run as run
import ofscraper.utils.args.read as read_args
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
        setLogger()
        readConfig()
        make_folder()
        run.main()
    except Exception as E:
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
    system.set_mulitproc_start_type()
    system.set_eventloop()


def readConfig():
    config_.read_config()


def make_folder():
    paths_manage.make_folders()
