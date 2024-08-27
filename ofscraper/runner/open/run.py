import logging
import traceback

import ofscraper.runner.close.exit as exit_manager
import ofscraper.utils.console as console
import ofscraper.utils.context.exit as exit_context
from ofscraper.runner.manager import start_manager


def main():
    try:
        start_manager()
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



