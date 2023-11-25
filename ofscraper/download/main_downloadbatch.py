
r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import pathlib
import traceback
from functools import singledispatch,partial
from tenacity import retry,stop_after_attempt,wait_random,AsyncRetrying
import aiofiles
import arrow
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
import ofscraper.utils.dates as dates
import ofscraper.db.operations as operations
import ofscraper.utils.config as config_
import ofscraper.utils.paths as paths
import ofscraper.constants as constants
import ofscraper.utils.config as config_
import ofscraper.utils.args as args_
import ofscraper.classes.placeholder as placeholder
from ofscraper.utils.run_async import run
import ofscraper.utils.system as system
from ofscraper.download.common import get_medialog,check_forced_skip,sem_wrapper,get_medialog \
,size_checker,moveHelper,addLocalDir,set_time,set_cache_helper,path_to_file_helper
import ofscraper.download.common as common


async def main_download(c,ele,path,username,model_id): 
    path_to_file=None
    common.innerlog.get().debug(f"{get_medialog(ele)} Downloading with normal downloader")
    result=list(await main_download_downloader(c,ele,path,username,model_id))
    if len(result)==2 and result[-1]==0:
        return result
    total ,temp_path,path_to_file=result
    
    check1=await size_checker(temp_path,ele,total,path_to_file)
    check2=await check_forced_skip(ele,path_to_file,total)
    if check1:
        return check1
    if check2:
        return check2
    
    
  
    common.innerlog.get().debug(f"{get_medialog(ele)} {ele.filename_} size match target: {total} vs actual: {pathlib.Path(temp_path).absolute().stat().st_size}")   
    common.innerlog.get().debug(f"{get_medialog(ele)} renaming {pathlib.Path(temp_path).absolute()} -> {path_to_file}")   
    moveHelper(temp_path,path_to_file,ele,common.innerlog.get())
    addLocalDir(path)

    if ele.postdate:
        newDate=dates.convert_local_time(ele.postdate)
        common.innerlog.get().debug(f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
        set_time(path_to_file,newDate )
        common.innerlog.get().debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  
    if ele.id:
        await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=True)
    await set_cache_helper(ele)
    return ele.mediatype,total




async def main_download_downloader(c,ele,path,username,model_id):
    
    
    try:
        async for _ in AsyncRetrying(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True):
            with _:
                    try:
                        data=await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.get,f"{ele.id}_headers"))
                        temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
                        if data and data.get('content-length'):
                                content_type = data.get("content-type").split('/')[-1]
                                total=int(data.get('content-length'))
                                filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
                                path_to_file = paths.truncate(pathlib.Path(path,f"{filename}")) 
                                resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
                                check1=await check_forced_skip(ele,path_to_file,total)
                                if check1:
                                    if ele.id:await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=path_to_file.exists())
                                    return check1
                                elif total==resume_size:
                                    return total ,temp,path_to_file
                                elif total<resume_size:
                                    pathlib.Path(temp).unlink(missing_ok=True)
                        else:
                            paths.truncate(pathlib.Path(temp)).unlink(missing_ok=True)
                    except Exception as E: 
                        raise E
    except Exception as E: 
                    raise E

      
    try:
        async for _ in AsyncRetrying(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True):
            with _:
                    try:
                        total=int(data.get("content-length")) if data else None
                        return await main_download_sendreq(c,ele,path,username,model_id,total)
                    except Exception as E: 
                        raise E
    except Exception as E: 
                    raise E

@sem_wrapper
async def main_download_sendreq(c,ele,path,username,model_id,total):
    common.attempt.set(common.attempt.get(0) + 1) 
    total=total if common.attempt.get()==1 else None
    try:
        temp=paths.truncate(pathlib.Path(path,f"{ele.filename}_{ele.id}.part"))
        common.innerlog.get().debug(f"{get_medialog(ele)} [attempt {common.attempt.get()}/{constants.NUM_TRIES}] download temp path {temp}")
        if not total:temp.unlink(missing_ok=True)
        resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
        if not total or total>resume_size:
            url=ele.url
            headers=None if not pathlib.Path(temp).exists() else {"Range":f"bytes={resume_size}-{total}"}
            async with c.requests(url=url,headers=headers)() as r:
                    if r.ok:
                        total=int(total or (r.headers['content-length']))
                        await common.pipe.coro_send(  (None, 0,total))
                        content_type = r.headers.get("content-type").split('/')[-1]
                        if not content_type and ele.mediatype.lower()=="videos":content_type="mp4"
                        if not content_type and ele.mediatype.lower()=="images":content_type="jpg"
                        filename=placeholder.Placeholders().createfilename(ele,username,model_id,content_type)
                        path_to_file=path_to_file_helper(filename,ele,path,common.innerlog.get())
                        check=await check_forced_skip(ele,path_to_file,total)
                        if check:
                            return 0 ,temp,path_to_file
                        elif total==resume_size:
                            return total ,temp,path_to_file
                        elif total<resume_size:
                            temp.unlink(missing_ok=True)
                        await main_download_datahandler(r,ele,total,temp,path_to_file)                       

                    else:
                        common.innerlog.get().debug(f"[bold] {get_medialog(ele)} main download response status code [/bold]: {r.status}")
                        common.innerlog.get().debug(f"[bold] {get_medialog(ele)} main download  response text [/bold]: {await r.text_()}")
                        common.innerlog.get().debug(f"[bold] {get_medialog(ele)}main download headers [/bold]: {r.headers}")
                        r.raise_for_status()  
                    await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.touch,f"{ele.filename}_headers",1))
                    await size_checker(temp,ele,total)
        return total,temp,path_to_file
    except OSError as E:
        common.log.traceback(E)
        common.log.traceback(traceback.format_exc())
        common.log.debug(f" Number of open Files across all processes-> {len(system.getOpenFiles(unique=False))}")   
        common.log.debug(f" Number of unique open files across all processes-> {len(system.getOpenFiles())}")   
        common.log.debug(f"Unique files data across all process -> {list(map(lambda x:(x.path,x.fd),(system.getOpenFiles())))}" )
    except Exception as E:
        common.innerlog.get().traceback(f"{get_medialog(ele)} [attempt {common.attempt.get()}/{constants.NUM_TRIES}] {traceback.format_exc()}")
        common.innerlog.get().traceback(f"{get_medialog(ele)} [attempt {common.attempt.get()}/{constants.NUM_TRIES}] {E}")
        raise E
async def main_download_datahandler(r,ele,total,temp,path_to_file): 
        pathstr=str(path_to_file)
        downloadprogress=config_.get_show_downloadprogress(config_.read_config()) or args_.getargs().downloadbars           
        try:
            count=0
            await common.pipe.coro_send({"type":"add_task","args":(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n",ele.id),
                        "total":total,"visible":False})
            
            fileobject= await aiofiles.open(temp, 'ab').__aenter__()
            await  common.pipe.coro_send({"type":"update","args":(ele.id,),"visible":True})
            async for chunk in r.iter_chunked(constants.maxChunkSizeB):
                count=count+1
                if downloadprogress:count=count+1
                common.innerlog.get().trace(f"{get_medialog(ele)} Download:{(pathlib.Path(temp).absolute().stat().st_size)}/{total}")
                await fileobject.write(chunk)
                if count==constants.CHUNK_ITER:await common.pipe.coro_send({"type":"update","args":(ele.id,),"completed":(pathlib.Path(temp).absolute().stat().st_size)});count=0                                        
        except Exception as E:
               # reset download data
            await common.pipe.coro_send(  (None, 0,-total))
            raise E
        finally:
            try:
                await common.pipe.coro_send({"type":"remove_task","args":(ele.id,)})   
            except:
                 None                         

            try:
                await fileobject.close()
            except Exception as E:
                None
          