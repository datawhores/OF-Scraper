from contextlib import contextmanager
from pathlib import Path
import pathlib
import os
import sys
import re
from rich.console import Console
console=Console()
import arrow

from ..constants import configPath,DIR_FORMAT_DEFAULT,DATE_DEFAULT,SAVE_LOCATION_DEFAULT
from ..utils import profiles
import src.utils.config as config_


homeDir=pathlib.Path.home()
config = config_.read_config()['config']
@contextmanager
def set_directory(path: Path):
    """Sets the cwd within the context

        Args:``
            path (``Path): The path to the cwd

    Yields:
        None
    """


    origin = Path().absolute()
    createDir(Path(str(path)))
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(origin)
def createDir(path):
    try:
        path.mkdir(exist_ok=True,parents=True)
    except:
        console.print("Error creating directory, check the directory and make sure correct permissions have been issued.")
        sys.exit()
def databasePathHelper(model_id,username):
    return pathlib.Path(config.get("metadata").format(configpath=homeDir / configPath,profile=profiles.get_current_profile(),model_username=username,username=username,model_id=model_id,sitename="Onlyfans",site_name="Onlyfans",first_letter=username[0]),"user_data.db")

def getmediadir(ele,username,model_id):
    root= pathlib.Path((config.get('save_location') or SAVE_LOCATION_DEFAULT))
    downloadDir=(config.get('dir_format') or DIR_FORMAT_DEFAULT ).format(sitename="onlyfans",first_letter=username[0].capitalize(),model_id=model_id,model_username=username,responsetype=ele.responsetype.capitalize(),mediatype=ele.mediatype.capitalize(),value=ele.value.capitalize(),date=arrow.get(ele.postdate).format(config.get('date') or DATE_DEFAULT))
    return root /downloadDir   


def messageResponsePathHelper(model_id,username):
    profile = profiles.get_current_profile()
    return homeDir / configPath / profile / ".data"/f"{username}_{model_id}"/"messages.json"


def timelineResponsePathHelper(model_id,username):
    profile = profiles.get_current_profile()
    return homeDir / configPath / profile / ".data"/f"{username}_{model_id}"/"timeline.json"


def archiveResponsePathHelper(model_id,username):
    profile = profiles.get_current_profile()
    return homeDir / configPath / profile / ".data"/f"{username}_{model_id}"/"archive.json"
def pinnedResponsePathHelper(model_id,username):
    profile = profiles.get_current_profile()
    return homeDir / configPath / profile / ".data"/f"{username}_{model_id}"/"pinned.json"

def cleanup():
    console.print("Cleaning up .part files\n\n")
    root= pathlib.Path((config.get('save_location') or SAVE_LOCATION_DEFAULT))
    for file in list(filter(lambda x:re.search("\.part$",str(x))!=None,root.glob("**/*"))):
        file.unlink(missing_ok=True)


def getlogpath():
    path=pathlib.Path.home() / configPath / "logging"/f'ofscraper_{config_.get_main_profile()}_{arrow.get().format("YYYY-MM-DD")}.log'
    createDir(path.parent)
    return path