import logging

import ofscraper.data.posts.post as OF
import ofscraper.actions.actions.download.download as download
import ofscraper.actions.actions.metadata.metadata as metadata

import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
from ofscraper.commands.utils.strings import (
    all_paid_download_str,
    all_paid_progress_metadata_str,
    metadata_activity_str,
    download_activity_str,
    all_paid_progress_download_str,
)
from ofscraper.utils.context.run_async import run
from ofscraper.runner.close.final.final_user import post_user_script
from ofscraper.utils.args.accessors.command import get_command




log = logging.getLogger("shared")


@run
async def scrape_paid_all():
    out = ["[bold yellow]Scrape Paid Results[/bold yellow]"]
    await manager.Manager.model_manager.all_subs_retriver()
    async for count, value, length in process_scrape_paid():
        process_user_info_printer(
            value,
            length,
            count,
            all_paid_update=all_paid_download_str,
            all_paid_activity=download_activity_str,
            log_progress=all_paid_progress_download_str,
        )
        out.append(await process_user(value, length))
    return out


@run
async def process_scrape_paid():
    progress_updater.update_activity_task(description="Scraping Entire Paid page")
    with progress_utils.setup_all_paid_database_live():
        async for ele in process_paid_dict():
            yield ele


async def process_paid_dict():
    user_dict = await OF.process_all_paid()
    length = len(list(user_dict.keys()))
    progress_updater.update_activity_count(totat=length, completed=0)

    for count, value in enumerate(user_dict.values()):
        yield count, value, length


def process_user_info_printer(
    value,
    length,
    count,
    all_paid_activity=None,
    all_paid_update=None,
    log_progress=None,
):
    model_id = value["model_id"]
    username = value["username"]

    all_paid_update = all_paid_update or all_paid_download_str
    all_paid_activity = all_paid_activity or metadata_activity_str
    log_progress = log_progress or all_paid_progress_metadata_str

    progress_updater.update_activity_count(
        totat=length,
        description=all_paid_update.format(username=username),
    )
    progress_updater.update_activity_task(
        description=(
            all_paid_activity.format(
                username=username, model_id=model_id, count=count + 1, length=length
            )
        )
    )
    logging.getLogger("shared_other").warning(
        log_progress.format(
            username=username, model_id=model_id, count=count + 1, length=length
        )
    )


async def process_user(value, length):
    model_id = value["model_id"]
    username = value["username"]
    posts = value["posts"]
    medias = value["medias"]
    if get_command()=="metadata":
        data=await metadata.metadata_process(username, model_id,medias,posts=posts)
    else:
        data, _ =await download.download_process(username,model_id, medias, posts=posts)
    progress_updater.increment_activity_count(total=length)
    post_user_script(value, medias, posts)
    return data
