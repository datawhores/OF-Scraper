from contextlib import contextmanager
from pathlib import Path
import pathlib
import os
import sys
import re
import platform
import subprocess
import logging
from rich.console import Console
import arrow
import ofscraper.constants as constants
import ofscraper.utils.profiles as profiles
import ofscraper.utils.config as config_

console=Console()
homeDir=pathlib.Path.home()
log=logging.getLogger(__package__)


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
        log.info("Error creating directory, check the directory and make sure correct permissions have been issued.")
        sys.exit()
def databasePathHelper(model_id,username):
    formatStr=config_.get_metadata(config_.read_config())
    return pathlib.Path(formatStr.format(configpath=homeDir / constants.configPath,profile=profiles.get_current_profile(),model_username=username,username=username,model_id=model_id,sitename="Onlyfans",site_name="Onlyfans",first_letter=username[0],save_location=config_.get_save_location(config_.read_config())),"user_data.db")

def getmediadir(ele,username,model_id):
    root= pathlib.Path((config_.get_save_location(config_.read_config())))
    downloadDir=config_.get_dirformat(config_.read_config())\
    .format(sitename="onlyfans",first_letter=username[0].capitalize(),model_id=model_id,model_username=username,responsetype=ele.responsetype.capitalize(),mediatype=ele.mediatype.capitalize(),value=ele.value.capitalize(),date=arrow.get(ele.postdate).format(config_.get_date(config_.read_config())))
    return root /downloadDir   


def messageResponsePathHelper(model_id,username):
    profile = profiles.get_current_profile()
    return homeDir / constants.configPath / profile / ".data"/f"{username}_{model_id}"/"messages.json"


def timelineResponsePathHelper(model_id,username):
    profile = profiles.get_current_profile()
    return homeDir / constants.configPath / profile / ".data"/f"{username}_{model_id}"/"timeline.json"


def archiveResponsePathHelper(model_id,username):
    profile = profiles.get_current_profile()
    return homeDir / constants.configPath / profile / ".data"/f"{username}_{model_id}"/"archive.json"
def pinnedResponsePathHelper(model_id,username):
    profile = profiles.get_current_profile()
    return homeDir / constants.configPath / profile / ".data"/f"{username}_{model_id}"/"pinned.json"

def cleanup():
    log.info("Cleaning up .part files\n\n")
    root= pathlib.Path((config_.get_save_location(config_.read_config())))
    for file in list(filter(lambda x:re.search("\.part$",str(x))!=None,root.glob("**/*"))):
        file.unlink(missing_ok=True)


def getcachepath():
    profile = profiles.get_current_profile()
    path=pathlib.Path.home() / constants.configPath / profile/"cache"
    createDir(path.parent)
    return path
def trunicate(path):
    if platform.system() == 'Windows' and len(str(path))>256:
        return _windows_trunicateHelper(path)
    elif platform.system() == 'Linux':
        return _linux_trunicateHelper(path)
    else:
        return pathlib.Path(path)
def _windows_trunicateHelper(path):
    path=pathlib.Path(path)
    if re.search("\.[a-z]*$",path.name,re.IGNORECASE):
        ext=re.search("\.[a-z]*$",path.name,re.IGNORECASE).group(0)
    else:
        ext=""
    filebase=str(path.with_suffix("").name)
    dir=path.parent
    #-1 for path split /
    maxLength=256-len(ext)-len(str(dir))-1
    outString=""
    for ele in list(filebase):
        temp=outString+ele
        if len(temp)>maxLength:
            break
        outString=temp
    return pathlib.Path(f"{pathlib.Path(dir,outString)}{ext}")

def _linux_trunicateHelper(path):
    path=pathlib.Path(path)
    if re.search("\.[a-z]*$",path.name,re.IGNORECASE):
        ext=re.search("\.[a-z]*$",path.name,re.IGNORECASE).group(0)
    else:
        ext=""
    filebase=str(re.sub(ext,"",path.name))
    dir=path.parent
    maxLength=255-len(ext.encode('utf8'))
    outString=""
    for ele in list(filebase):
        temp=outString+ele
        if len(temp.encode("utf8"))>maxLength:
            break
        outString=temp
    return pathlib.Path(f"{pathlib.Path(dir,outString)}{ext}")

def mp4decryptchecker(x):
    if not pathlib.Path(x).is_file():
        return False
    try:
        t=subprocess.run([x],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if re.search("mp4decrypt",t.stdout.decode())!=None or  re.search("mp4decrypt",t.stderr.decode())!=None:
            return True
    except:
        return False
def ffmpegchecker(x):
    if not pathlib.Path(x).is_file():
        return False
    try:
        t=subprocess.run([x],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if re.search("ffmpeg",t.stdout.decode())!=None or  re.search("ffmpeg",t.stderr.decode())!=None:
            return True
    except:
        return False   
def getlogpath():
    path=pathlib.Path.home() / constants.configPath / "logging"/f'ofscraper_{config_.get_main_profile()}_{arrow.get().format("YYYY-MM-DD")}.log'
    createDir(path.parent)
    return path
