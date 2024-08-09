import json
import re
import logging
import traceback
import tempfile


import ofscraper.utils.settings as settings
from ofscraper.utils.system.subprocess import run
def post_user_process(username, model_id, medialist, postlist):
    log = logging.getLogger("shared")
    if not settings.get_post_download_script():
        return
    log.debug(f"Running post script for {username}")
    try:
        posts=list(map(lambda x: x.post, postlist or []))
        media=list(map(lambda x: x.media, medialist or []))
        master_dump=json.dumps({"username":username,"model_id":model_id,"media":media,"posts":posts})

        with tempfile.NamedTemporaryFile() as f:
          with open(f.name, "w") as g:
              g.write(master_dump)
          run([settings.get_post_download_script(),f.name])




       
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

  match = re.match(r'([^\{\}]+)\s+(.*)$', text)
  if match:
    command, args = match.groups()
    args = re.findall(r'\{\w+\}' ,args)
    return [command] , args
  else:
    return []
