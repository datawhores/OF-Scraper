import re
import os

from humanfriendly import format_size

import ofscraper.actions.utils.globals as common_globals
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants


def get_medialog(ele):
    if not ele:
        return ""
    return f"PID: {os.getpid()} Media:{ele.id} Post:{ele.postid}"


def path_to_file_logger(placeholderObj, ele, innerlog=None):
    innerlog = innerlog or common_globals.log
    innerlog.debug(
        f"{get_medialog(ele)} \\[attempt {common_globals.attempt.get()}/{constants.getattr('API_NUM_TRIES')}] filename from config {placeholderObj.filename}"
    )
    innerlog.debug(
        f"{get_medialog(ele)} \\[attempt {common_globals.attempt.get()}/{constants.getattr('API_NUM_TRIES')}] full path from config {placeholderObj.filepath}"
    )
    innerlog.debug(
        f"{get_medialog(ele)} \\[attempt {common_globals.attempt.get()}/{constants.getattr('API_NUM_TRIES')}] full path trunicated from config {placeholderObj.trunicated_filepath}"
    )


def temp_file_logger(placeholderObj, ele, innerlog=None):
    innerlog = innerlog or common_globals.log
    innerlog.debug(
        f"{get_medialog(ele)} \\[attempt {common_globals.attempt.get()}/{constants.getattr('API_NUM_TRIES')}] filename from config {placeholderObj.tempfilepath}"
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


def final_log(username, log=None):
    log = log or common_globals.log
    log.error("\n")
    log.error(final_log_text(username))
    log.error("\n")


def final_log_text(
    username,
    photo_count=0,
    audio_count=0,
    video_count=0,
    forced_skipped_count=0,
    skipped_count=0,
    total_bytes_downloaded=0,
):
    photo_count = photo_count or common_globals.photo_count
    audio_count = audio_count or common_globals.audio_count
    video_count = video_count or common_globals.video_count
    skipped_count = skipped_count or common_globals.skipped
    forced_skipped_count = forced_skipped_count or common_globals.forced_skipped
    total_bytes_downloaded = (
        total_bytes_downloaded or common_globals.total_bytes_downloaded
    )
    total_count = photo_count + audio_count + video_count

    size_log = _get_size_log(total_bytes_downloaded)

    photo_log = _section_log_helper(photo_count, "photos")
    audio_log = _section_log_helper(audio_count, "audios")
    video_log = _section_log_helper(video_count, "videos")
    failed_log = _section_log_helper(skipped_count, "failed", color="red")
    total_log = _get_total_log(total_count)
    action = _get_action()

    skipped_log = _get_forced_skipped_log(forced_skipped_count)

    outer_color = _get_outer_color(audio_count, video_count, photo_count)

    return f"[{outer_color}]\\[{username}]\\[Action {action}] ({size_log}) ({total_log}\\[{video_log}, {audio_log}, {photo_log}], {skipped_log}, {failed_log}))[/{outer_color}]"


def _get_outer_color(audio_count, video_count, photo_count):
    return (
        "white"
        if (audio_count + video_count + photo_count) == 0
        else "bold deep_sky_blue2"
    )


def _get_size_log(total_bytes_downloaded):
    color = "white" if total_bytes_downloaded == 0 else "bold green"
    return f"[{color}]{format_size(total_bytes_downloaded )}[/{color}]"


def _get_total_log(total_count):
    color = "white" if total_count == 0 else "bold green"
    if read_args.retriveArgs().metadata:
        total = f"[{color}]{total_count} changed media item total [/{color}]"
    else:
        total = f"[{color}]{total_count} downloads total [/{color}]"
    return total


def _get_action():
    if read_args.retriveArgs().metadata:
        return "Metadata"

    return "Download"


def _get_forced_skipped_log(forced_skipped_count):
    color = "white" if forced_skipped_count == 0 else "bold yellow"
    if read_args.retriveArgs().metadata:
        skipped_log = (
            f"[{color}]{forced_skipped_count} metadata unchanged[/{color}]"
            if forced_skipped_count > 0
            else f"{forced_skipped_count} items unchanged"
        )
    else:
        skipped_log = (
            f"[bold yellow]{forced_skipped_count} skipped[/bold yellow]"
            if forced_skipped_count > 0
            else f"{forced_skipped_count} skipped"
        )
    return skipped_log


def _section_log_helper(count, area, color="green"):
    return (
        f"[bold {color}]{count} {area}[/bold {color}]"
        if count > 0
        else f"{count} {area}"
    )


def text_log(username, value=0, fails=0, exists=0, log=None):
    outer_color = "white" if (value + fails + exists) == 0 else "bold deep_sky_blue2"
    text_log = _section_log_helper(value, "text")
    exists_log = _section_log_helper(exists, "skipped")
    fails_log = _section_log_helper(fails, "failed", color="red")
    val = f"[{outer_color}]\\[{username}]\\[Action Text Download] \\[{text_log}, {exists_log}, {fails_log}][/{outer_color}]"
    (log or common_globals.log).warning(val)
    return val


def set_media_log(log, ele):
    ele.log = log
