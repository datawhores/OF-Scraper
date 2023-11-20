r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
from functools import partial
from concurrent.futures import ThreadPoolExecutor
import pathlib
import traceback

from tenacity import stop_after_attempt,wait_random,AsyncRetrying
import arrow
import aiofiles
import psutil
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
import ofscraper.utils.config as config_
import ofscraper.utils.paths as paths
import ofscraper.constants as constants
import ofscraper.utils.config as config_
import ofscraper.utils.args as args_
import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.dates as dates
import ofscraper.db.operations as operations
from ofscraper.download.utils import cache,cache_thread,log,metadata,check_forced_skip,size_checker,\
addGlobalDir,moveHelper,sem_wrapper,set_time,get_medialog,update_total,attempt,set_cache_helper,path_to_file_helper



async def main_download(c,ele,path,username,model_id,progress):
    path_to_file=None
    log.debug(f"{get_medialog(ele)} Downloading with normal downloader")
    global thread
    thread=ThreadPoolExecutor(max_workers=config_.get_download_semaphores(config_.read_config())*2)

    #total may be none if no .part file
    if args_.getargs().metadata:
        return await metadata(c,ele,path,username,model_id)
    result=await main_download_downloader(c,ele,path,username,model_id,progress)

    if len(result)==2 and result[-1]==0:
        return result
    total ,temp,path_to_file=result

    check1=await size_checker(temp,ele,total) 
    check2=check_forced_skip(ele,total)
    if check1:
        return check1
    if check2:
        return check2
    
    log.debug(f"{get_medialog(ele)} {ele.filename_} size match target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}")   
    log.debug(f"{get_medialog(ele)} renaming {pathlib.Path(temp).absolute()} -> {path_to_file}")   
    moveHelper(temp,path_to_file,ele)
    addGlobalDir(path)
    if ele.postdate:
        newDate=dates.convert_local_time(ele.postdate)
        log.debug(f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
        set_time(path_to_file,newDate )
        log.debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  

    if ele.id:
        await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=True)
    await set_cache_helper(ele)
    return ele.mediatype,total








async def main_download_downloader(c,ele,path,username,model_id,progress): 
    try:
        async for _ in AsyncRetrying(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True):
            with _:
                    try:    
    
                        data=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,f"{ele.id}_headers"))
                        temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
                        
                        if data and data.get('content-length'):
                                content_type = data.get("content-type").split('/')[-1]
                                total=int(data.get('content-length'))
                                filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
                                path_to_file = paths.truncate(pathlib.Path(path,f"{filename}")) 
                                resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
                                check1=check_forced_skip(ele,total)
                                if check1:
                                    return 0 ,temp,path_to_file
                                elif total==resume_size:
                                    return total ,temp,path_to_file
                                elif total<resume_size:
                                   temp.unlink(missing_ok=True)
                        else:
                            paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part")).unlink(missing_ok=True)
                    except Exception as E: 
                        raise E    
    
    
    except Exception as E: 
                    raise E
    
    try:
        async for _ in AsyncRetrying(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True):
            with _:
                    try:
                        total=int(data.get("content-length")) if data else None
                        return await main_download_sendreq(c,ele,path,username,model_id,progress,total)
                    except Exception as E: 
                        raise E
    except Exception as E: 
                    raise E
    
@sem_wrapper
async def main_download_sendreq(c,ele,path,username,model_id,progress,total):
    attempt.set(attempt.get(0) + 1) 
    total=total if attempt.get()==1 else None
    try: 
        temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
        log.debug(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] download temp path {temp}")
        if not total:temp.unlink(missing_ok=True)
        resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
        if not total or total>resume_size:
            url=ele.url
            headers=None if not pathlib.Path(temp).exists() else {"Range":f"bytes={resume_size}-{total}"}               
            async with c.requests(url=url,headers=headers)()  as r:
                    if r.ok:
                        total=int(total or r.headers['content-length'])
                        if attempt.get()==1:await update_total(total)
                        content_type = r.headers.get("content-type").split('/')[-1]
                        if not content_type and ele.mediatype.lower()=="videos":content_type="mp4"
                        if not content_type and ele.mediatype.lower()=="images":content_type="jpg"
                        filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
                        path_to_file=path_to_file_helper(filename,ele,path,logout=True)
                        check=check_forced_skip(ele,total)
                        if check:
                            return 0 ,temp,path_to_file
                        elif total==resume_size:
                            return total ,temp,path_to_file
                        elif total<resume_size:
                            temp.unlink(missing_ok=True)
                        await main_download_datahandler(r,progress,ele,total,temp,path_to_file)                       
                    else:
                        log.debug(f"[bold] {get_medialog(ele)} main download response status code [/bold]: {r.status}")
                        log.debug(f"[bold] {get_medialog(ele)}  main download  response text [/bold]: {await r.text_()}")
                        log.debug(f"[bold] {get_medialog(ele)}  main download headers [/bold]: {r.headers}")
                        r.raise_for_status()  
                    await size_checker(temp,ele,total) 
        return total ,temp,path_to_file 
    except OSError as E:
        log.traceback(E)
        log.traceback(traceback.format_exc())
        log.debug(f"Number of Open Files -> { len(psutil.Process().open_files())}")      
        log.debug(f"Open Files -> {list(map(lambda x:(x.path,x.fd),psutil.Process().open_files()))}")                  
    except Exception as E:
        log.traceback(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] {traceback.format_exc()}")
        log.traceback(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] {E}")  
        raise E



async def main_download_datahandler(r,progress,ele,total,temp,path_to_file): 
    pathstr=str(path_to_file)
    log.debug(f"{get_medialog(ele)} passed size check with size {total}")    
    downloadprogress=config_.get_show_downloadprogress(config_.read_config()) or args_.getargs().downloadbars
    task1 = progress.add_task(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n", total=total,visible=True if downloadprogress else False)
    try:
        count=0
        loop=asyncio.get_event_loop()
        fileobject= await aiofiles.open(temp, 'ab').__aenter__()

        async for chunk in r.iter_chunked(constants.maxChunkSize):
            if downloadprogress:count=count+1
            await fileobject.write(chunk)
            if count==constants.CHUNK_ITER:\
            await loop.run_in_executor(thread,partial( progress.update,task1, completed=pathlib.Path(temp).absolute().stat().st_size)); \
            count=0
        await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.touch,f"{ele.filename}_headers",1))
    except Exception as E:
        raise E
    finally:
        #Close file if needed
        try:
            await fileobject.close()
        except Exception as E:
            None
        try:
             progress.remove_task(task1)
        except Exception as E:
            None