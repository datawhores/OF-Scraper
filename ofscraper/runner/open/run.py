import logging
import time
import traceback

import ofscraper.commands.utils.picker as picker
import ofscraper.runner.close.exit as exit_manager
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.console as console
import ofscraper.utils.context.exit as exit_context
import ofscraper.utils.logs.logs as logs
import ofscraper.utils.system.system as system


def main():
    try:
        main_helper()
    except KeyboardInterrupt:
        console.get_shared_console().print("handling force closing of script")
        try:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
        except KeyboardInterrupt:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
    except Exception as E:
        logging.getLogger("shared").debug(traceback.format_exc())
        logging.getLogger("shared").debug(E)
        try:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.shutdown()
        except KeyboardInterrupt as E:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
                raise E


def main_helper():
    if read_args.retriveArgs().get("help"):
        return
    initLogs()
    time.sleep(3)
    print_name()
    picker.pick()
    exit_manager.shutdown()


def print_name():
    console.get_shared_console().print(
        """ 
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                                                                  

"""
    )


def initLogs():
    if len(system.get_dupe_ofscraper()) > 0:
        console.get_shared_console().print(
            "[bold yellow]Warning another OF-Scraper instance was detected[bold yellow]\n\n\n"
        )
    logs.printStartValues()
