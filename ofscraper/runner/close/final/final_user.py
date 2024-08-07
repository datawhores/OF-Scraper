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
        post_dump=list(map(lambda x: x.post, postlist or []))
        media_dump=list(map(lambda x: x.media, medialist or []))

        master_dump={"username":username,"model_id":model_id,"media":media_dump,"posts":post_dump}
        run(
            [
                settings.get_post_download_script(),
                username,
                model_id,
                json.dumps(media_dump),
                json.dumps(post_dump),
                json.dumps(master_dump),
            ]
        )
    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
