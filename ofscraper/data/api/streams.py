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

# The scan itself is in common/dated_posts.py, shared with timeline and archived.
# The functions and DB helpers imported here are looked up through this module,
# so patching one here changes the streams scan only.
import logging
import sys

import ofscraper.data.api.common.dated_posts as dated_posts

# Test handles (module.incomplete, module.progress_utils, module.of_env,
# module.settings) and per-area helpers looked up on this module by dated_posts.
import ofscraper.data.api.common.incomplete as incomplete  # noqa: F401
import ofscraper.data.api.common.scan_range as scan_range
import ofscraper.utils.live.updater as progress_utils  # noqa: F401
import ofscraper.utils.of_env.of_env as of_env  # noqa: F401
import ofscraper.utils.settings as settings  # noqa: F401
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.data.api.common.after import get_after_pre_checks  # noqa: F401
from ofscraper.data.api.common.check import update_check  # noqa: F401
from ofscraper.data.api.common.page import get_min_posts_batch  # noqa: F401
from ofscraper.data.api.common.timeline import process_posts_as_individual  # noqa: F401
from ofscraper.db.operations_.media import (
    get_media_ids_downloaded_model,  # noqa: F401
    get_streams_media,
)
from ofscraper.db.operations_.posts import (
    get_deleted_post_ids,  # noqa: F401
    get_streams_post_info,
    get_youngest_streams_date,
    mark_post_as_deleted,  # noqa: F401
)
from ofscraper.utils.context.run_async import run

API = "Streams"
AREA = dated_posts.Area(
    api=API,
    endpoint="streamsEP",
    next_endpoint="streamsNextEP",
    max_individual="MAX_STREAMS_INDIVIDUAL_SEARCH",
    cache_trace="oldtimestreams",
    ghosts="ghost streams in database.",
    log_final=True,
)
log = logging.getLogger("shared")
_area = sys.modules[__name__]


@run
@stop.fetching
async def get_streams_posts(model_id, username, c=None, post_id=None):
    return await dated_posts.get_posts(_area, model_id, username, c, post_id)


async def get_oldstreams(model_id, username):
    return await dated_posts.get_old_posts(
        _area, get_streams_post_info, model_id, username
    )


async def process_tasks_batch(generators):
    return await dated_posts.process_tasks_batch(_area, generators)


async def get_split_array(model_id, username, after):
    oldstreams = await get_oldstreams(model_id, username)
    return dated_posts.split_posts(_area, oldstreams, after)


def get_tasks(splitArrays, c, model_id, username, after):
    return dated_posts.get_tasks(
        scrape_stream_posts, splitArrays, c, model_id, username, after
    )


def scrape_stream_posts(
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
        _area, get_streams_media, get_youngest_streams_date, model_id, username
    )


def time_log(username, after):
    scan_range.log_scan_range(log, username, "streams", after)
