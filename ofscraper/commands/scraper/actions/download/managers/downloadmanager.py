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
from ofscraper.scripts.skip_download_script import (
    SKIP_PERMANENT,
    skip_download_script,
)
from ofscraper.scripts.after_download_script import after_download_script
from ofscraper.commands.scraper.actions.download.utils.retries import NoRetry


class StartOver(Exception):
    """A reply that can't continue the part on disk. The part has been deleted,
    so the next request downloads the file from the start."""


class ErrorReply(NoRetry):
    """The server answered with an error status (a 404, say), or with an
    empty reply. Its body isn't the file: nothing is written, the part on disk is kept,
    and the item is left for the next run. Retrying now would only delete the
    part (each retry starts from an empty one), so it isn't retried."""


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

    def _get_resume_header(self, resume_size, total, validator=None):
        if not resume_size or not total:
            return None
        headers = {"Range": f"bytes={resume_size}-"}
        if validator:
            # if the file isn't the one the part was started from, the server
            # sends all of it (200) instead of the rest (206)
            headers["If-Range"] = validator
        return headers

    def _validator(self, r):
        """What identifies this version of the file, for If-Range: a strong
        ETag, else Last-Modified. A weak ETag can't be used in If-Range, and
        a date mustn't be sent there when the server has an ETag, even a weak
        one (RFC 9110, 13.1.5), so then there's none."""
        etag = (r.headers.get("etag") or "").strip()
        if etag:
            return None if etag.startswith("W/") else etag
        return (r.headers.get("last-modified") or "").strip() or None

    def _check_status(self, r, ele, headers):
        """Raise ErrorReply for a reply that isn't the file. The session
        raises for most error statuses itself but hands a 404 back, and a 416
        to a ranged request, which _full_size_from_reply handles."""
        if 200 <= r.status < 300:
            length = (r.headers.get("content-length") or "").strip()
            if r.status == 204 or length == "0":
                # an empty reply isn't the file either; as a 0-byte size it
                # would read as "skipped" and be marked as downloaded (#267)
                raise ErrorReply(
                    f"{get_medialog(ele)} the server sent an empty reply "
                    f"({r.status}), not downloaded"
                )
            return
        if r.status == 416 and "Range" in (headers or {}):
            return
        raise ErrorReply(
            f"{get_medialog(ele)} the server answered {r.status}, not downloaded"
        )

    def _full_size_from_reply(self, r, resume_size, path, saved_total=None):
        """Return (total, resume_size) for the reply to a request that may have
        asked for a range.

        A 206 reply carries only the missing bytes, so its Content-Length is the
        size of that piece, not of the file. The full size comes from
        Content-Range, or from the part on disk plus Content-Length. A server
        that ignores Range answers 200 with the whole file, so the download
        starts again from 0 instead of appending: resume_size comes back as 0,
        and the writer replaces the part once the reply's first bytes arrive.
        Until then the part is kept, so an empty reply doesn't lose it (#271).

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

    async def _check_forced_skip(self, ele, total, before=0, track=None):
        """0 if the file isn't downloaded. before is the size of the item's
        parts already downloaded (a DRM video's audio track), which the size
        limits add to total; None checks no size limits. track names a DRM
        video's track, for skip_download_script's answer."""
        if total is None:
            return
        total = int(total)
        if total == 0:
            return 0
        if await self._script_skips(ele, total, track):
            return 0
        if before is None:
            return
        size = total + int(before)
        file_size_max = settings.get_settings().size_max
        file_size_min = settings.get_settings().size_min
        if int(file_size_max) > 0 and (size > int(file_size_max)):
            ele.mediatype = "Forced_skipped"
            common_globals.log.debug(
                f"{get_medialog(ele)} {format_size(size)} over size limit"
            )
            return 0
        elif int(file_size_min) > 0 and (size < int(file_size_min)):
            ele.mediatype = "Forced_skipped"
            common_globals.log.debug(
                f"{get_medialog(ele)} {format_size(size)} under size min"
            )
            return 0

    async def _script_skips(self, ele, total, track=None):
        """skip_download_script's answer for the file (or a DRM video's
        track) at this size. It's asked once per run: the check on the saved
        size, the one on the reply and those of retries get the answer it
        gave (#350). run.download starts each download call with no
        answers, so a later run, or the check table sending the item
        again, asks again."""
        answers = ele.skip_script_answers
        key = (track, total)
        if key not in answers:
            answer = await skip_download_script(total, ele)
            answers[key] = answer if answer == SKIP_PERMANENT else bool(answer)
        return answers[key]

    def _skipped_by_script(self, ele):
        """How skip_download_script skipped the item in this run: None (it
        didn't), True (for this run) or SKIP_PERMANENT (for good)."""
        answers = ele.skip_script_answers.values()
        if SKIP_PERMANENT in answers:
            return SKIP_PERMANENT
        return True if any(answers) else None

    async def _script_skip_result(self, ele, username, model_id):
        """The result of an item skip_download_script skipped: counted as
        skipped. A skip for this run isn't saved, so the next run asks the
        script again (#351); a permanent one is saved as done, with no
        file, as every script skip was before."""
        if self._skipped_by_script(ele) == SKIP_PERMANENT:
            await self._force_download(ele, username, model_id, skip_permanent=True)
        return "forced_skipped", 0

    def _skipped_by_size(self, ele, error):
        """True if the size limits have already skipped the item in this
        attempt. An error after that (saving the reply's headers to the
        cache, say) doesn't undo the skip: the attempt ends as a skip, with
        no retry. A retry can't work anyway for a DRM video: the skip leaves
        it no manifest (#345)."""
        # read with getattr: this runs while handling the error, and mustn't
        # replace it with another
        if getattr(ele, "mediatype", None) != "Forced_skipped":
            return False
        common_globals.log.debug(
            f"{get_medialog(ele)} skipped by the size limits, ignoring a later error: {error}"
        )
        return True

    def _check_same_file(self, r, resume_size, path, saved_validator):
        """After a 206 (resume_size set), start over if the reply's ETag or
        Last-Modified isn't the one saved with the part. If-Range should have
        made the server send the whole new file, but a server that ignores it
        sends the rest of the new file instead."""
        validator = self._validator(r)
        if resume_size and saved_validator and validator and validator != saved_validator:
            self._start_over(
                path,
                f"the file changed on the server ({saved_validator} -> {validator})",
            )

    def _downloadspace(self):
        if not system.check_free_size():
            raise Exception(of_env.getattr("SPACE_DOWNLOAD_MESSAGE"))

    async def _after_download_script(self, filepath):
        await after_download_script(filepath)

    def _size_written(self, ele, size):
        """The size of a file whose reply didn't say how big it was (no
        Content-Length, chunked): the bytes the writer wrote from 0. The
        transfer's own end-of-data marks the end of the file, so what was
        written is the file. An empty reply is an error, not a 0-byte file: 0
        means "skipped" to the callers."""
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

    async def _force_download(self, ele, username, model_id, skip_permanent=None):
        """Save the item as downloaded with no file. skip_permanent marks a
        permanent skip_download_script skip, so it can be told apart."""
        await mark_media_as_downloaded(
            ele,
            filepath=None,
            model_id=model_id,
            username=username,
            downloaded=True,
            skip_permanent=skip_permanent,
        )
