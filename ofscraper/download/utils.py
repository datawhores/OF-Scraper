r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
from concurrent.futures import ThreadPoolExecutor
from collections import abc
import asyncio
import math
import pathlib
import platform
import shutil
import logging
import contextvars

from functools import singledispatch,partial
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
from tenacity import retry,stop_after_attempt,wait_random,AsyncRetrying
import ofscraper.utils.config as config_
import ofscraper.utils.paths as paths
import ofscraper.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.config as config_
import ofscraper.utils.args as args_
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
from ofscraper.utils.run_async import run


from diskcache import Cache
attempt = contextvars.ContextVar("attempt")
attempt2 = contextvars.ContextVar("attempt")
total_count = contextvars.ContextVar("total")
total_count2 = contextvars.ContextVar("total")

cache=None
cache_thread=None
log=None
sem=None
mpd_sem=None
dirSet=None
lock=None
total_data=None


def get_sem():
    global sem
    if not sem:
        sem=semaphoreDelayed(config_.get_download_semaphores(config_.read_config()))
    return sem


def get_cache_thread():
    global cache_thread
    if not cache_thread:
        cache_thread=ThreadPoolExecutor(max_workers=1)
    return cache_thread


def get_cache():
    global cache
    if not cache:
        cache= Cache(paths.getcachepath(),disk=config_.get_cache_mode(config_.read_config()))

    return cache

def get_log():
    global log
    if not log:
        log=logging.getLogger("ofscraper-download")
    return log

def get_dirSet():
    global dirSet
    if not dirSet:
        dirSet=set()
    return dirSet  

def get_sem():
    global mpd_sem
    if not mpd_sem:
        mpd_sem=semaphoreDelayed(config_.get_download_semaphores(config_.read_config()))
    return mpd_sem

def get_lock():
    global lock
    
    if not lock:
        lock=asyncio.Lock()
    return lock

def get_total_data():
    global total_data
    if not total_data:
        total_data=0
get_log()
get_sem()
get_cache_thread()
get_cache()
get_dirSet()
get_lock()
get_total_data()
def get_medialog(ele):
    return f"Media:{ele.id} Post:{ele.postid}"



@singledispatch
def sem_wrapper(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
         return sem_wrapper(args[0])
    return sem_wrapper(**kwargs)

@sem_wrapper.register
def _(input_sem: semaphoreDelayed):
    return partial(sem_wrapper,input_sem=input_sem)


@sem_wrapper.register
def _(func:abc.Callable,input_sem:None|semaphoreDelayed=None):
    async def inner(*args,input_sem=input_sem,**kwargs):
        if input_sem==None:input_sem=get_sem()
        await input_sem.acquire()
        try:  
            return await func(*args,**kwargs) 
        except Exception as E:
            raise E  
        finally:
            input_sem.release()  
    return inner




async def update_total(update):
    global total_data
    global lock
    async with lock:
        total_data+=update


async def size_checker(path,ele,total,name=None):
    name=name or ele.filename
    if not pathlib.Path(path).exists():
        s=f"{get_medialog(ele)} {path} was not created"
        raise Exception(s)
    elif total-pathlib.Path(path).absolute().stat().st_size>500:
        s=f"{get_medialog(ele)} {name} size mixmatch target: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
        pathlib.Path(path).unlink(missing_ok=True)
        await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,f"{ele.id}_headers",None))       
        raise Exception(s)    
    elif (total-pathlib.Path(path).absolute().stat().st_size)<0:
        s=f"{get_medialog(ele)} {path} size mixmatch target item too large: {total} vs current file: {pathlib.Path(path).absolute().stat().st_size}"
        pathlib.Path(path).unlink(missing_ok=True)
        await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,f"{ele.id}_headers",None))        
        raise Exception(s)

    
    
def path_to_file_helper(filename,ele,path,logout=False):
    if logout:log.debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] filename from config {filename}")
    if logout:log.debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] full path from config {pathlib.Path(path,f'{filename}')}")
    path_to_file = paths.truncate(pathlib.Path(path,f"{filename}")) 
    if logout:log.debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] full path trunicated from config {path_to_file}")
    return path_to_file


def check_forced_skip(ele,*args): 
    total=sum(map(lambda x:int(x),args))  

    file_size_limit = args_.getargs().size_max or config_.get_filesize_limit(config_.read_config()) 
    file_size_min=args_.getargs().size_min or config_.get_filesize_limit(config_.read_config()) 
      
    if total==0:
        return ele.mediatype,0
    if int(file_size_limit)>0 and int(total) > int(file_size_limit): 
        log.debug(f"{get_medialog(ele)} over size limit") 
        return 'forced_skipped', 1 
    elif int(file_size_min)>0 and int(total) < int(file_size_min): 
        log.debug(f"{get_medialog(ele)} under size min") 
        return 'forced_skipped', 1 


async def metadata(c,ele,path,username,model_id,filename=None,path_to_file=None):
    log.info(f"{get_medialog(ele)} skipping adding download to disk because metadata is on")
    data=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,f"{ele.id}_headers"))
    if filename and path_to_file:
        if ele.id:await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=pathlib.Path(path_to_file).exists())
        return ele.mediatype if pathlib.Path(path_to_file).exists() else "forced_skipped",0
    if data and data.get('content-length'):
            content_type = data.get("content-type").split('/')[-1]
            filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
            path_to_file = paths.truncate(pathlib.Path(path,f"{filename}")) 
            if ele.id:await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=pathlib.Path(path_to_file).exists())
            return ele.mediatype if pathlib.Path(path_to_file).exists() else "forced_skipped",0
    else:
        try:
            async for _ in AsyncRetrying(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True):
                with _:
                    return await metadata_helper(c,ele,path,username,model_id)
        except Exception as E: 
            raise E
@sem_wrapper
async def metadata_helper(c,ele,path,username,model_id):
        url=ele.url
        path_to_file=None
        filename=None
        attempt.set(attempt.get(0) + 1) 
        async with c.requests(url=url,headers=None)() as r:
                if r.ok:
                    data=r.headers
                    await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,f"{ele.id}_headers",{"content-length":data.get("content-length"),"content-type":data.get("content-type")}))
                    content_type = data.get("content-type").split('/')[-1]
                    if not content_type and ele.mediatype.lower()=="videos":content_type="mp4"
                    if not content_type and ele.mediatype.lower()=="images":content_type="jpg"
                    filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
                    path_to_file=path_to_file_helper(filename,ele,path,logout=True)


                else:
                    r.raise_for_status()
        if ele.id:await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=pathlib.Path(path_to_file).exists())
        return ele.mediatype if pathlib.Path(path_to_file).exists() else "forced_skipped",0 



def convert_num_bytes(num_bytes: int) -> str:
    if num_bytes == 0:
      return '0 B'
    num_digits = int(math.log10(num_bytes)) + 1

    if num_digits >= 10:
        return f'{round(num_bytes / 10**9, 2)} GB'
    return f'{round(num_bytes / 10 ** 6, 2)} MB'

               
def set_time(path, timestamp):
    if platform.system() == 'Windows':
        setctime(path, timestamp)
    pathlib.os.utime(path, (timestamp, timestamp))


def get_error_message(content):
    error_content = content.get('error', 'No error message available')
    try:
        return error_content.get('message', 'No error message available')
    except AttributeError:
        return error_content


async def set_cache_helper(ele):
    if  ele.postid and ele.responsetype_=="profile":
        await asyncio.get_event_loop().run_in_executor(cache_thread,partial(  cache.set,ele.postid ,True))

def moveHelper(temp,path_to_file,ele):
    if not path_to_file.exists():
        shutil.move(temp,path_to_file)
    elif pathlib.Path(temp).absolute().stat().st_size>=pathlib.Path(path_to_file).absolute().stat().st_size: 
        shutil.move(temp,path_to_file)
    else:
        pathlib.Path(temp).unlink(missing_ok=True)
        log.debug(f"{get_medialog(ele)} smaller then previous file")

def addGlobalDir(path):
    dirSet.add(path.parent)


def setDirectoriesDate():
    log.info("Setting Date for modified directories")
    output=set()
    rootDir=pathlib.Path(config_.get_save_location(config_.read_config()))
    log.debug(f"Original DirSet {list(dirSet)}")
    log.debug(f"rooDir {rootDir}")

    for ele in dirSet:
        output.add(ele)
        while ele!=rootDir and ele.parent!=rootDir:
            log.debug(f"Setting Dates ele:{ele} rootDir:{rootDir}")
            output.add(ele.parent)
            ele=ele.parent
    log.debug(f"Directories list {output}")
    for ele in output:
        set_time(ele,dates.get_current_time())