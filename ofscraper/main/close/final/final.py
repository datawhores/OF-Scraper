r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      f
"""

import logging

import ofscraper.main.close.exit_status as exit_status
import ofscraper.utils.settings as settings
from ofscraper.scripts.final_script import final_script
from ofscraper.utils.logs.logs import printEndValues
import ofscraper.managers.manager as manager
import ofscraper.main.close.final.run_record as run_record


def final_action(outcome="ok"):
    """End a run: the run record (post_script's summary, --discord SUMMARY),
    post_script and the printed summaries. outcome is "ok" or "stopped"."""
    # before the record, so the record carries it
    if manager.Manager.stats_manager.failed_count() > 0:
        exit_status.record(exit_status.PARTIAL)
    record = run_record.finish(outcome)
    try:
        # the daemon checks after each pass; a one-off run has only this
        if outcome == "ok" and not getattr(settings.get_settings(), "daemon", None):
            import ofscraper.main.close.alerts as alerts

            alerts.after_run()
    except Exception as e:  # an alert must never break the run's end
        logging.getLogger("shared").debug(f"disk alert not checked: {e}")
    final_script(record)
    manager.Manager.stats_manager.print_summary_by_activity()
    manager.Manager._stats_manager.print_global_summary()
    printEndValues()
