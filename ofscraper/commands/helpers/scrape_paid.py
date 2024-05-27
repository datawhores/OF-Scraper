import logging
import time

import ofscraper.api.profile as profile
import ofscraper.classes.models as models
import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.post as OF
import ofscraper.download.download as download
import ofscraper.models.selector as userselector
import ofscraper.utils.constants as constants
import ofscraper.utils.live.screens as progress_utils
from ofscraper.commands.helpers.strings import all_paid_download_str
from ofscraper.utils.context.run_async import run

log = logging.getLogger("shared")

@run
async def process_scrape_paid(download_progress_message=None,log_progress_message=None):
    progress_utils.update_activity_task(
                    description="[bold yellow]Scraping Entire Paid page[/bold yellow]"
    )
    oldUsers = userselector.get_ALL_SUBS_DICT()
    with progress_utils.setup_all_paid_database_live():
        data=await process_paid_dict(download_progress_message=download_progress_message,log_progress_message=log_progress_message)
        
    # restore og users
    userselector.set_ALL_SUBS_DICT(oldUsers)
    return data

async def process_paid_dict(download_progress_message=None,log_progress_message=None):
    user_dict = await OF.process_all_paid()
    length = len(list(user_dict.keys()))
    progress_utils.update_activity_count(totat=length, completed=0)

    out=["[bold yellow]Scrape Paid Results[/bold yellow]"]

    for count, value in enumerate(user_dict.values()):
            model_id = value["model_id"]
            username = value["username"]
            posts = value["posts"]
            medias = value["medias"]
            progress_utils.update_activity_count(
                totat=length,
                description=all_paid_download_str.format(username=username),
            )
            if  download_progress_message:
                progress_utils.update_activity_task(
                    description=(download_progress_message.format(name=username,model_id=model_id,count=count+1,length=length)
                ))
            if log_progress_message:
                logging.getLogger("shared_other").warning(
                   log_progress_message.format(username=username,model_id=model_id,count=count+1,length=length)
                )
            userselector.set_ALL_SUBS_DICTVManger(
                {
                    username: models.Model(
                        profile.scrape_profile(model_id, refresh=False)
                    )
                }
            )
            out.append(await download.download_process(username, model_id, medias, posts=posts))
            progress_utils.increment_activity_count(total=length)
    if len(out)>1:
        return out
    else:
        return []
    