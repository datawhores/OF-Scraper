import json
import logging
import traceback


import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess  import run
def post_user_process(username, model_id, medialist, postlist):
    log = logging.getLogger("shared")
    if not settings.get_post_download_script():
        return
    try:
        mediadump = json.dumps(list(map(lambda x: x.media, medialist)))
        postdump = json.dumps(list(map(lambda x: x.post, postlist)))
        model_id = str(model_id)
        run(
            [
                settings.get_post_download_script(),
                username,
                model_id,
                mediadump,
                postdump,
            ]
        )
    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())
