from contextlib import contextmanager
from pathlib import Path
import traceback
import pathlib
import os
import sys
import re
import platform
import subprocess
import logging
import arrow
from InquirerPy.utils import patched_print
import ofscraper.constants as constants
import ofscraper.utils.profiles as profiles
import ofscraper.utils.config as config_
import ofscraper.utils.args as args_
import ofscraper.utils.console as console_
from .profiles import get_current_config_profile
import ofscraper.api.me as me



console=console_.shared_console
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
    configpath= get_config_home()
    profile=profiles.get_active_profile()
    model_username=username
    username=username
    modelusername=username
    model_id=model_id
    sitename="Onlyfans"
    site_name="Onlyfans"
    first_letter=username[0]

    save_location=config_.get_save_location(config_.read_config())
    my_profile = profiles.get_my_info()
    my_id, my_username =me.parse_user(my_profile)
    if config_.get_allow_code_execution(config_.read_config()):
        formatStr=eval("f'{}'".format(config_.get_metadata(config_.read_config())))
    else:
        formatStr=config_.get_metadata(config_.read_config()).format(
                         profile=profile,
                         model_username=username,
                         username=username,
                         model_id=model_id,
                         sitename=site_name,
                         site_name=site_name,
                         first_letter=first_letter,
                        save_location=save_location,
                                        my_id=my_id, 
                        my_username=my_username,
                         configpath=configpath)


    formatStr
    return pathlib.Path(formatStr,"user_data.db")

def getmediadir(ele,username,model_id):
    sitename="onlyfans"
    site_name="onlyfans"
    post_id=ele.postid
    media_id=ele.id
    first_letter=username[0].capitalize()
    mediatype=ele.mediatype.capitalize()
    value=ele.value.capitalize()
    date=arrow.get(ele.postdate).format(config_.get_date(config_.read_config()))
    model_username=username
    responsetype=ele.responsetype
    root= pathlib.Path((config_.get_save_location(config_.read_config())))
    profile=profiles.get_active_profile()
    my_profile = profiles.get_my_info()
    my_id, my_username =me.parse_user(my_profile)
    if config_.get_allow_code_execution(config_.read_config()):
        downloadDir=eval("f'{}'".format(config_.get_dirformat(config_.read_config())))
    else:
        downloadDir=config_.get_dirformat(config_.read_config())\
        .format(post_id=post_id,
                sitename=site_name,
                site_name=site_name,
                username=model_username,
                modeluesrname=model_username,
                first_letter=first_letter,
                model_id=model_id,
                model_username=username,
                responsetype=responsetype,
                mediatype=mediatype,
                date=date,
                      my_id=my_id, 
                        my_username=my_username,
                profile=profile,
                value=value)
        
    return root /downloadDir  



def createfilename(ele,username,model_id,ext):
    filename=ele.filename_
    sitename="Onlyfans"
    site_name="Onlyfans"
    user=me
    post_id=ele.postid_
    media_id=ele.id
    first_letter=username[0]
    mediatype=ele.mediatype
    value=ele.value
    text=ele.text_
    date=arrow.get(ele.postdate).format(config_.get_date(config_.read_config()))
    model_username=username
    responsetype=ele.responsetype
    profile=profiles.get_active_profile()
    my_profile = profiles.get_my_info()
    my_id, my_username =me.parse_user(my_profile)
   

    if ele.responsetype_ =="profile":
        return f"{filename}.{ext}"
    elif config_.get_allow_code_execution(config_.read_config()):
        return eval("f'{}'".format(config_.get_fileformat(config_.read_config())))
    else:
        return config_.get_fileformat(config_.read_config()).format(filename=filename,
                                                                    sitename=sitename,
                                                                    site_name=sitename,post_id=post_id,
                                                                    media_id=media_id,
                                                                    first_letter=first_letter,
                                                                    mediatype=mediatype,
                                                                    value=value,
                                                                    text=text,
                                                                    date=date,
                                                                    ext=ext,
                                                                    model_username=username,
                                                                    model_id=model_id,
                                                                    responsetype=responsetype,
                                                                          my_id=my_id, 
                                                                my_username=my_username,
                                                                    profile=profile) 






def cleanup():
    log.info("Cleaning up temp files\n\n")
    root= pathlib.Path((config_.get_save_location(config_.read_config())))
    for file in list(filter(lambda x:re.search("\.part$|^temp_",str(x))!=None,root.glob("**/*"))):
        file.unlink(missing_ok=True)


def getcachepath():
    profile = get_profile_path()
    path= profile/"cache"
    createDir(path.parent)
    return path
def truncate(path):
    if args_.getargs().original:
        return path
    if platform.system() == 'Windows':
        return _windows_truncateHelper(path)
    elif platform.system() == 'Linux':
        return _linux_truncateHelper(path)
    elif platform.system() == 'Darwin':
        return _mac_truncateHelper(path)
    else:
        return pathlib.Path(path)
def _windows_truncateHelper(path):
    if len(str(path))<=256:
        return path
    path=pathlib.Path(path)
    dir=path.parent
    file=path.name
    match=re.search("_[0-9]+\.[a-z]*$",path.name,re.IGNORECASE) or re.search("\.[a-z]*$",path.name,re.IGNORECASE)
    if match:
        ext=match.group(0)
    else:
        ext=""
    #-1 is for / between parentdirs and file
    fileLength=256-len(ext)-len(str(dir))-1
    newFile=f"{re.sub(ext,'',file)[fileLength]}{ext}"
    final=pathlib.Path(dir,newFile)
    log.debug(f"path: {final} path size: {len(str(final))}")
    return pathlib.Path(dir,newFile)

def _mac_truncateHelper(path):
    path=pathlib.Path(path)
    dir=path.parent
    match=re.search("_[0-9]+\.[a-z]*$",path.name,re.IGNORECASE) or re.search("\.[a-z]*$",path.name,re.IGNORECASE)
    ext= match.group(0) if match else ""
    file=re.sub(ext,"",path.name)
    maxlength=255-len(ext)
    newFile=f"{file[:maxlength]}{ext}"
    final=pathlib.Path(dir,newFile)
    log.debug(f"path: {final} path size: {len(str(final))}")
    log.debug(f"path: {final} filename size: {len(str(final.name))}")
    return pathlib.Path(dir,newFile)

def _linux_truncateHelper(path):
    path=pathlib.Path(path)
    dir=path.parent
    match=re.search("_[0-9]+\.[a-z]*$",path.name,re.IGNORECASE) or re.search("\.[a-z]*$",path.name,re.IGNORECASE)
    ext= match.group(0) if match else ""
    file=re.sub(ext,"",path.name)
    maxbytes=254-len(ext.encode('utf8'))
    small=0
    large=len(file)
    target=None
    maxLength=254-len(ext)
    if len(path.name.encode('utf8'))<=maxbytes:
        target=large
    while True and not target:
        if len(file[:large].encode('utf8'))==maxbytes:
            target=large
        elif len(file[:small].encode('utf8'))==maxbytes:
            target=small
        elif large==small:
            target=large
        elif large==small+1:
            target=small
        elif len(file[:large].encode('utf8'))>maxbytes:
            large=int((small+large)/2)
        elif len(file[:large].encode('utf8'))<maxbytes:
             small=large
             large=int((large+maxLength)/2)        
    newFile=f"{file[:target]}{ext}"
    log.debug(f"path: {path} filename bytesize: {len(newFile.encode('utf8'))}")
    return pathlib.Path(dir,newFile)



def mp4decryptchecker(x):
   return mp4decryptpathcheck(x) and mp4decryptexecutecheck(x)

def mp4decryptpathcheck(x):
    if not pathlib.Path(x).is_file():
        patched_print("path to mp4decrypt is not valid")
        return False
    return True
def mp4decryptexecutecheck(x):
    try:
        t=subprocess.run([x],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if re.search("mp4decrypt",t.stdout.decode())!=None or  re.search("mp4decrypt",t.stderr.decode())!=None:
            return True
        patched_print("issue executing path as mp4decrypt")
    except Exception as E:
        patched_print(E)
        patched_print(traceback.format_exc())
        return False


def ffmpegchecker(x):
    return ffmpegexecutecheck(x) and ffmpegpathcheck(x)

def ffmpegpathcheck(x):
    if not pathlib.Path(x).is_file():
        patched_print("path to ffmpeg is not valid")
        return False
    return True 

def ffmpegexecutecheck(x):
    try:
        t=subprocess.run([x],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if re.search("ffmpeg",t.stdout.decode())!=None or  re.search("ffmpeg",t.stderr.decode())!=None:
            return True
        patched_print("issue executing path as ffmpeg")
    except Exception as E:
        patched_print(E)
        patched_print(traceback.format_exc())
        return False  
   
def getlogpath():
    path= get_config_home() / "logging"/f'ofscraper_{config_.get_main_profile()}_{arrow.now().format("YYYY-MM-DD")}.log'
    createDir(path.parent)
    return path

def get_config_path():
    configPath=args_.getargs().config
    defaultPath=pathlib.Path.home() / constants.configPath/constants.configFile
    ofscraperHome=pathlib.Path.home() / constants.configPath

    if configPath==None or configPath=="":
        return defaultPath
    configPath=pathlib.Path(configPath)
    # check if path exists
    if  configPath.is_file():
         return configPath
    elif configPath.is_dir():
        return configPath/constants.configFile
    #enforce that configpath needs some extension
    elif configPath.suffix=="":
        return configPath/constants.configFile
    
    elif str(configPath.parent)==".":
        return ofscraperHome/configPath
    return configPath

def get_profile_path(name=None):
    if name:
        return get_config_home()/name
    elif not args_.getargs().profile:
        return get_config_home()/get_current_config_profile()
    return get_config_home()/args_.getargs().profile

def get_config_home():
    return get_config_path().parent


def get_auth_file():
    return get_profile_path() /constants.authFile

    
   
