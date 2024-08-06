
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
from functools import partial
import ofscraper.utils.constants as constants
import ofscraper.utils.live.updater as progress_updater
from ofscraper.actions.utils.send.message import send_msg
from ofscraper.actions.actions.download.utils.total import batch_total_change_helper,total_change_helper

class DownloadManager:
    def __init__(self, multi=False):
        self._multi=multi
    async def _add_download_job_task(self,ele,total,placeholderObj):
        pathstr = str(placeholderObj.tempfilepath)
        task1=None
        if not  self._multi:
            task1 = progress_updater.add_download_job_task(
                f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
                total=total,
            )
        else:
            await send_msg(
            partial(
                progress_updater.add_download_job_multi_task,
                f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
                ele.id,
                total=total,
                file=placeholderObj.tempfilepath,
            )
            )
        return task1
    
    async def _remove_download_job_task(self,task1,ele):
        if not self._multi and task1:
            progress_updater.remove_download_job_task(task1)
        elif self._multi and not task1:
            await send_msg(
                    partial(progress_updater.remove_download_multi_job_task, ele.id)
         )
    async def _total_change_helper(self,*arg,**kwargs):
        if not self._multi:
            await total_change_helper(*arg,**kwargs)
        else:
            await batch_total_change_helper(*arg,**kwargs)