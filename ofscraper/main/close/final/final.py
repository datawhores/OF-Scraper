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

import ofscraper.main.close.exit_status as exit_status
from ofscraper.scripts.final_script import final_script
from ofscraper.utils.logs.logs import printEndValues
import ofscraper.managers.manager as manager


def final_action():
    final_script()
    manager.Manager.stats_manager.print_summary_by_activity()
    manager.Manager._stats_manager.print_global_summary()
    if manager.Manager.stats_manager.failed_count() > 0:
        exit_status.record(exit_status.PARTIAL)
    printEndValues()
