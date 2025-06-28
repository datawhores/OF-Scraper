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
import ofscraper.utils.logs.utils.level as log_helpers

log = logging.getLogger("shared")


def scrape_user():
    with manager.Manager.get_ofsession() as c:
        return _scraper_user_helper(c)


def _scraper_user_helper(c):
    try:
        with c.requests(of_env.getattr("meEP")) as r:
            data = r.json_()
            if data["isAuth"]:
                log_helpers.updateSenstiveDict(data["id"], "userid")
                log_helpers.updateSenstiveDict(
                    f"{data['username']} | {data['username']}|\\b{data['username']}\\b",
                    "username",
                )
                log_helpers.updateSenstiveDict(
                    f"{data['name']} | {data['name']}|\\b{data['name']}\\b",
                    "name",
                )

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
    return data


def parse_subscriber_count():
    with manager.Manager.get_ofsession() as c:
        try:
            with c.requests(of_env.getattr("subscribeCountEP")) as r:
                data = r.json_()
                return (
                    data["subscriptions"]["active"],
                    data["subscriptions"]["expired"],
                )

        except Exception as E:
            log.traceback_(E)
            log.traceback_(traceback.format_exc())
            raise E
