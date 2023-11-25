

r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""
import asyncio
import re
import subprocess
from functools import partial
import pathlib
import traceback
from tenacity import stop_after_attempt,wait_random,AsyncRetrying,retry,retry_if_not_exception_type
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
import ofscraper.utils.logger as logger
from ofscraper.download.common import metadata,check_forced_skip,size_checker,\
addGlobalDir,moveHelper,sem_wrapper,set_time,get_medialog,update_total,get_item_total
import ofscraper.download.keyhelpers as keyhelpers
import ofscraper.download.common as common

async def alt_download(c,ele,path,username,model_id,progress):
    common.log.debug(f"{get_medialog(ele)} Downloading with protected media downloader")      
    filename=f'{placeholder.Placeholders().createfilename(ele,username,model_id,"mp4")}'  
    common.log.debug(f"{get_medialog(ele)} filename from config {filename}")
    common.log.debug(f"{get_medialog(ele)} full filepath from config{pathlib.Path(path,filename)}")
    path_to_file = paths.truncate(pathlib.Path(path,filename))
    common.log.debug(f"{get_medialog(ele)} full path trunicated from config {path_to_file}")
    if args_.getargs().metadata:
        return await metadata(c,ele,path,username,model_id,filename=filename,path_to_file=path_to_file) 
    temp_path=paths.truncate(pathlib.Path(path,f"temp_{ele.id or ele.filename_}.mp4"))
    common.log.debug(f"{get_medialog(ele)}  temporary path from combined audio/video {temp_path}")

    audio,video=await alt_download_preparer(ele)

    audio=await alt_download_downloader(audio,c,ele,path, path_to_file,progress)
    video=await alt_download_downloader(video,c,ele,path,path_to_file,progress)
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
        item=await keyhelpers.un_encrypt(item,c,ele)
    
    temp_path.unlink(missing_ok=True)
    t=subprocess.run([config_.get_ffmpeg(config_.read_config()),"-i",str(video["path"]),"-i",str(audio["path"]),"-c","copy","-movflags", "use_metadata_tags",str(temp_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if t.stderr.decode().find("Output")==-1:
        common.log.debug(f"{get_medialog(ele)} ffmpeg failed")
        common.log.debug(f"{get_medialog(ele)} ffmpeg {t.stderr.decode()}")
        common.log.debug(f"{get_medialog(ele)} ffmpeg {t.stdout.decode()}")

    video["path"].unlink(missing_ok=True)
    audio["path"].unlink(missing_ok=True)
    common.log.debug(f"Moving intermediate path {temp_path} to {path_to_file}")
    moveHelper(temp_path,path_to_file,ele)
    addGlobalDir(path_to_file)
    if ele.postdate:
        newDate=dates.convert_local_time(ele.postdate)
        common.log.debug(f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
        set_time(path_to_file,newDate )
        common.log.debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  
    if ele.id:
        await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=True)
    return ele.mediatype,video["total"]+audio["total"]

async def alt_download_preparer(ele):
    @sem_wrapper(common.mpd_sem)
    async def inner(ele):
        common.log.debug(f"{get_medialog(ele)} Attempting to get info for {ele.filename_} with {ele.mpd}")
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
    return await inner(ele)


@sem_wrapper   
async def alt_download_sendreq(item,c,ele,path,path_to_file,progress,total):
    base_url=re.sub("[0-9a-z]*\.mpd$","",ele.mpd,re.IGNORECASE)
    url=f"{base_url}{item['origname']}"
    common.log.debug(f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}")
    
    if item["type"]=="video":_attempt=common.attempt
    if item["type"]=="audio":_attempt=common.attempt2
    _attempt.set(_attempt.get(0) + 1)
    item["total"]=item["total"] if _attempt.get()==1 else None
    total=total if _attempt.get()==1 else None

    try:
        temp= paths.truncate(pathlib.Path(path,f"{item['name']}.part"))
        if total==None:temp.unlink(missing_ok=True)
        resume_size=0 if not pathlib.Path(temp).absolute().exists() else pathlib.Path(temp).absolute().stat().st_size        
        if not total or total>resume_size:
            headers= {"Range":f"bytes={resume_size}-{total}"} if pathlib.Path(temp).exists() else None
            params={"Policy":ele.policy,"Key-Pair-Id":ele.keypair,"Signature":ele.signature}   
            item["path"]=temp
            async with c.requests(url=url,headers=headers,params=params)() as l:                
                if l.ok:
                    total=int(l.headers['content-length'])
                    await update_total(total)
                    check1=await check_forced_skip(ele,path_to_file,total)
                    if check1:
                        return check1                
                    common.log.debug(f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] download temp path {temp}")
                    await alt_download_datahandler(item,total,l,ele,progress,path)        
                else:                            
                    common.log.debug(f"[bold]  {get_medialog(ele)}  alt download status[/bold]: {l.status}")
                    common.log.debug(f"[bold] {get_medialog(ele)}  alt download text [/bold]: {await l.text_()}")
                    common.log.debug(f"[bold]  {get_medialog(ele)} alt download  headers [/bold]: {l.headers}")   
                    l.raise_for_status()
            await size_checker(temp,ele,total) 
        return item           
    except OSError as E:
        common.log.traceback(E)
        common.log.traceback(traceback.format_exc())
        common.log.debug(f"Number of Open Files -> { len(psutil.Process().open_files())}")      
        common.log.debug(f"Open Files -> {list(map(lambda x:(x.path,x.fd),psutil.Process().open_files()))}")              
    except Exception as E:
        common.log.traceback(f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] {traceback.format_exc()}")
        common.log.traceback(f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] {E}")  
        raise E
async def alt_download_datahandler(item,total,l,ele,progress,path):
    temp= item["path"]
    pathstr=str(temp)
    

    downloadprogress=config_.get_show_downloadprogress(config_.read_config()) or args_.getargs().downloadbars
    task1 = progress.add_task(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n", total=total,visible=True if downloadprogress else False)
    count=0
    loop=asyncio.get_event_loop()
    
    fileobject= await aiofiles.open(temp, 'ab').__aenter__()
    try:
        async for chunk in l.iter_chunked(constants.maxChunkSize):
            if downloadprogress:count=count+1
            common.log.trace(f"{get_medialog(ele)} Download:{(pathlib.Path(temp).absolute().stat().st_size)}/{total}")
            await fileobject.write(chunk)
            if count==constants.CHUNK_ITER:await loop.run_in_executor(common.thread,partial( progress.update,task1, completed=pathlib.Path(path).absolute().stat().st_size));count=0
        data=l.headers
        await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.set,f"{item['name']}_headers",{"content-length":data.get("content-length"),"content-type":data.get("content-type")}))            
    except Exception as E:
        await update_total(-total)
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


async def alt_download_downloader(item,c,ele,path,path_to_file,progress):
    data=await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.get,f"{item['name']}_headers"))
    temp= paths.truncate(pathlib.Path(path,f"{item['name']}.part"))
    item['path']=temp
    pathlib.Path(temp).unlink(missing_ok=True) if (args_.getargs().part_cleanup or config_.get_part_file_clean(config_.read_config()) or False) else None

    if data:
        item["total"]=int(data.get("content-length"))
        check1=await check_forced_skip(ele,path_to_file,item["total"])
        item["path"]=temp
        resume_size=0 if not pathlib.Path(temp).exists() else pathlib.Path(temp).absolute().stat().st_size
        if check1:
            return check1
        elif item["total"]==resume_size:
                return item
        elif item["total"]<resume_size:
                pathlib.Path(temp).unlink(missing_ok=True)
       
    else:
        paths.truncate(pathlib.Path(path,f"{item['name']}.part")).unlink(missing_ok=True)        
    try:
            async for _ in AsyncRetrying(stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True):
                with _:
                    try:
                        total=int(data.get("content-length")) if data else None
                        return await alt_download_sendreq(item,c,ele,path,path_to_file,progress,total)
                    except Exception as E:
                        raise E
    except Exception as E:
        pass




  
 

