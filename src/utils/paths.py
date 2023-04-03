from contextlib import contextmanager
from pathlib import Path
import pathlib
import os
import sys
from rich.console import Console
console=Console()

from ..constants import configPath
from ..utils import profiles

homeDir=pathlib.Path.home()

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
    profile = profiles.get_current_profile()
    return homeDir / configPath / profile / ".data"/f"{username}_{model_id}"/"user_data.db"


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

