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

import pathlib
import os
from humanfriendly import format_size
import psutil

import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.live.updater as progress_updater
from ofscraper.commands.scraper.actions.utils.progress.update import update_total
import ofscraper.utils.settings as settings
import ofscraper.commands.scraper.actions.utils.globals as common_globals
from ofscraper.commands.scraper.actions.utils.log import get_medialog
import ofscraper.utils.config.data as config_data
import ofscraper.utils.system.free as system
from ofscraper.db.operations_.media import download_media_update
from ofscraper.scripts.skip_download_script import skip_download_script
from ofscraper.scripts.after_download_script import after_download_script


class DownloadManager:
    def __init__(self):
        self.total = None
        self.process = psutil.Process(os.getpid())

    async def _add_download_job_task(
        self, ele, total=None, placeholderObj=None, tempholderObj=None
    ):
        pathstr = str(placeholderObj.trunicated_filepath)
        task1 = progress_updater.add_download_job_task(
            f"{(pathstr[:of_env.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > of_env.getattr('PATH_STR_MAX') else pathstr}\n",
            total=total,
            file=tempholderObj.tempfilepath,
        )
        return task1

    async def _remove_download_job_task(self, task1, ele):
        if task1:
            progress_updater.remove_download_job_task(task1)

    async def _total_change_helper(self, new_total, **kwargs):
        if not self.total and not new_total:
            return
        elif not self.total:
            await update_total(new_total)
            self.total = new_total
        elif self.total and new_total - self.total != 0:
            await update_total(new_total - self.total)
            self.total = new_total

    def _get_resume_header(self, resume_size, total):
        return (
            None
            if not resume_size or not total
            else {"Range": f"bytes={resume_size}-{total}"}
        )

    def _get_resume_size(
        self,
        tempholderObj,
    ):
        if not settings.get_settings().auto_resume:
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
        if skip_download_script(total, ele):
            return 0
        file_size_max = settings.get_settings().size_max
        file_size_min = settings.get_settings().size_min
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

    def _downloadspace(self):
        space_limit = config_data.get_system_freesize()
        if space_limit > 0 and space_limit > system.get_free():
            raise Exception(of_env.getattr("SPACE_DOWNLOAD_MESSAGE"))

    def _after_download_script(sel, filepath):
        after_download_script(filepath)

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
