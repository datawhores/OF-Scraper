import argparse
import pathlib
import re
import sys

import arrow
from humanfriendly import parse_size

import ofscraper.utils.config.data as config_data
import ofscraper.utils.system.system as system
from ofscraper.__version__ import __version__
from ofscraper.const.constants import KEY_OPTIONS, OFSCRAPER_RESERVED_LIST

args = None
