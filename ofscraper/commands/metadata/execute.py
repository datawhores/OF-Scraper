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

import logging

import arrow

import ofscraper.db.operations as operations
import ofscraper.download.download as download
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.live.updater as progress_updater
from ofscraper.commands.utils.strings import mark_stray_str, metadata_activity_str
from ofscraper.db.operations_.media import (
    batch_set_media_downloaded,
    get_archived_media,
    get_messages_media,
    get_timeline_media,
)

log = logging.getLogger("shared")


# runs metadata action for specific user used by normal and --userfirst
async def execute_metadata_action_on_user(*args, ele=None, media=None, **kwargs):
    username = ele.name
    model_id = ele.id
    mark_stray = read_args.retriveArgs().mark_stray
    metadata_action = read_args.retriveArgs().metadata
    active = ele.active
    log.warning(
        f"""
                Perform Meta {metadata_action} with
                Mark Stray: {mark_stray}
                Anon Mode {read_args.retriveArgs().anon}

                for [bold]{username}[/bold]
                [bold]Subscription Active:[/bold] {active}
                """
    )
    await operations.table_init_create(model_id=model_id, username=username)
    progress_updater.update_activity_task(
        description=metadata_activity_str.format(username=username)
    )
    data = await download.download_process(username, model_id, media)
    await metadata_stray_media(username, model_id, media)
    return [data]


async def metadata_stray_media(username, model_id, media):
    if not read_args.retriveArgs().mark_stray:
        return
    all_media = []
    curr_media_set = set(map(lambda x: str(x.id), media))
    args = read_args.retriveArgs()
    progress_updater.update_activity_task(
        description=mark_stray_str.format(username=username)
    )
    if "Timeline" in args.download_area:
        all_media.extend(await get_timeline_media(model_id=model_id, username=username))
    if "Messages" in args.download_area:
        all_media.extend(await get_messages_media(model_id=model_id, username=username))
    if "Archived" in args.download_area:
        all_media.extend(await get_archived_media(model_id=model_id, username=username))
    if not bool(all_media):
        return
    filtered_media = list(
        filter(
            lambda x: str(x["media_id"]) not in curr_media_set
            and arrow.get(x.get("posted_at") or 0).is_between(
                arrow.get(args.after or 0), args.before
            )
            and x.get("downloaded") != 1
            and x.get("unlocked") != 0,
            all_media,
        )
    )
    log.info(f"Found {len(filtered_media)} stray items to mark as locked")
    batch_set_media_downloaded(filtered_media, model_id=model_id, username=username)
