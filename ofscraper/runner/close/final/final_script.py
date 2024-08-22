r"""
                                                             
 _______  _______         _______  _______  _______  _______  _______  _______  _______ 
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (   
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/
                                                                                      f
"""

import json
import tempfile
import logging
from collections import defaultdict
from ofscraper.classes.models import Model
import ofscraper.utils.settings as settings
import ofscraper.utils.config.data as config_data

from ofscraper.utils.system.subprocess import run


def final_script(users):
    log = logging.getLogger("shared")
    if not settings.get_post_script():
        return
    if not isinstance(users, list):
        users = [users]
    log.debug("Running post script")
    data = {}
    for ele in users:
        key=ele.model if isinstance(ele, Model) else ele["id"]
        value=ele.model if isinstance(ele, Model) else ele
        data[key] = value
    out_dict = json.dumps(
        {
            "users": data,
            "dir_format": config_data.get_dirformat(),
            "file_format": config_data.get_fileformat(),
            "metadata": config_data.get_metadata(),
        }
    )
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        with open(f.name, "w") as g:
            g.write(out_dict)
        run([settings.get_post_script(), f.name])
