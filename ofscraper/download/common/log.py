import pathlib
import re

from humanfriendly import format_size

import ofscraper.download.common.globals as common_globals
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants


def get_medialog(ele):
    return f"Media:{ele.id} Post:{ele.postid}"


def path_to_file_logger(placeholderObj, ele, innerlog=None):
    innerlog = innerlog or common_globals.log
    innerlog.debug(
        f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('NUM_TRIES')}] filename from config {placeholderObj.filename}"
    )
    innerlog.debug(
        f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('NUM_TRIES')}] full path from config {placeholderObj.filepath}"
    )
    innerlog.debug(
        f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('NUM_TRIES')}] full path trunicated from config {placeholderObj.trunicated_filepath}"
    )


def temp_file_logger(placeholderObj, ele, innerlog=None):
    innerlog = innerlog or common_globals.log
    innerlog.debug(
        f"{get_medialog(ele)} [attempt {common_globals.attempt.get()}/{constants.getattr('NUM_TRIES')}] filename from config {placeholderObj.tempfilepath}"
    )


def get_url_log(ele):
    url = ele.url or ele.mpd
    url = re.sub("/\w{5}\w+", "/{hidden}", url)
    if ele.url:
        url = re.sub(ele.filename, "{hidden}", url)
    return url


def log_download_progress(media_type):
    if media_type is None:
        return
    if (
        common_globals.photo_count
        + common_globals.audio_count
        + common_globals.video_count
        + common_globals.forced_skipped
        + common_globals.skipped
    ) % 20 == 0:
        common_globals.log.debug(
            f"In progress -> {format_size(common_globals.total_bytes )}) ({common_globals.photo_count+common_globals.audio_count+common_globals.video_count} \
downloads total [{common_globals.video_count} videos, {common_globals.audio_count} audios, {common_globals.photo_count} photos], \
            {common_globals.forced_skipped} skipped, {common_globals.skipped} failed)"
        )


def final_log(username, log=None):
    skipped_word = (
        "skipped" if not read_args.retriveArgs().metadata else "metadata unchanged"
    )
    (log or common_globals.log).warning(
        f"[bold]{username}[/bold] ({format_size(common_globals.total_bytes )}) ({common_globals.photo_count+common_globals.audio_count+common_globals.video_count}"
        f" downloads total [{common_globals.video_count} videos, {common_globals.audio_count} audios, {common_globals.photo_count} photos], "
        f"{common_globals.forced_skipped} {skipped_word}, {common_globals.skipped} failed)"
    )


def text_log(username, value=0, fails=0, exists=0, log=None):
    (log or common_globals.log).warning(
        f"[bold]{username}[/bold] {value} text, {exists} skipped, {fails} failed"
    )
