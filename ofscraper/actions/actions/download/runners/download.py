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
from ofscraper.actions.actions.download.managers.alt_download import AltDownloadManager
from ofscraper.actions.actions.download.managers.main_download import (
    MainDownloadManager,
)
from ofscraper.actions.utils.log import get_medialog


async def download(c, ele, model_id, username, multi=False):
    try:
        data = None
        if ele.url:
            data = await MainDownloadManager(multi=multi).main_download(
                c,
                ele,
                username,
                model_id,
            )
        elif ele.mpd:
            data = await AltDownloadManager(multi=multi).alt_download(
                c, ele, username, model_id
            )
        common_globals.log.debug(f"{get_medialog(ele)} Download finished")
        return data
    except Exception as E:
        common_globals.log.debug(f"{get_medialog(ele)} exception {E}")
        common_globals.log.debug(
            f"{get_medialog(ele)} exception {traceback.format_exc()}"
        )
        return "skipped", 0
