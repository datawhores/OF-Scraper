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
import pathlib
from humanfriendly import format_size

import ofscraper.utils.constants as constants
import ofscraper.utils.live.updater as progress_updater
from ofscraper.actions.utils.send.message import send_msg
from ofscraper.actions.utils.progress.update import update_total
import ofscraper.utils.settings as settings
import ofscraper.actions.utils.globals as common_globals
from ofscraper.actions.utils.log import get_medialog
import ofscraper.utils.config.data as config_data
import ofscraper.utils.system.free as system
from ofscraper.db.operations_.media import download_media_update


class DownloadManager:
    def __init__(self, multi=False):
        self._multi = multi

    async def _add_download_job_task(
        self, ele, total=None, placeholderObj=None, tempholderObj=None
    ):
        pathstr = str(placeholderObj.trunicated_filepath)
        task1 = None
        if not self._multi:
            task1 = progress_updater.add_download_job_task(
                f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
                total=total,
                file=tempholderObj.tempfilepath,
            )
        else:
            await send_msg(
                partial(
                    progress_updater.add_download_job_multi_task,
                    f"{(pathstr[:constants.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > constants.getattr('PATH_STR_MAX') else pathstr}\n",
                    ele.id,
                    total=total,
                    file=tempholderObj.tempfilepath,
                )
            )
        return task1

    async def _remove_download_job_task(self, task1, ele):
        if not self._multi and task1:
            progress_updater.remove_download_job_task(task1)
        elif self._multi and not task1:
            await send_msg(
                partial(progress_updater.remove_download_multi_job_task, ele.id)
            )

    async def _total_change_helper(self, *arg, **kwargs):
        if not self._multi:
            await self._normal_total_change_helper(*arg, **kwargs)
        else:
            await self._batch_total_change_helper(*arg, **kwargs)

    async def _batch_total_change_helper(self, past_total, new_total):
        if not new_total and not past_total:
            return
        elif not past_total:
            await send_msg((None, 0, new_total))
        elif past_total and new_total - past_total != 0:
            await send_msg((None, 0, new_total - past_total))

    async def _normal_total_change_helper(self, past_total, new_total):
        if not new_total and not past_total:
            return
        elif not past_total:
            await update_total(new_total)
        elif past_total and new_total - past_total != 0:
            await update_total(new_total - past_total)

    def _get_resume_header(self, resume_size, total):
        return (
            None
            if not resume_size or not total
            else {"Range": f"bytes={resume_size}-{total}"}
        )

    def _get_resume_size(self, tempholderObj, mediatype=None):
        if not settings.get_auto_resume(mediatype=mediatype):
            pathlib.Path(tempholderObj.tempfilepath).unlink(missing_ok=True)
            return 0
        return (
            0
            if not pathlib.Path(tempholderObj.tempfilepath).exists()
            else pathlib.Path(tempholderObj.tempfilepath).absolute().stat().st_size
        )

    def _resume_cleaner(self, resume_size, total, path):
        if not resume_size:
            return 0
        elif resume_size > total:
            pathlib.Path(path).unlink(missing_ok=True)
            return 0
        return resume_size

    async def _check_forced_skip(self, ele, total):
        if total is None:
            return
        total = int(total)
        if total == 0:
            return 0
        file_size_max = settings.get_size_max(mediatype=ele.mediatype)
        file_size_min = settings.get_size_min(mediatype=ele.mediatype)
        if int(file_size_max) > 0 and (int(total) > int(file_size_max)):
            ele.mediatype = "forced_skipped"
            common_globals.log.debug(
                f"{get_medialog(ele)} {format_size(total)} over size limit"
            )
            return 0
        elif int(file_size_min) > 0 and (int(total) < int(file_size_min)):
            ele.mediatype = "forced_skipped"
            common_globals.log.debug(
                f"{get_medialog(ele)} {format_size(total)} under size min"
            )
            return 0

    def _downloadspace(self, mediatype=None):
        space_limit = config_data.get_system_freesize(mediatype=mediatype)
        if space_limit > 0 and space_limit > system.get_free():
            raise Exception(constants.getattr("SPACE_DOWNLOAD_MESSAGE"))

    async def _size_checker(self, path, ele, total, name=None):
        name = name or ele.filename
        if total == 0:
            return True
        if not pathlib.Path(path).exists():
            s = f"{get_medialog(ele)} {path} was not created"
            raise Exception(s)
        elif total - pathlib.Path(path).absolute().stat().st_size > 500:
            s = f"{get_medialog(ele)} {name} size mixmatch target: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
            raise Exception(s)
        elif (total - pathlib.Path(path).absolute().stat().st_size) < 0:
            s = f"{get_medialog(ele)} {path} size mixmatch target item too large: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
            raise Exception(s)

    async def _force_download(self, ele, username, model_id):
        await download_media_update(
            ele,
            filepath=None,
            model_id=model_id,
            username=username,
            downloaded=True,
        )
