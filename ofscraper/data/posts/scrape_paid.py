import logging
from typing import List

import ofscraper.data.posts.post as OF
import ofscraper.commands.scraper.actions.download.download as download
import ofscraper.commands.metadata.metadata as metadata

import ofscraper.utils.live.screens as progress_utils
import ofscraper.utils.live.updater as progress_updater
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
activity = "scrape_paid"


@run
async def scrape_paid_all() -> List[str]:
    """
    Scrapes and processes all paid content, either for metadata or download.
    """

    # Prefill modelmanager.all_models property
    # Does not effected queued models
    await manager.Manager.model_manager.sync_models(all_main_models=True)
    manager.Manager.model_manager.clear_paid_queues()

    # Set strings based on the command type for clarity.
    is_metadata_command = settings.get_settings().command == "metadata"
    if is_metadata_command:
        update_str = all_paid_metadata_str
        activity_str = metadata_activity_str
        log_progress_str = all_paid_progress_metadata_str
        actions="metadata"
    else:
        update_str = all_paid_download_str
        activity_str = download_activity_str
        log_progress_str = all_paid_progress_download_str
        actions="download"
    # Process all paid content.
    async for count, value, length in process_scrape_paid(actions):
        process_user_info_printer(
            value,
            length,
            count,
            all_paid_update=update_str,
            all_paid_activity=activity_str,
            log_progress=log_progress_str,
        )
        await process_user(value, length)


@run
async def process_scrape_paid(actions):
    progress_updater.update_activity_task(description="Scraping Entire Paid page")
    with progress_utils.setup_all_paid_database_live():
        async for ele in process_paid_dict():
            yield ele


async def process_paid_dict(actions):
    user_dict = await OF.process_all_paid(actions)
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
    desc = progress_updater.get_activity_description()
    # Manually search for model, and queue
    await manager.Manager.model_manager.add_models(username, activity=activity)
    progress_updater.update_activity_task(description=desc)
    if settings.get_settings().command == "metadata":
        data = await metadata.metadata_process(username, model_id, medias)
    else:
        data, _ = await download.download_process(
            username, model_id, medias, posts=posts
        )
    data = []
    # mark queued model as done
    manager.Manager.model_manager.mark_as_processed(username, activity=activity)
    progress_updater.increment_activity_count(total=length)
    after_download_action_script(username, medias, posts)
    return data
