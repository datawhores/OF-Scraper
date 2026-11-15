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

# The scan itself is in common/dated_posts.py, shared with streams. The
# names imported here are this area's: the shared code reaches them through
# this module, so patching one here changes the archived scan only.
import logging
import sys

import ofscraper.data.api.common.dated_posts as dated_posts
import ofscraper.data.api.common.scan_range as scan_range
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.utils.context.run_async import run

# Imports marked F401 are used through this module by dated_posts, or patched
# through it (module.settings, module.progress_utils, module.incomplete)
import ofscraper.data.api.common.incomplete as incomplete  # noqa: F401
import ofscraper.utils.live.updater as progress_utils  # noqa: F401
import ofscraper.utils.of_env.of_env as of_env  # noqa: F401
import ofscraper.utils.settings as settings  # noqa: F401
from ofscraper.data.api.common.after import get_after_pre_checks  # noqa: F401
from ofscraper.data.api.common.check import update_check  # noqa: F401
from ofscraper.data.api.common.page import get_min_posts_batch  # noqa: F401
from ofscraper.data.api.common.timeline import process_posts_as_individual  # noqa: F401
from ofscraper.db.operations_.media import (  # noqa: F401
    get_archived_media,
    get_media_ids_downloaded_model,
)
from ofscraper.db.operations_.posts import (  # noqa: F401
    get_archived_post_info,
    get_deleted_post_ids,
    get_youngest_archived_date,
    mark_post_as_deleted,
)

API = "Archived"
AREA = dated_posts.Area(
    api=API,
    endpoint="archivedEP",
    next_endpoint="archivedNextEP",
    max_individual="MAX_ARCHIVED_INDIVIDUAL_SEARCH",
    cache_trace="oldarchived",
    ghosts="ghost archived posts.",
)
log = logging.getLogger("shared")
_area = sys.modules[__name__]


@run
@stop.fetching
async def get_archived_posts(model_id, username, c=None, post_id=None):
    return await dated_posts.get_posts(_area, model_id, username, c, post_id)


async def get_oldarchived(model_id, username):
    return await dated_posts.get_old_posts(
        _area, get_archived_post_info, model_id, username
    )


async def process_tasks_batch(generators):
    return await dated_posts.process_tasks_batch(_area, generators)


async def get_split_array(model_id, username, after):
    oldarchived = await get_oldarchived(model_id, username)
    return dated_posts.split_posts(_area, oldarchived, after)


def get_tasks(splitArrays, c, model_id, username, after):
    return dated_posts.get_tasks(
        scrape_archived_posts, splitArrays, c, model_id, username, after
    )


def scrape_archived_posts(
    c,
    model_id,
    username,
    timestamp=None,
    required_posts=None,
    is_last_chunk=False,
    offset=False,
):
    """An async generator of one worker's pages."""
    return dated_posts.scrape_posts(
        _area, c, model_id, username, timestamp, required_posts, is_last_chunk, offset
    )


async def get_after(model_id, username):
    return await dated_posts.get_after(
        _area, get_archived_media, get_youngest_archived_date, model_id, username
    )


def time_log(username, after):
    scan_range.log_scan_range(log, username, "archived", after)
