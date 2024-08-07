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
import logging
from ofscraper.classes.models import Model
import ofscraper.utils.settings as settings
import ofscraper.utils.config.data as config_data

from ofscraper.utils.system.subprocess  import run

def final_script(users):
    log = logging.getLogger("shared")
    if not settings.post_script():
        return
    if not isinstance(users, list):
        users=[users]
    log.debug("Running post script")
    data=[]
    for ele  in users:
        if isinstance(ele,Model):
            data.append(ele.model)
        elif isinstance(ele,dict):
            data.append(ele)
    out_dict={"users":users,
             "dir_format":config_data.get_dirformat(),
             "file_format":config_data.get_fileformat(),
             "metadata":config_data.get_metadata()
             }
    run(
            [
                settings.post_script(),
                json.dumps(out_dict)
            ]
    )
