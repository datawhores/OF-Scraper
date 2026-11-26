import logging
import traceback

import ofscraper.main.close.exit as exit_manager
import ofscraper.main.close.exit_status as exit_status
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
    exit_status.reset()
    try:
        check_database()
        start_manager()
    except SystemExit as exc:
        if exc.code in {
            exit_status.AUTH,
            exit_status.UNAVAILABLE,
            exit_status.INTERRUPTED,
        }:
            exit_manager.shutdown()
        raise
    except KeyboardInterrupt as exc:
        console.get_shared_console().print("handling force closing of script")
        try:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
        except KeyboardInterrupt:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
        if not isinstance(exc, exit_context.SigtermInterrupt):
            raise SystemExit(exit_status.INTERRUPTED)
        return
    except Exception as E:
        logging.getLogger("shared").debug(traceback.format_exc())
        logging.getLogger("shared").error(E)
        try:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.shutdown()
        except KeyboardInterrupt:
            with exit_context.DelayedKeyboardInterrupt():
                exit_manager.forcedShutDown()
            raise SystemExit(exit_status.INTERRUPTED)
        # The run failed; don't report success to scripts and schedulers
        import ofscraper.db.postgres as postgres

        if isinstance(E, postgres.PostgresUnavailable):
            raise SystemExit(exit_status.CONFIG)
        raise SystemExit(exit_status.ERROR)
    raise SystemExit(exit_status.code())
