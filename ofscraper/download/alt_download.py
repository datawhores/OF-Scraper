

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
import json
from concurrent.futures import ThreadPoolExecutor
import subprocess
from functools import partial
import pathlib
import traceback
from bs4 import BeautifulSoup
from tenacity import stop_after_attempt,wait_random,AsyncRetrying,retry,retry_if_not_exception_type
import arrow
import aiofiles
import psutil
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH
import ofscraper.classes.sessionbuilder as sessionbuilder

import ofscraper.utils.auth as auth
import ofscraper.utils.config as config_
import ofscraper.utils.paths as paths
import ofscraper.constants as constants
import ofscraper.utils.config as config_
import ofscraper.utils.args as args_
import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.dates as dates
import ofscraper.db.operations as operations
import ofscraper.utils.logger as logger
from ofscraper.download.utils import cache,cache_thread,log,metadata,check_forced_skip,size_checker,\
addGlobalDir,moveHelper,sem_wrapper,set_time,get_medialog,update_total,attempt,attempt2,mpd_sem

async def alt_download(c,ele,path,username,model_id,progress):
    log.debug(f"{get_medialog(ele)} Downloading with protected media downloader")      
    global thread
    thread=ThreadPoolExecutor(max_workers=config_.get_download_semaphores(config_.read_config())*2)
    filename=f'{placeholder.Placeholders().createfilename(ele,username,model_id,"mp4")}'  
    log.debug(f"{get_medialog(ele)} filename from config {filename}")
    log.debug(f"{get_medialog(ele)} full filepath from config{pathlib.Path(path,filename)}")
    path_to_file = paths.truncate(pathlib.Path(path,filename))
    log.debug(f"{get_medialog(ele)} full path trunicated from config {path_to_file}")
    if args_.getargs().metadata:
        return await metadata(c,ele,path,username,model_id,filename=filename,path_to_file=path_to_file) 
    temp_path=paths.truncate(pathlib.Path(path,f"temp_{ele.id or ele.filename_}.mp4"))
    log.debug(f"{get_medialog(ele)}  temporary path from combined audio/video {temp_path}")

    audio,video=await alt_download_preparer(ele)

    audio=await alt_download_downloader(audio,c,ele,path,progress)
    video=await alt_download_downloader(video,c,ele,path,progress)
    for m in [audio,video]:
        if not isinstance(m,dict):
            return m
        check1=await size_checker(m["path"],ele,m["total"])  
        check2=check_forced_skip(ele,m["total"])
        if check1:
            return check1
        if check2:
            return check2
    for item in [audio,video]:
        key=None
        keymode=(args_.getargs().key_mode or config_.get_key_mode(config_.read_config()) or "cdrm")
        if  keymode== "manual": key=await key_helper_manual(c,item["pssh"],ele.license,ele.id)  
        elif keymode=="keydb":key=await key_helper_keydb(c,item["pssh"],ele.license,ele.id)  
        elif keymode=="cdrm": key=await key_helper_cdrm(c,item["pssh"],ele.license,ele.id)  
        elif keymode=="cdrm2": key=await key_helper_cdrm2(c,item["pssh"],ele.license,ele.id) 
        if key==None:
            raise Exception(f"{get_medialog(ele)} Could not get key")
        log.debug(f"{get_medialog(ele)} got key")
        newpath=pathlib.Path(re.sub("\.part$","",str(item["path"]),re.IGNORECASE))
        log.debug(f"{get_medialog(ele)}  renaming {pathlib.Path(item['path']).absolute()} -> {newpath}")   
        r=subprocess.run([config_.get_mp4decrypt(config_.read_config()),"--key",key,str(item["path"]),str(newpath)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if not pathlib.Path(newpath).exists():
            log.debug(f"{get_medialog(ele)} mp4decrypt failed")
            log.debug(f"{get_medialog(ele)} mp4decrypt {r.stderr.decode()}")
            log.debug(f"{get_medialog(ele)} mp4decrypt {r.stdout.decode()}")
        else:
            log.debug(f"{get_medialog(ele)} mp4decrypt success {newpath}")    
        pathlib.Path(item["path"]).unlink(missing_ok=True)
        item["path"]=newpath
    
    temp_path.unlink(missing_ok=True)
    t=subprocess.run([config_.get_ffmpeg(config_.read_config()),"-i",str(video["path"]),"-i",str(audio["path"]),"-c","copy","-movflags", "use_metadata_tags",str(temp_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if t.stderr.decode().find("Output")==-1:
        log.debug(f"{get_medialog(ele)} ffmpeg failed")
        log.debug(f"{get_medialog(ele)} ffmpeg {t.stderr.decode()}")
        log.debug(f"{get_medialog(ele)} ffmpeg {t.stdout.decode()}")

    video["path"].unlink(missing_ok=True)
    audio["path"].unlink(missing_ok=True)
    log.debug(f"Moving intermediate path {temp_path} to {path_to_file}")
    moveHelper(temp_path,path_to_file,ele)
    addGlobalDir(path_to_file)
    if ele.postdate:
        newDate=dates.convert_local_time(ele.postdate)
        log.debug(f"{get_medialog(ele)} Attempt to set Date to {arrow.get(newDate).format('YYYY-MM-DD HH:mm')}")  
        set_time(path_to_file,newDate )
        log.debug(f"{get_medialog(ele)} Date set to {arrow.get(path_to_file.stat().st_mtime).format('YYYY-MM-DD HH:mm')}")  
    if ele.id:
        await operations.update_media_table(ele,filename=path_to_file,model_id=model_id,username=username,downloaded=True)
    return ele.mediatype,audio["total"]+video["total"]

async def alt_download_preparer(ele):
    @sem_wrapper(mpd_sem)
    async def inner(ele):
        log.debug(f"{get_medialog(ele)} Attempting to get info for {ele.filename_} with {ele.mpd}")
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
async def alt_download_sendreq(item,c,ele,path,progress):
    base_url=re.sub("[0-9a-z]*\.mpd$","",ele.mpd,re.IGNORECASE)
    url=f"{base_url}{item['origname']}"
    log.debug(f"{get_medialog(ele)} Attempting to download media {item['origname']} with {url}")
    
    if item["type"]=="video":_attempt=attempt
    if item["type"]=="audio":_attempt=attempt2
    _attempt.set(_attempt.get(0) + 1)
    fileobject=None 
    item["total"]=item["total"] if _attempt.get()==1 else None

    try:
        total=item.get("total")
        temp= paths.truncate(pathlib.Path(path,f"{item['name']}.part"))
        if total==None:temp.unlink(missing_ok=True)
        resume_size=0 if not pathlib.Path(temp).absolute().exists() else pathlib.Path(temp).absolute().stat().st_size        

        if not total or total>resume_size:
            headers= {"Range":f"bytes={resume_size}-{total}"} if pathlib.Path(temp).exists() else None
            params={"Policy":ele.policy,"Key-Pair-Id":ele.keypair,"Signature":ele.signature}   
            item["path"]=temp
            async with c.requests(url=url,headers=headers,params=params)() as l:                
                if l.ok:
                    item["total"]=int(total or (l.headers['content-length']))
                    total=item["total"]
                    if attempt.get(0) + 1==1:await update_total(total)
                    check1=check_forced_skip(ele,item["total"])
                    if check1:
                        return check1                
                    log.debug(f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] download temp path {temp}")
                    await alt_download_datahandler(item,l,ele,progress,path)        
                                            
                    log.debug(f"[bold]  {get_medialog(ele)}  alt download data finder status[/bold]: {l.status}")
                    log.debug(f"[bold] {get_medialog(ele)}  alt download data finder text [/bold]: {await l.text_()}")
                    log.debug(f"[bold]  {get_medialog(ele)} alt download data finder headeers [/bold]: {l.headers}")   
                    l.raise_for_status()
            await size_checker(temp,ele,total) 
        return item           
    except OSError as E:
        log.traceback(E)
        log.traceback(traceback.format_exc())
        log.debug(f"Number of Open Files -> { len(psutil.Process().open_files())}")      
        log.debug(f"Open Files -> {list(map(lambda x:(x.path,x.fd),psutil.Process().open_files()))}")              
    except Exception as E:
        log.traceback(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] {traceback.format_exc()}")
        log.traceback(f"{get_medialog(ele)} [attempt {attempt.get()}/{constants.NUM_TRIES}] {E}")  
        raise E
    finally:
        #Close file if needed
        try:
            await fileobject.close()
        except Exception as E:
            None
async def alt_download_datahandler(item,l,ele,progress,path):
    total=item["total"]
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
            log.trace(f"{get_medialog(ele)} Download:{(pathlib.Path(temp).absolute().stat().st_size)}/{total}")
            await fileobject.write(chunk)
            if count==constants.CHUNK_ITER:await loop.run_in_executor(thread,partial( progress.update,task1, completed=pathlib.Path(path).absolute().stat().st_size));count=0
        data=l.headers
        await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,f"{item['name']}_headers",{"content-length":data.get("content-length"),"content-type":data.get("content-type")}))            
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


async def alt_download_downloader(item,c,ele,path,progress):
    data=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,f"{item['name']}_headers"))
    temp= paths.truncate(pathlib.Path(path,f"{item['name']}.part"))
    item['path']=temp
    pathlib.Path(temp).unlink(missing_ok=True) if (args_.getargs().part_cleanup or config_.get_part_file_clean(config_.read_config()) or False) else None

    if data:
        item["total"]=int(data.get("content-length"))
        check1=check_forced_skip(ele,item["total"])
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
                        return await alt_download_sendreq(item,c,ele,path,progress)
                    except Exception as E:
                        log.debug(f"{get_medialog(ele)} {E} {_.retry_state.attempt_number} alt expection")
                        raise E
    except Exception as E:
        pass




  
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_cdrm(c,pssh,licence_url,id):
    log.debug(f"ID:{id} using cdrm auto key helper")
    try:
        out=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,licence_url))
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        if out!=None:
            log.debug(f"ID:{id} cdrm auto key helper got key from cache")
            return out
        headers=auth.make_headers(auth.read_auth())
        headers["cookie"]=auth.get_cookies()
        auth.create_sign(licence_url,headers)
        json_data = {
            'license': licence_url,
            'headers': json.dumps(headers),
            'pssh': pssh,
            'buildInfo': '',
            'proxy': '',
            'cache': True,
        }
        async with c.requests(url=constants.CDRM,method="post",json=json_data)() as r:
            if r.ok:
                httpcontent=await r.text_()
                log.debug(f"ID:{id} key_response: {httpcontent}")
                soup = BeautifulSoup(httpcontent, 'html.parser')
                out=soup.find("li").contents[0]
                await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,licence_url,out, expire=constants.KEY_EXPIRY))
            else:
                log.debug(f"[bold]  key helper cdrm status[/bold]: {r.status}")
                log.debug(f"[bold]  key helper cdrm text [/bold]: {await r.text_()}")
                log.debug(f"[bold]  key helper cdrm headers [/bold]: {r.headers}") 
                r.raise_for_status()
            return out
    except Exception as E:        
        log.traceback(E)
        log.traceback(traceback.format_exc())
        raise E

       
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_cdrm2(c,pssh,licence_url,id):
    log.debug(f"ID:{id} using cdrm2 auto key helper")
    try:
        out=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,licence_url))
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        if out!=None:
            log.debug(f"ID:{id} cdrm2 auto key helper got key from cache")
            return out
        headers=auth.make_headers(auth.read_auth())
        headers["cookie"]=auth.get_cookies()
        auth.create_sign(licence_url,headers)
        json_data = {
            'license': licence_url,
            'headers': json.dumps(headers),
            'pssh': pssh,
            'buildInfo': 'google/sdk_gphone_x86/generic_x86:8.1.0/OSM1.180201.037/6739391:userdebug/dev-keys',
            'proxy': '',
            'cache': True,
        }
        async with c.requests(url=constants.CDRM2,method="post",json=json_data)() as r:
            if r.ok:
                httpcontent=await r.text_()
                log.debug(f"ID:{id} key_response: {httpcontent}")
                soup = BeautifulSoup(httpcontent, 'html.parser')
                out=soup.find("li").contents[0]
                await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,licence_url,out, expire=constants.KEY_EXPIRY))
            else:
                log.debug(f"[bold]  key helper cdrm2 status[/bold]: {r.status}")
                log.debug(f"[bold]  key helper cdrm2 text [/bold]: {await r.text_()}")
                log.debug(f"[bold]  key helper cdrm2 headers [/bold]: {r.headers}")    
                r. raise_for_status()  
        return out
    except Exception as E:    
        log.traceback(E)
        log.traceback(traceback.format_exc())
        raise E


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_keydb(c,pssh,licence_url,id):
    log.debug(f"ID:{id} using keydb auto key helper")
    try:
        out=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,licence_url))
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        if out!=None:
            log.debug(f"ID:{id} keydb auto key helper got key from cache")
            return out
        headers=auth.make_headers(auth.read_auth())
        headers["cookie"]=auth.get_cookies()
        auth.create_sign(licence_url,headers)
        json_data = {
            'license_url': licence_url,
            'headers': json.dumps(headers),
            'pssh': pssh,
            'buildInfo': '',
            'proxy': '',
            'cache': True,
        }
  
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (Ktesttemp, like Gecko) Chrome/90.0.4430.85 Safari/537.36",
            "Content-Type": "application/json",
            "X-API-Key": config_.get_keydb_api(config_.read_config()),
        }
   




        async with c.requests(url=constants.KEYDB,method="post",json=json_data,headers=headers)() as r:
            if r.ok:
                data=await r.json()
                log.debug(f"keydb json {data}")
                if  isinstance(data,str): out=data
                elif isinstance(data["keys"][0],str):
                    out=data["keys"][0]
                elif  isinstance(data["keys"][0],object):
                    out=data["keys"][0]["key"]
                await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,licence_url,out, expire=constants.KEY_EXPIRY))
            else:
                log.debug(f"[bold]  key helper keydb status[/bold]: {r.status}")
                log.debug(f"[bold]  key helper keydb text [/bold]: {await r.text_()}")
                log.debug(f"[bold]  key helper keydb headers [/bold]: {r.headers}")  
                r.raise_for_status()
        return out
    except Exception as E:         
        log.traceback(E)
        log.traceback(traceback.format_exc())
        raise E 

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_manual(c,pssh,licence_url,id):
    async with sessionbuilder.sessionBuilder(backend="httpx") as c:
        log.debug(f"ID:{id} using manual key helper")
        try:
            out=await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.get,licence_url))
            if out!=None:
                log.debug(f"ID:{id} manual key helper got key from cache")
                return out
            log.debug(f"ID:{id} pssh: {pssh!=None}")
            log.debug(f"ID:{id} licence: {licence_url}")

            # prepare pssh
            pssh = PSSH(pssh)


            # load device
            private_key=pathlib.Path(config_.get_private_key(config_.read_config())).read_bytes()
            client_id=pathlib.Path(config_.get_client_id(config_.read_config())).read_bytes()
            device = Device(security_level=3,private_key=private_key,client_id=client_id,type_="ANDROID",flags=None)


            # load cdm
            cdm = Cdm.from_device(device)

            # open cdm session
            session_id = cdm.open()

            
            keys=None
            challenge = cdm.get_license_challenge(session_id, pssh)
            async with c.requests(url=licence_url,method="post",data=challenge)() as r:            
                cdm.parse_license(session_id, (await r.content.read()))

                # cdm.parse_license(session_id, (await r.content.read()))
                keys = cdm.get_keys(session_id)
                cdm.close(session_id)
            keyobject=list(filter(lambda x:x.type=="CONTENT",keys))[0]

            
            key="{}:{}".format(keyobject.kid.hex,keyobject.key.hex())
            await asyncio.get_event_loop().run_in_executor(cache_thread,partial( cache.set,licence_url,out, expire=constants.KEY_EXPIRY))
            return key
        except Exception as E:
            log.traceback(E)
            log.traceback(traceback.format_exc())
            raise E 

