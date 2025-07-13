import logging
from typing import List

import ofscraper.data.posts.post as OF
import ofscraper.commands.scraper.actions.download.download as download
import ofscraper.commands.metadata.metadata as metadata

import ofscraper.utils.live.updater as progress_updater
import ofscraper.utils.live.screens as progress_utils

from ofscraper.commands.utils.strings import (
    all_paid_download_str,
    all_paid_progress_download_str,
    download_activity_str,
    metadata_activity_str,
    all_paid_progress_metadata_str,
    all_paid_metadata_str,
)
from ofscraper.utils.context.run_async import run
import ofscraper.managers.manager as manager
import ofscraper.utils.settings as settings
from ofscraper.scripts.after_download_action_script import after_download_action_script

log = logging.getLogger("shared")


@run
async def scrape_paid_all() -> List[str]:
    """
    Scrapes and processes all paid content, either for metadata or download.
    """

    # Prefill modelmanager.all_models property
    # Does not effected queued models
    await manager.Manager.model_manager.sync_models(all_main_models=True)
    manager.Manager.model_manager.clear_paid_queues()
    manager.Manager.stats_manager.clear_paid_stats()

    # Set strings based on the command type for clarity.
    is_metadata_command = settings.get_settings().command == "metadata"
    if is_metadata_command:
        update_str = all_paid_metadata_str
        activity_str = metadata_activity_str
        log_progress_str = all_paid_progress_metadata_str
    else:
        update_str = all_paid_download_str
        activity_str = download_activity_str
        log_progress_str = all_paid_progress_download_str
    # Process all paid content.
    async for count, value, length in process_scrape_paid():
        process_user_info_printer(
            value,
            length,
            count,
            update_str,
            activity_str,
            log_progress_str,
        )
        await process_user(value, length)
    progress_updater.activity.update_task(visible=False)
    progress_updater.activity.update_overall(visible=False)
    progress_updater.activity.update_user(visible=False)


@run
async def process_scrape_paid():
    progress_updater.activity.update_task(description="Scraping Entire Paid page")
    async for ele in process_paid_dict():
        yield ele


async def process_paid_dict():
    user_dict = await OF.process_all_paid()
    length = len(list(user_dict.keys()))
    for count, value in enumerate(user_dict.values()):
        yield count, value, length


def process_user_info_printer(
    value,
    length,
    count,
    all_paid_activity,
    all_paid_update,
    log_progress,
):
    model_id = value["model_id"]
    username = value["username"]

    progress_updater.activity.update_task(
        description=all_paid_update.format(username=username), visible=True
    )
    progress_updater.activity.update_overall(
        description=(
            all_paid_activity.format(
                username=username, model_id=model_id, count=count + 1, length=length
            )
        ),
        total=length,
        completed=count,
        visible=True,
    )
    progress_updater.activity.update_user(visible=False)
    logging.getLogger("shared").warning(
        log_progress.format(
            username=username, model_id=model_id, count=count + 1, length=length
        )
    )


async def process_user(value, length):
    model_id = value["model_id"]
    username = value["username"]
    posts = value["posts"]
    medias = value["medias"]
    # lock activity from changing
    with progress_utils.TaskLock(progress_updater.activity, ["main", "overall"]):
        if settings.get_settings().command == "metadata":
            await manager.Manager.model_manager.add_models(
                username, activity="scrape_paid_metadata"
            )
            await metadata.metadata_process(username, model_id, medias)
            manager.Manager.stats_manager.update_and_print_stats(
                username, "scrape_paid_metadata", medias
            )
            manager.Manager.model_manager.mark_as_processed(
                username, "scrape_paid_metadata"
            )
        else:
            await manager.Manager.model_manager.add_models(
                username, activity="scrape_paid_download"
            )
            await download.download_process(username, model_id, medias, posts=posts)
            manager.Manager.stats_manager.update_and_print_stats(
                username, "scrape_paid_download", medias
            )
            manager.Manager.model_manager.mark_as_processed(
                username, "scrape_paid_download"
            )
        progress_updater.activity.update_overall(total=length, advance=1)
        after_download_action_script(username, medias, posts)
