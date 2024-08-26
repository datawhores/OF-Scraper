import json
import re
import logging
import traceback
import tempfile


import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import run
import  ofscraper.runner.manager as manager



def post_user_script(username, media=None, posts=None):
    if not settings.get_post_download_script():
        return
    userdata=manager.Manager.model_manager.get_model(username)
    if not userdata:
        return
    try:
        username = userdata["username"] if isinstance(userdata, dict) else userdata.name
        model_id = userdata["id"] if isinstance(userdata, dict) else userdata.id
        userdict = userdata if isinstance(userdata, dict) else userdata.model

        log = logging.getLogger("shared")

        log.debug(f"Running post script for {username}")

        posts = list(map(lambda x: x.post, posts or []))
        media = list(map(lambda x: x.media, media or []))
        master_dump = json.dumps(
            {
                "username": username,
                "model_id": model_id,
                "media": media,
                "posts": posts,
                "userdata": userdict,
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            with open(f.name, "w") as g:
                g.write(master_dump)
            run([settings.get_post_download_script(), f.name])

    except Exception as e:
        log.traceback_(e)
        log.traceback_(traceback.format_exc())


def extract_command_and_args(text):
    """Extracts the command and arguments from a text string.

    Args:
      text: The input text string.

    Returns:
      A list containing the command and arguments.
    """

    match = re.match(r"([^\{\}]+)\s+(.*)$", text)
    if match:
        command, args = match.groups()
        args = re.findall(r"\{\w+\}", args)
        return [command], args
    else:
        return []
