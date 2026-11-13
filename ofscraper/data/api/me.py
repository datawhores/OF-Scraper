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
import re
import traceback

import ofscraper.managers.manager as manager
import ofscraper.sites as sites
import ofscraper.sites.fansly.me as fansly_me
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.logs.utils.sensitive as sensitive

log = logging.getLogger("shared")


def _name_pattern(value):
    """Mask pattern for a username or display name.

    The display name is free text, so it's escaped: "Jane (VIP)" or "A+B" as a
    raw regex wouldn't match itself, and an unbalanced "(" broke every log
    line. The lookarounds work like the old \\b, also for names that start or
    end with a symbol.
    """
    e = re.escape(str(value))
    return f"{e} | {e}|(?<!\\w){e}(?!\\w)"


def scrape_user():
    if sites.is_fansly():
        return fansly_me.scrape_user()
    with manager.Manager.session.get_ofsession() as c:
        return _scraper_user_helper(c)


def _scraper_user_helper(c):
    try:
        with c.requests(of_env.getattr("meEP")) as r:
            data = r.json_()
            if data["isAuth"]:
                sensitive.add_sensitive_pattern(data["id"], "userid")
                # an empty value would match every space or word edge
                if data.get("username"):
                    sensitive.add_sensitive_pattern(
                        _name_pattern(data["username"]), "username"
                    )
                if data.get("name"):
                    sensitive.add_sensitive_pattern(
                        _name_pattern(data["name"]), "name"
                    )

    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
    return data


def parse_subscriber_count():
    with manager.Manager.session.get_ofsession() as c:
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
