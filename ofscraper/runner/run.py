import logging
import time
import traceback

import ofscraper.commands.picker as picker
import ofscraper.runner.exit as exit_manager
import ofscraper.utils.args.read as read_args
import ofscraper.utils.console as console
import ofscraper.utils.context.exit as exit_context
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.system.system as system


def main():
    try:
        main_helper()
    except KeyboardInterrupt as E:
        console.get_shared_console().print("handling force closing of script")
        try:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
                exit_manager.closeCache()
        except KeyboardInterrupt as E:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
                raise E
    except Exception as E:
        logging.getLogger("shared").debug(traceback.format_exc())
        logging.getLogger("shared").debug(E)
        try:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
                exit_manager.closeCache()
        except KeyboardInterrupt as E:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
                raise E


def main_helper():
    if vars(read_args.retriveArgs()).get("help"):
        return
    initLogs()
    time.sleep(3)
    picker.pick()
    exit_manager.shutdown()


def initLogs():
    if len(system.get_dupe_ofscraper()) > 0:
        console.get_shared_console().print(
            "[bold yellow]Warning another OF-Scraper instance was detected[bold yellow]\n\n\n"
        )
    logs.printStartValues()
