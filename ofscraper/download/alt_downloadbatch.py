import asyncio
import re
import pathlib
import subprocess
import traceback
from functools import singledispatch,partial
from tenacity import retry,stop_after_attempt,wait_random,AsyncRetrying,retry_if_not_exception_type
import aiofiles
import arrow
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
import ofscraper.utils.logger as logger
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
,size_checker,moveHelper,addLocalDir,set_time,get_item_total
import ofscraper.download.common as common
import ofscraper.download.keyhelpers as keyhelpers
                
        




async def alt_download(c,ele,path,username,model_id):

    common.innerlog.get().debug(f"{get_medialog(ele)} Downloading with protected media downloader")      
    common.innerlog.get().debug(f"{get_medialog(ele)} Attempting to download media {ele.filename_} with {ele.mpd}")
    filename=f'{placeholder.Placeholders().createfilename(ele,username,model_id,"mp4")}'
    common.innerlog.get().debug(f"{get_medialog(ele)} filename from config {filename}")
    common.innerlog.get().debug(f"{get_medialog(ele)} full filepath from config{pathlib.Path(path,filename)}")
    path_to_file = paths.truncate(pathlib.Path(path,filename))
    common.innerlog.get().debug(f"{get_medialog(ele)} full path trunicated from config {path_to_file}") 
    temp_path=paths.truncate(pathlib.Path(path,f"temp_{ele.id or ele.filename_}.mp4"))
    common.log.debug(f"Media:{ele.id} Post:{ele.postid}  temporary path from combined audio/video {temp_path}")
    audio,video=await alt_download_preparer(ele)

    audio=await alt_download_downloader(audio,c,ele,path)
    video=await alt_download_downloader(video,c,ele,path)

    for m in [audio,video]:
        m["total"]=get_item_total(m)
        if not isinstance(m,dict):
            return m
        check1=await size_checker(m["path"],ele,m["total"])
        check2=await check_forced_skip(ele,path_to_file,m["total"])
        if check1:
            return check1
        if check2:
            return check2
    for item in [audio,video]:
        item=await keyhelpers.un_encrypt(item,c,ele,common.innerlog.get())

    temp_path.unlink(missing_ok=True)
    t=subprocess.run([config_.get_ffmpeg(config_.read_config()),"-i",str(video["path"]),"-i",str(audio["path"]),"-c","copy","-movflags", "use_metadata_tags",str(temp_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if t.stderr.decode().find( "Output")==-1:
        common.innerlog.get().debug(f"{get_medialog(ele)} ffmpeg failed")
        common.innerlog.get().debug(f"{get_medialog(ele)} ffmpeg {t.stderr.decode()}")
        common.innerlog.get().debug(f"{get_medialog(ele)} ffmpeg {t.stdout.decode()}")
    video["path"].unlink(missing_ok=True)
    audio["path"].unlink(missing_ok=True)
    common.innerlog.get().debug(f"Moving intermediate path {temp_path} to {path_to_file}")
    moveHelper(temp_path,path_to_file,ele,common.innerlog.get())
    addLocalDir(path_to_file)
    if ele.postdate:
        newDate=dates.convert_local_time(ele.postdate)
        set_time(path_to_file,newDate )
        common.innerlog.get().debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  
    if ele.id:
        await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=True)
    return ele.mediatype,video["total"]+audio["total"]
async def alt_download_preparer(ele):
    mpd=await ele.parse_mpd
    for period in mpd.periods:
                for adapt_set in filter(lambda x:x.mime_type=="video/mp4",period.adaptation_sets):             
                    kId=None
                    for prot in adapt_set.content_protections:
                        if prot.value==None:
                            kId = prot.pssh[0].pssh 
                            break
                    maxquality=max(map(lambda x:x.height,adapt_set.representations))
                    for repr in adapt_set.representations:
                        origname=f"{repr.base_urls[0].base_url_value}"
                        if repr.height==maxquality:
                            video={"origname":origname,"pssh":kId,"type":"video","name":f"tempvid_{origname}"}
                            break
                for adapt_set in filter(lambda x:x.mime_type=="audio/mp4",period.adaptation_sets):             
                    kId=None
                    for prot in adapt_set.content_protections:
                        if prot.value==None:
                            kId = prot.pssh[0].pssh 
                            logger.updateSenstiveDict(kId,"pssh_code")
                            break
                    for repr in adapt_set.representations:
                        origname=f"{repr.base_urls[0].base_url_value}"
                        audio={"origname":origname,"pssh":kId,"type":"audio","name":f"tempaudio_{origname}"}
                        break
    return audio,video
  


@sem_wrapper    
async def alt_download_sendreq(item,c,ele,path_to_file):
    base_url=re.sub("[0-9a-z]*\.mpd$","",ele.mpd,re.IGNORECASE)
    url=f"{base_url}{item['origname']}"
    common.innerlog.get().debug(f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}")
    
    if item["type"]=="video":_attempt=common.attempt
    if item["type"]=="audio":_attempt=common.attempt2
    _attempt.set(_attempt.get(0)+1) 
    item["total"]=item["total"] if _attempt.get()==1 else None

    try:
        total=item.get("total")
        temp= paths.truncate(pathlib.Path(path_to_file,f"{item['name']}.part"))
        if total==None:temp.unlink(missing_ok=True)
        resume_size=0 if not pathlib.Path(temp).absolute().exists() else pathlib.Path(temp).absolute().stat().st_size
        
        if not total or total>resume_size:
            headers= {"Range":f"bytes={resume_size}-{total}"} if pathlib.Path(temp).exists() else None
            params={"Policy":ele.policy,"Key-Pair-Id":ele.keypair,"Signature":ele.signature}   
            item["path"]=temp
            async with c.requests(url=url,headers=headers,params=params)() as l:                
                if l.ok:
                    total=int(l.headers['content-length'])
                    await common.pipe.coro_send(  (None, 0,total))
                    await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.set,f"{item['name']}_headers",{"content-length":l.headers.get("content-length"),"content-type":l.headers.get("content-type")}))
                    check1=await check_forced_skip(ele,path_to_file,total)
                    if check1:
                        return check1
                    common.innerlog.get().debug(f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] download temp path {temp}")
                    await alt_download_datahandler(item,total,l,ele)        

                else:
                    common.innerlog.get().debug(f"[bold]  {get_medialog(ele)}  main download data finder status[/bold]: {l.status}")
                    common.innerlog.get().debug(f"[bold] {get_medialog(ele)}  main download data finder text [/bold]: {await l.text_()}")
                    common.innerlog.get().debug(f"[bold]  {get_medialog(ele)} main download data finder headeers [/bold]: {l.headers}")   
                    l.raise_for_status()
            await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.set,f"{item['name']}_headers",{"content-length":l.headers.get("content-length"),"content-type":l.headers.get("content-type")}))
            await size_checker(temp,ele,total) 
        
        return item
    except OSError as E:
        common.log.traceback(E)
        common.log.traceback(traceback.format_exc())
        common.log.debug(f" Number of open Files across all processes-> {len(system.getOpenFiles(unique=False))}")   
        common.log.debug(f" Number of unique open files across all processes-> {len(system.getOpenFiles())}")   
        common.log.debug(f"Unique files data across all process -> {list(map(lambda x:(x.path,x.fd),(system.getOpenFiles())))}" )
    except Exception as E:
        common.innerlog.get().traceback(f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] {traceback.format_exc()}")
        common.innerlog.get().traceback(f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] {E}")
        raise E

async def alt_download_datahandler(item,total,l,ele):
    temp= item["path"]
    pathstr=str(temp)
    try:
        count=0
        await common.pipe.coro_send({"type":"add_task","args":(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n",ele.id),
                                "total":total,"visible":False})
        fileobject= await aiofiles.open(temp, 'ab').__aenter__()
        await  common.pipe.coro_send({"type":"update","args":(ele.id,),"visible":True})

        async for chunk in l.iter_chunked(constants.maxChunkSizeB):
            count=count+1
            common.innerlog.get().trace(f"{get_medialog(ele)} Download:{(pathlib.Path(temp).absolute().stat().st_size)}/{total}")
            await fileobject.write(chunk)
            if count==constants.CHUNK_ITER:await common.pipe.coro_send({"type":"update","args":(ele.id,),"completed":(pathlib.Path(temp).absolute().stat().st_size)});count=0
    except Exception as E:
        # reset download data
        await common.pipe.coro_send(  (None, 0,-total))
        raise E
    finally:
        #Close file if needed
        try:
            await fileobject.close()
        except Exception as E:
            None

        try:
            await common.pipe.coro_send({"type":"remove_task","args":(ele.id,)})
        except Exception as E:
            None




async def alt_download_downloader(item,c,ele,path_to_file):
    data=await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.get,f"{item['name']}_headers")) 
    temp= paths.truncate(pathlib.Path(path_to_file,f"{item['name']}.part"))
    item['path']=temp
    pathlib.Path(temp).unlink(missing_ok=True) if (args_.getargs().part_cleanup or config_.get_part_file_clean(config_.read_config()) or False) else None

    if data:
        item["total"]=int(data.get("content-length"))
        check1=await check_forced_skip(ele,path_to_file,item["total"])
        resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
        if check1:
            return check1
        elif item["total"]==resume_size:
            return item
        elif item["total"]<resume_size:
            pathlib.Path(temp).unlink(missing_ok=True)
    else:
        paths.truncate(pathlib.Path(path_to_file,f"{item['name']}.part")).unlink(missing_ok=True)
    try:
        async for _ in AsyncRetrying(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True):
            with _:
                try:
                    return await alt_download_sendreq(item,c,ele,path_to_file)
                except Exception as E:
                    raise E
    except Exception as E:
        pass

