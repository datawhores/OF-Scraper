r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/

"""

import logging
from datetime import datetime
from contextlib import contextmanager

import arrow

import ofscraper.main.close.final.run_record as run_record
import ofscraper.main.close.status_file as status_file

log = logging.getLogger("shared")


@contextmanager
def scrape_context_manager():
    # reset stream if needed
    # Before yield as the enter method
    start = datetime.now()
    run_record.start()
    status_file.start_pass()
    from ofscraper.utils.checkers import new_pass

    new_pass()
    log.info("""
==============================
[bold] starting script [/bold]
==============================
""")
    try:
        yield
    except BaseException as e:
        # a pass that raises still reports (post_script isn't run for it)
        from ofscraper.commands.scraper.actions.download import stop

        import ofscraper.main.close.exit_status as exit_status

        if isinstance(e, SystemExit) and e.code not in (None, 0, exit_status.INTERRUPTED):
            # an exit with a reason (maintenance, --auth-fail), not a Ctrl+C
            try:
                exit_status.record(e.code)
                reason = exit_status.label(e.code)
            except (TypeError, ValueError, KeyError):  # not one of the codes
                reason = str(e.code)
            run_record.finish("failed", reason)
            raise
        stopped = isinstance(e, (KeyboardInterrupt, SystemExit, stop.DownloadsStopped))
        run_record.finish("stopped" if stopped else "failed", None if stopped else str(e) or type(e).__name__)
        raise
    end = datetime.now()
    log.warning(f"""
===========================
[bold] Script Finished [/bold]
Run Time:  [bold]{str(arrow.get(end)-arrow.get(start)).split(".")[0]}[/bold]
Started At:  [bold]{str(arrow.get(start).format("YYYY-MM-DD HH:mm:ss"))}[/bold]
Finished At:  [bold]{str(arrow.get(end).format("YYYY-MM-DD HH:mm:ss"))}[/bold]
===========================
""")
