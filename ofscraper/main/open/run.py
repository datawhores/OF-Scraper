import logging
import traceback

import ofscraper.main.close.exit as exit_manager
import ofscraper.utils.console as console
import ofscraper.utils.context.exit as exit_context
from ofscraper.managers.manager import start_manager


def check_database():
    """With PostgreSQL configured, connect before any work starts: a server
    that can't be used stops the run here with one sentence."""
    import ofscraper.db.postgres as postgres

    if postgres.enabled():
        version = postgres.POSTGRES.check()
        logging.getLogger("shared").info(
            f"Using the PostgreSQL database at {postgres.describe()} "
            f"(server version {version})"
        )


def main():
    try:
        check_database()
        start_manager()
    except SystemExit as exc:
        if exc.code == 130:
            exit_manager.shutdown()
        raise
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
        logging.getLogger("shared").error(E)
        try:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.shutdown()
        except KeyboardInterrupt as E:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
                raise E
        # The run failed; don't report success to scripts and schedulers
        raise SystemExit(1)
