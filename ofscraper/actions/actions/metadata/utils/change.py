import asyncio
import pathlib
import random
from functools import partial

import ofscraper.classes.placeholder as placeholder
import ofscraper.actions.utils.general as common
import ofscraper.actions.utils.globals as common_globals
import ofscraper.actions.utils.paths.media as media
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.cache as cache
import ofscraper.utils.hash as hash
import ofscraper.utils.settings as settings
from ofscraper.db.operations_.media import (
    download_media_update,
    prev_download_media_data,
)
from ofscraper.actions.utils.log import get_medialog
from ofscraper.actions.utils.retries import get_download_retries
from ofscraper.actions.utils.params import get_alt_params
from ofscraper.classes.sessionmanager.sessionmanager import (
    FORCED_NEW,SIGN
)
import ofscraper.utils.constants as constants





