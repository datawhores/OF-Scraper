import re

from humanfriendly import format_size

import ofscraper.download.shared.globals.globals as common_globals
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants


def get_medialog(ele):
    return f"Media:{ele.id} Post:{ele.postid}"


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
    (log or common_globals.log).error(
            final_log_text(username)
    )

def final_log_text(username):
    total_count=common_globals.audio_count+common_globals.photo_count+common_globals.video_count
    size_log=f"[green]{format_size(common_globals.total_bytes )}[/green]"

    
    photo_log=f"[green]{common_globals.photo_count} photos[/green]"if common_globals.photo_count>0 else f"{common_globals.photo_count} photos"

    audio_log=f"[green]{common_globals.audio_count} audios[/green]"if common_globals.audio_count>0 else f"{common_globals.audio_count} audios"


    video_log=f"[green]{common_globals.video_count} videos[/green]"if common_globals.video_count>0 else f"{common_globals.video_count} videos"


    failed_log=f"[red]{common_globals.video_count} failed[/red]"if common_globals.skipped>0 else f"{common_globals.skipped} failed"

    log_format=None
    skipped_log=""
    if read_args.retriveArgs().metadata:
        log_format="[blue][bold]\\[{username}][/bold] [bold]\\[Action Metadata][/bold] ({size_log}) ([green]{total_count} changed media item total[/green]\\[{video_log}, {audio_log}, {photo_log}], {skipped_log}, {failed_log}))[/blue]"
        skipped_log=f"[yellow]{common_globals.skipped} metadata unchanged[/yellow]"if common_globals.skipped>0 else f"{common_globals.forced_skipped} items unchanged"
    else:
        log_format="[blue][bold]\\[{username}][/bold][bold]\\[Action Download][/bold] ({size_log}) ([green]{total_count} downloads total[/green]\\[{video_log}, {audio_log}, {photo_log}], {skipped_log}, {failed_log}))[/blue]"
        skipped_log=f"[yellow]{common_globals.video_count} skipped[/yellow]"if common_globals.skipped>0 else f"{common_globals.forced_skipped} skipped"

    return log_format.format(username=username,total_count=total_count,video_log=video_log,audio_log=audio_log,skipped_log=skipped_log,failed_log=failed_log,photo_log=photo_log,size_log=size_log)

        

def empty_log(username):

    if read_args.retriveArgs().metadata:
        return f"[white][bold]\\[{username}][/bold] [bold]\\[Action Metadata][/bold] ({0} MB) ({0}  changed media items total \\[{0}  videos, {0}  audios, {0}  photos], {0}  items unchanged, {0}  failed))[/white]"
    else:
        return f"[white][bold]\\[{username}][/bold] [bold]\\[Action Download][/bold] ({0} MB) ({0}  downloads total \\[{0}  videos, {0}  audios, {0}  photos], {0}  skipped, {0}  failed))[/white]"







def text_log(username, value=0, fails=0, exists=0, log=None):
    (log or common_globals.log).warning(
        f"[bold]{username}[/bold] {value} text, {exists} skipped, {fails} failed"
    )
