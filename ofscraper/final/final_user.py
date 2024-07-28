import json
import logging
import traceback


import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess  import run
def post_user_process(username, model_id, medialist, postlist):
    log = logging.getLogger("shared")
    if not settings.get_post_download_script():
        return
    log.debug(f"Running post script for {username}")
    try:
        master_dump={"username":username,"model_id":model_id,"media":list(map(lambda x: x.media, medialist)),"posts":list(map(lambda x: x.post, postlist))}
        run(
            [
                settings.get_post_download_script(),
                json.dumps(master_dump),
            ]
        )
    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
