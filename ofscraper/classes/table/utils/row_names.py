import re

import ofscraper.utils.constants as constants


def row_names():
    for ele in row_names_all():
        if re.search("^number$", ele, re.IGNORECASE):
            continue
        yield ele


def row_names_all():
    for ele in constants.getattr("ROW_NAMES"):
        yield ele.lower()
