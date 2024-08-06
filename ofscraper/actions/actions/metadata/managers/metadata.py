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
from ofscraper.actions.utils.log import get_medialog
from ofscraper.actions.actions.metadata.utils.change import change_metadata
from ofscraper.actions.utils.log import (
    set_media_log,
)


class  MetaDataManager:
    def __init__(self,multi=False):
        self._multi=multi
    async def metadata(self,c, ele, model_id, username):
        try:
            self._prepare()
            return await change_metadata(c, ele, username, model_id)
        except Exception as E:
            common_globals.log.debug(f"{get_medialog(ele)} exception {E}")
            common_globals.log.debug(
                f"{get_medialog(ele)} exception {traceback.format_exc()}"
            )
            common_globals.log.traceback_(f"{get_medialog(ele)} Metadata Failed\n")
            return "skipped", 0
    def _prepare(self,ele):
        if self._multi:
            set_media_log(common_globals.log, ele)
            common_globals.attempt.set(0)
