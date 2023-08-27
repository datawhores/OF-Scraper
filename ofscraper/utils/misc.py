from contextlib import asynccontextmanager
import asyncio
import logging
import ofscraper.utils.separate as seperate
import ofscraper.db.operations as operations
import ofscraper.utils.args as args_
import ofscraper.utils.downloadbatch as batchdownloader
import ofscraper.utils.download as download
import ofscraper.utils.config as config_
import ofscraper.utils.system as system




def medialist_filter(medialist,model_id,username):
    log=logging.getLogger("shared")
    if not args_.getargs().dupe:
        media_ids = set(operations.get_media_ids(model_id=model_id,username=username))
        log.debug(f"Number of unique media ids in database for {username}: {len(media_ids)}")
        medialist = seperate.separate_by_id(medialist, media_ids)
        log.debug(f"Number of new mediaids with dupe ids removed: {len(medialist)}")  
        medialist=seperate.seperate_avatars(medialist)
        log.debug(f"Removed previously downloaded avatar/headers")
        log.debug(f"Final Number of media to download {len(medialist)}")

    else:
        log.info(f"forcing all downloads media count {len(medialist)}")
    return medialist


def download_picker(username, model_id, medialist):
    medialist=medialist_filter(medialist,model_id,username)
    if len(medialist)==0:
        logging.getLogger("shared").error(f'[bold]{username}[/bold] ({0} photos, {0} videos, {0} audios,  {0} skipped, {0} failed)' )
        return  0,0,0,0,0
    elif (len(medialist)>=config_.get_download_semaphores(config_.read_config())) and system.getcpu_count()>1 and (args_.getargs().downloadthreads or config_.get_threads(config_.read_config()))>0:
        return batchdownloader.process_dicts(username, model_id, medialist)
    else:
        
        return asyncio.run(download.process_dicts(
                    username,
                    model_id,
                    medialist
                    ))
    


