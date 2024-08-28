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
from ofscraper.classes.models import Model
import ofscraper.utils.settings as settings
import ofscraper.utils.config.data as config_data

from ofscraper.utils.system.subprocess import run
import  ofscraper.runner.manager as manager



def final_script():
    log = logging.getLogger("shared")
    if not settings.get_post_script():
        return
    log.debug("Running post script")

    out_dict = json.dumps(
        {
            "users": {key: value.model for key, value in manager.Manager.model_manager.all_subs_dict.items()},
            "dir_format": config_data.get_dirformat(),
            "file_format": config_data.get_fileformat(),
            "metadata": config_data.get_metadata(),
        }
    )
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        with open(f.name, "w") as g:
            g.write(out_dict)
        run([settings.get_post_script(), f.name])
