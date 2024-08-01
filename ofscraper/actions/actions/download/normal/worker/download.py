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
import traceback

import ofscraper.actions.utils.globals as common_globals
from ofscraper.actions.actions.download.normal.alt_download import alt_download
from ofscraper.actions.actions.download.normal.main_download import main_download
from ofscraper.actions.utils.log import get_medialog


async def download(c, ele, model_id, username):
    try:
        if ele.url:
            data=await main_download(
                c,
                ele,
                username,
                model_id,
            )
        elif ele.mpd:
            data=await alt_download(
                c,
                ele,
                username,
                model_id,
            )
        common_globals.log.debug(f"{get_medialog(ele)} Download finished")
        return data


    except Exception as E:
        common_globals.log.debug(f"{get_medialog(ele)} exception {E}")
        common_globals.log.debug(
            f"{get_medialog(ele)} exception {traceback.format_exc()}"
        )
        return "skipped", 0
