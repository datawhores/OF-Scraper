import time
from contextlib import asynccontextmanager
import logging
import httpx
import ofscraper.utils.separate as seperate
import ofscraper.db.operations as operations
import ofscraper.utils.args as args_
import ofscraper.download.downloadbatch as batchdownloader
import ofscraper.download.download as download
import ofscraper.utils.config as config_
import ofscraper.utils.system as system
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.constants as constants
import ofscraper.utils.console as console_
import ofscraper.utils.stdout as stdout



def medialist_filter(medialist,model_id,username):
    log=logging.getLogger("shared")
    if not args_.getargs().dupe:
        media_ids = set(operations.get_media_ids_downloaded(model_id=model_id,username=username))
        log.debug(f"Number of unique media ids in database for {username}: {len(media_ids)}")
        medialist = seperate.separate_by_id(medialist, media_ids)
        log.debug(f"Number of new mediaids with dupe ids removed: {len(medialist)}")  
        medialist=seperate.seperate_avatars(medialist)
        log.debug(f"Removed previously downloaded avatars/headers")
        log.debug(f"Final Number of media to download {len(medialist)}")

    else:
        log.info(f"forcing all downloads media count {len(medialist)}")
    return medialist


def download_picker(username, model_id, medialist):
    medialist=medialist_filter(medialist,model_id,username)

    if len(medialist)==0:
        logging.getLogger("shared").error(f'[bold]{username}[/bold] ({0} photos, {0} videos, {0} audios,  {0} skipped, {0} failed)' )
        return  0,0,0,0,0
    elif system.getcpu_count()>1 and (len(medialist)>=config_.get_download_semaphores(config_.read_config())*5) and (args_.getargs().downloadthreads or config_.get_threads(config_.read_config()))>0:
        return batchdownloader.process_dicts(username, model_id, medialist)
    else:
        
        return download.process_dicts(
                    username,
                    model_id,
                    medialist
                    )
    
def check_cdm():
    with stdout.lowstdout():
        console=console_.get_shared_console()
        log=logging.getLogger("shared")

        keymode=(args_.getargs().key_mode or config_.get_key_mode(config_.read_config()) or "cdrm")
        console.print(f"[yellow]Key Mode: {keymode}\n\n[/yellow]")
        if  keymode== "manual":\
        console.print("[yellow]WARNING:Make sure you have all the correct settings for choosen cdm\nhttps://of-scraper.gitbook.io/of-scraper/cdm-options\n\n[/yellow]");return True
        elif keymode=="keydb":url=constants.KEYDB
        elif keymode=="cdrm": url=constants.CDRM
        elif keymode=="cdrm2": url=constants.CDRM2
        try:
            with sessionbuilder.sessionBuilder(backend="httpx",total_timeout=30) as c:
                with c.requests(url=url)() as r:
                    if r.ok:
                        console.print("[green] CDM service seems to be working\n[/green]")
                        console.print("[yellow]WARNING:Make sure you have all the correct settings for choosen cdm\nhttps://of-scraper.gitbook.io/of-scraper/cdm-options\n\n[/yellow]")
                        return True
                    else:
                        console.print("[red]CDM return an error\nThis may cause a lot of failed downloads\n consider switching\nhttps://of-scraper.gitbook.io/of-scraper/cdm-options\n\n[/red]")
                        log.debug(f"[bold] cdm status[/bold]: {r.status}[/bold]")
                        log.debug(f"[bold]  cdm text [/bold]: {r.text_()}[/bold]")
                        log.debug(f"[bold]  cdm headers [/bold]: {r.headers}[/bold]") 
                        time.sleep(3.5)
                        return False
        except httpx.TimeoutException as E:
                console.print(f"[red]CDM service {keymode} timed out and seems to be down\nThis may cause a lot of failed downloads\nPlease confirm by checking the url:{url}\n Consider switching\nhttps://of-scraper.gitbook.io/of-scraper/cdm-options\n\n[/red]")
                time.sleep(3.5)
       
        except Exception as E:
                console.print(f"[red]CDM service {keymode} has an issue {E}\nThis may cause a lot of failed downloads\nPlease confirm by checking the url:{url}\n Consider switching\nhttps://of-scraper.gitbook.io/of-scraper/cdm-options\n\n[/red]")
                time.sleep(3.5)
        return False

