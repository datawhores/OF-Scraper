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

import  ofscraper.runner.manager as manager2
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants

log = logging.getLogger("shared")


def get_individual_timeline_post(id, session=None):
    with session or manager2.Manager.get_ofsession(
        backend="httpx",
    ) as c:
        with c.requests(constants.getattr("INDIVIDUAL_TIMELINE").format(id)) as r:
            log.trace(f"post raw individual {r.json()}")
            return r.json()


def process_individual():
    data = []
    for ele in read_args.retriveArgs().post_id:
        try:
            post = get_individual_timeline_post(ele)
            if not post.get("error"):
                data.append(post)
        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
    return data
