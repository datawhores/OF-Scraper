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

import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.download.utils.leaky import CHUNK_SIZE
import ofscraper.utils.of_env.of_env as of_env


def get_chunk_size():
    """
    get chunk size in bytes
    """
    if settings.get_settings().download_limit <= 0:
        return CHUNK_SIZE
    return min(CHUNK_SIZE, settings.get_settings().download_limit)


def get_chunk_timeout():
    return of_env.getattr("CHUNK_TIMEOUT_SEC")
