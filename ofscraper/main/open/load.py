import logging
import os
import platform
import traceback

import ofscraper.main.close.exit_status as exit_status
import ofscraper.main.open.run as run
import ofscraper.utils.config.config as config_
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.naming_check as naming_check
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.paths.manage as paths_manage
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system


def _report_startup_error(error):
    print(error)
    print(traceback.format_exc())
    try:
        logging.getLogger("shared").debug(traceback.format_exc())
        logging.getLogger("shared").debug(error)
    except Exception as E:
        print(E)
        print(traceback.format_exc())


def main():
    try:
        systemSet()
        try:
            # settings are read from config.json, so a broken file can stop
            # either of these
            settings_loader()
            setdate()
            readConfig()
        except Exception as E:
            _report_startup_error(E)
            raise SystemExit(exit_status.CONFIG)
        setLogger()
        make_folder()
        checkFileOptions()
        run.main()
    except Exception as E:
        _report_startup_error(E)
        raise SystemExit(exit_status.ERROR)


def settings_loader():
    settings.get_settings()


def setdate():
    dates.resetLogDate()


def setLogger():
    logger.get_shared_logger()
    config_file.log_notes()
    logs.discord_warning()
    paths_manage.cleanup_logs()


def systemSet():
    system.setName()
    system.set_eventloop()
    if platform.system() == "Windows":
        os.system("color")


def readConfig():
    import ofscraper.utils.dry_run as dry_run

    # a dry run changes nothing, so an older config.json isn't rewritten in
    # the current form; the getters read either form
    config_.read_config(update=not dry_run.active())


def make_folder():
    paths_manage.make_folders()


def checkFileOptions():
    naming_check.report()
