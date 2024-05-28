import logging

import ofscraper.api.profile as profile
import ofscraper.classes.models as models
import ofscraper.commands.scraper.post as OF
import ofscraper.download.download as download
import ofscraper.models.selector as userselector
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.helpers.strings import all_paid_download_str,metadata_activity_str, all_paid_progress_metadata_str

from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")

@run
async def process_scrape_paid():
    progress_utils.update_activity_task(
                    description="Scraping Entire Paid page"
    )
    with progress_utils.setup_all_paid_database_live():
        async for ele in process_paid_dict():
            yield ele
        

async def process_paid_dict():
    user_dict = await OF.process_all_paid()
    length = len(list(user_dict.keys()))
    progress_utils.update_activity_count(totat=length, completed=0)


    for count, value in enumerate(user_dict.values()):
        yield count,value,length



def process_user_info_printer(value,length,count,all_paid_activity=None,all_paid_update=None,log_progress=None):
    model_id = value["model_id"]
    username = value["username"]

    all_paid_update=all_paid_update or all_paid_download_str
    all_paid_activity=all_paid_activity or metadata_activity_str
    log_progress=log_progress or all_paid_progress_metadata_str

    progress_utils.update_activity_count(
                totat=length,
                description=all_paid_update.format(username=username),
    )
    progress_utils.update_activity_task(
        description=(all_paid_activity.format(username=username,model_id=model_id,count=count+1,length=length)
    ))
    logging.getLogger("shared_other").warning(
        log_progress.format(username=username,model_id=model_id,count=count+1,length=length)
    )

async def process_user(value,length):
    model_id = value["model_id"]
    username = value["username"]
    posts = value["posts"]
    medias = value["medias"]

    userselector.set_ALL_SUBS_DICTVManger(
        {
            username: models.Model(
                profile.scrape_profile(model_id, refresh=False)
            )
        }
    )
    progress_utils.increment_activity_count(total=length)
    return (await download.download_process(username, model_id, medias, posts=posts))
