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
import traceback

import ofscraper.main.manager as manager
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")


def get_individual_timeline_post(id, session=None):
    with session or manager.Manager.get_ofsession() as c:
        with c.requests(of_env.getattr("INDIVIDUAL_TIMELINE").format(id)) as r:
            log.trace(f"post raw individual {r.json()}")
            return r.json()


def process_individual():
    data = []
    for ele in settings.get_settings().post_id:
        try:
            post = get_individual_timeline_post(ele)
            if not post.get("error"):
                data.append(post)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
    return data
