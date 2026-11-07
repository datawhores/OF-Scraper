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
import ofscraper.utils.system.free as system
from ofscraper.db.operations_.media import mark_media_as_downloaded
from ofscraper.scripts.skip_download_script import skip_download_script
from ofscraper.scripts.after_download_script import after_download_script


class StartOver(Exception):
    """A reply that can't continue the part on disk. The part has been deleted,
    so the next request downloads the file from the start."""


class DownloadManager:
    def __init__(self):
        self.total = None
        self.process = psutil.Process(os.getpid())

    async def _add_download_job_task(
        self, ele, total=None, placeholderObj=None, tempholderObj=None
    ):
        pathstr = str(placeholderObj.trunicated_filepath)
        task1 = progress_updater.download.add_job_task(
            f"{(pathstr[:of_env.getattr('PATH_STR_MAX')] + '....') if len(pathstr) > of_env.getattr('PATH_STR_MAX') else pathstr}\n",
            total=total,
            file=tempholderObj.tempfilepath,
        )
        return task1

    async def _remove_download_job_task(self, task1, ele):
        if task1:
            progress_updater.download.remove_job_task(task1)

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
            else {"Range": f"bytes={resume_size}-"}
        )

    def _full_size_from_reply(self, r, resume_size, path, saved_total=None):
        """Return (total, resume_size) for the reply to a request that may have
        asked for a range.

        A 206 reply carries only the missing bytes, so its Content-Length is the
        size of that piece, not of the file. The full size comes from
        Content-Range, or from the part on disk plus Content-Length. A server
        that ignores Range answers 200 with the whole file, so the part on disk
        is dropped and the download starts again from 0 instead of appending.

        saved_total is the size saved when the part was started. If the reply
        is for a file of another size (the file changed on the server, or the
        part was written by an older version that saved the wrong size), or it
        can't be lined up with the part at all, the part is deleted and
        StartOver is raised so the caller downloads the file from the start.
        """
        length = r.headers.get("content-length")
        length = int(length) if length is not None else None
        if length is None and 200 <= r.status < 300 and r.status != 206:
            self._require_chunked(r, path)
        if not resume_size:
            return length, 0
        content_range = (r.headers.get("content-range") or "").strip()
        sent, _, full = content_range.removeprefix("bytes ").partition("/")
        full = full.strip()
        if r.status == 416:
            # nothing left to send from resume_size on: the part isn't the
            # start of the file the server has now
            self._start_over(path, f"the server answered 416 ({content_range})")
        if r.status != 206:
            pathlib.Path(path).unlink(missing_ok=True)
            return length, 0
        start = sent.split("-")[0].strip()
        if start and start != str(resume_size):
            self._start_over(
                path,
                f"resume asked for bytes from {resume_size} but the server sent {content_range}",
            )
        if full.isdigit():
            total = int(full)
        elif length is not None:
            total = resume_size + length
        else:
            self._start_over(path, "the reply doesn't give the file size")
        if saved_total and total != int(saved_total):
            self._start_over(
                path,
                f"the file is {total} bytes but the part was started from a {saved_total}-byte file",
            )
        return total, resume_size

    def _start_over(self, path, reason):
        pathlib.Path(path).unlink(missing_ok=True)
        raise StartOver(f"can't resume, downloading from the start: {reason}")

    def _require_chunked(self, r, path):
        """A reply with no Content-Length is only taken if it's chunked: a
        chunked transfer marks its own end, so a cut-off one fails. A reply
        that just ends when the connection closes can't be told apart from
        one cut off halfway, so it fails before anything is written, and
        the part on disk is left as it was."""
        encoding = (r.headers.get("transfer-encoding") or "").lower()
        if "chunked" in encoding:
            return
        message = (
            f"{pathlib.Path(path).name}: the server sent no file size and didn't "
            "send the file chunked, so a cut-off download can't be detected; "
            "not downloaded, the .part is kept"
        )
        common_globals.log.info(message)
        raise Exception(message)

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
        elif total is None or resume_size > total:
            # with no saved size there's nothing to check the part against
            pathlib.Path(path).unlink(missing_ok=True)
            return 0
        return resume_size

    async def _check_forced_skip(self, ele, total):
        if total is None:
            return
        total = int(total)
        if total == 0:
            return 0
        if await skip_download_script(total, ele):
            return 0
        file_size_max = settings.get_settings().size_max
        file_size_min = settings.get_settings().size_min
        if int(file_size_max) > 0 and (int(total) > int(file_size_max)):
            ele.mediatype = "Forced_skipped"
            common_globals.log.debug(
                f"{get_medialog(ele)} {format_size(total)} over size limit"
            )
            return 0
        elif int(file_size_min) > 0 and (int(total) < int(file_size_min)):
            ele.mediatype = "Forced_skipped"
            common_globals.log.debug(
                f"{get_medialog(ele)} {format_size(total)} under size min"
            )
            return 0

    def _downloadspace(self):
        if not system.check_free_size():
            raise Exception(of_env.getattr("SPACE_DOWNLOAD_MESSAGE"))

    async def _after_download_script(self, filepath):
        await after_download_script(filepath)

    def _size_written(self, ele, path):
        """The size of a file whose reply didn't say how big it was (no
        Content-Length, chunked). The transfer's own end-of-data marks the end
        of the file, so what was written is the file. An empty reply is an
        error, not a 0-byte file: 0 means "skipped" to the callers."""
        size = pathlib.Path(path).stat().st_size if pathlib.Path(path).exists() else 0
        if not size:
            raise Exception(
                f"{get_medialog(ele)} the server sent no data and no file size"
            )
        return size

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
        await mark_media_as_downloaded(
            ele,
            filepath=None,
            model_id=model_id,
            username=username,
            downloaded=True,
        )
