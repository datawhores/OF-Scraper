import subprocess

import arrow

import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.download.shared.common.general as common
import ofscraper.download.shared.globals as common_globals
import ofscraper.download.shared.utils.keyhelpers as keyhelpers
import ofscraper.download.shared.utils.log as common_logs
import ofscraper.download.shared.utils.paths as common_paths
import ofscraper.utils.dates as dates
import ofscraper.utils.settings as settings
import ofscraper.utils.system.system as system
from ofscraper.db.operations_.media import download_media_update


async def handle_result_alt(
    sharedPlaceholderObj, ele, audio, video, username, model_id
):
    tempPlaceholder = await placeholder.tempFilePlaceholder(
        ele, f"temp_{ele.id or await ele.final_filename}.mp4"
    ).init()
    temp_path = tempPlaceholder.tempfilepath
    temp_path.unlink(missing_ok=True)
    t = subprocess.run(
        [
            settings.get_ffmpeg(),
            "-i",
            str(video["path"]),
            "-i",
            str(audio["path"]),
            "-c",
            "copy",
            "-movflags",
            "use_metadata_tags",
            str(temp_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if t.stderr.decode().find("Output") == -1:
        common_globals.log.debug(f"{common_logs.get_medialog(ele)} ffmpeg failed")
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} ffmpeg {t.stderr.decode()}"
        )
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} ffmpeg {t.stdout.decode()}"
        )

    video["path"].unlink(missing_ok=True)
    audio["path"].unlink(missing_ok=True)

    common_globals.log.debug(
        f"Moving intermediate path {temp_path} to {sharedPlaceholderObj.trunicated_filepath}"
    )
    common_paths.moveHelper(temp_path, sharedPlaceholderObj.trunicated_filepath, ele)
    (
        common_paths.addGlobalDir(sharedPlaceholderObj.filedir)
        if system.get_parent_process()
        else common_paths.addLocalDir(sharedPlaceholderObj.filedir)
    )
    if ele.postdate:
        newDate = dates.convert_local_time(ele.postdate)
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}"
        )
        common_paths.set_time(sharedPlaceholderObj.trunicated_filepath, newDate)
        common_globals.log.debug(
            f"{common_logs.get_medialog(ele)} Date set to {arrow.get(sharedPlaceholderObj.trunicated_filepath.stat().st_mtime).format('YYYY-MM-DD HH:mm')}"
        )
    if ele.id:
        await download_media_update(
            ele,
            filename=sharedPlaceholderObj.trunicated_filepath,
            model_id=model_id,
            username=username,
            downloaded=True,
            hashdata=await common.get_hash(
                sharedPlaceholderObj, mediatype=ele.mediatype
            ),
        )
    common.add_additional_data(sharedPlaceholderObj, ele)
    return ele.mediatype, video["total"] + audio["total"]


async def media_item_post_process_alt(audio, video, ele, username, model_id):
    if (audio["total"] + video["total"]) == 0:
        if ele.mediatype != "forced_skipped":
            await common.force_download(ele, username, model_id)
        return ele.mediatype, 0
    for m in [audio, video]:
        m["total"] = common.get_item_total(m)

    for m in [audio, video]:
        if not isinstance(m, dict):
            return m
        await common.size_checker(m["path"], ele, m["total"])


async def media_item_keys_alt(c, audio, video, ele):
    for item in [audio, video]:
        item = await keyhelpers.un_encrypt(item, c, ele)
