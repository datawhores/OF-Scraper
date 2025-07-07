import re
import os

from humanfriendly import format_size

import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.of_env.of_env as of_env


def get_medialog(ele):
    if not ele:
        return ""
    return f"PID: {os.getpid()} Media:{ele.id} Post:{ele.post_id}"


def path_to_file_logger(placeholderObj, ele, innerlog=None):
    innerlog = innerlog or common_globals.log
    innerlog.debug(
        f"{get_medialog(ele)} \\[attempt {common_globals.attempt.get()}/{of_env.getattr('API_NUM_TRIES')}] filename from config {placeholderObj.filename}"
    )
    innerlog.debug(
        f"{get_medialog(ele)} \\[attempt {common_globals.attempt.get()}/{of_env.getattr('API_NUM_TRIES')}] full path from config {placeholderObj.filepath}"
    )
    innerlog.debug(
        f"{get_medialog(ele)} \\[attempt {common_globals.attempt.get()}/{of_env.getattr('API_NUM_TRIES')}] full path trunicated from config {placeholderObj.trunicated_filepath}"
    )


def temp_file_logger(placeholderObj, ele, innerlog=None):
    innerlog = innerlog or common_globals.log
    innerlog.debug(
        f"{get_medialog(ele)} \\[attempt {common_globals.attempt.get()}/{of_env.getattr('API_NUM_TRIES')}] filename from config {placeholderObj.tempfilepath}"
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
downloads total \\[{common_globals.video_count} videos, {common_globals.audio_count} audios, {common_globals.photo_count} photos], \
            {common_globals.forced_skipped} skipped, {common_globals.skipped} failed)"
        )
