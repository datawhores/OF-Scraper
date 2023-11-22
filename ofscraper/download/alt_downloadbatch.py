import asyncio
import re
import json
import pathlib
import subprocess
import traceback
from functools import singledispatch,partial
from tenacity import retry,stop_after_attempt,wait_random,AsyncRetrying,retry_if_not_exception_type
import aiofiles
import arrow
from bs4 import BeautifulSoup
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.logger as logger
import ofscraper.utils.auth as auth
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
,size_checker,moveHelper,addLocalDir,set_time
import ofscraper.download.common as common
                
        




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
        if not isinstance(m,dict):
            return m
        check1=await size_checker(m["path"],ele,m["total"])
        check2=await check_forced_skip(ele,path_to_file,m["total"])
        if check1:
            return check1
        if check2:
            return check2
    for item in [audio,video]:
        item=await un_encrypt(item,c,ele)
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
    return ele.mediatype,audio["total"]+video["total"]

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
    fileobject=None
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
                    pathstr=str(temp)
                    item["total"]=int(total or (l.headers['content-length']))
                    total=item["total"]
                    if _attempt.get(0) + 1==1:await common.pipe.coro_send(  (None, 0,total))
                    data=l.headers
                    await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.set,f"{item['name']}_headers",{"content-length":data.get("content-length"),"content-type":data.get("content-type")}))
                    check1=await check_forced_skip(ele,path_to_file,item["total"])
                    if check1:
                        return check1
                    common.innerlog.get().debug(f"{get_medialog(ele)} [attempt {_attempt.get()}/{constants.NUM_TRIES}] download temp path {temp}")
                    await common.pipe.coro_send({"type":"add_task","args":(f"{(pathstr[:constants.PATH_STR_MAX] + '....') if len(pathstr) > constants.PATH_STR_MAX else pathstr}\n",ele.id),
                                "total":total,"visible":False})
                    await common.pipe.coro_send({"type":"update","args":(ele.id,),"completed":resume_size,"visible":True})     
                    count=0
                    fileobject= await aiofiles.open(temp, 'ab').__aenter__()
                    async for chunk in l.iter_chunked(constants.maxChunkSizeB):
                        count=count+1
                        common.innerlog.get().trace(f"{get_medialog(ele)} Download:{(pathlib.Path(temp).absolute().stat().st_size)}/{total}")
                        await fileobject.write(chunk)
                        if count==constants.CHUNK_ITER:await common.pipe.coro_send({"type":"update","args":(ele.id,),"completed":(pathlib.Path(temp).absolute().stat().st_size)});count=0
                    await common.pipe.coro_send({"type":"remove_task","args":(ele.id,)})

                else:
                    common.innerlog.get().debug(f"[bold]  {get_medialog(ele)}  main download data finder status[/bold]: {l.status}")
                    common.innerlog.get().debug(f"[bold] {get_medialog(ele)}  main download data finder text [/bold]: {await l.text_()}")
                    common.innerlog.get().debug(f"[bold]  {get_medialog(ele)} main download data finder headeers [/bold]: {l.headers}")   
                    l.raise_for_status()
            await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.set,f"{item['name']}_headers",{"content-length":data.get("content-length"),"content-type":data.get("content-type")}))
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
    finally:
        try:
            await fileobject.close()
        except Exception as E:
            raise None

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
                    common.innerlog.get().debug(f"{get_medialog(ele)} {E} {_.retry_state.attempt_number} alt expection")
                    raise E
    except Exception as E:
        pass

async def un_encrypt(item,c,ele):
    key=None
    keymode=(args_.getargs().key_mode or config_.get_key_mode(config_.read_config()) or "cdrm")

    past_key=await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.get,ele.license))
    if past_key:
        key=past_key
        common.log.debug(f"ID:{ele.id} cdrm auto key helper got key from cache")
    elif  keymode== "manual": key=await key_helper_manual(item["pssh"],ele.license,ele.id)  
    elif keymode=="keydb":key=await key_helper_keydb(c,item["pssh"],ele.license,ele.id)  
    elif keymode=="cdrm": key=await key_helper_cdrm(c,item["pssh"],ele.license,ele.id)  
    elif keymode=="cdrm2": key=await key_helper_cdrm2(c,item["pssh"],ele.license,ele.id) 
    
    if key==None:
        raise Exception(f"{get_medialog(ele)} Could not get key")
    await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.set,ele.license,key, expire=constants.KEY_EXPIRY))
    common.innerlog.get().debug(f"{get_medialog(ele)} got key")
    newpath=pathlib.Path(re.sub("\.part$","",str(item["path"]),re.IGNORECASE))
    common.innerlog.get().debug(f"{get_medialog(ele)}  renaming {pathlib.Path(item['path']).absolute()} -> {newpath}")   
    r=subprocess.run([config_.get_mp4decrypt(config_.read_config()),"--key",key,str(item["path"]),str(newpath)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if not pathlib.Path(newpath).exists():
        common.innerlog.get().debug(f"{get_medialog(ele)} mp4decrypt failed")
        common.innerlog.get().debug(f"{get_medialog(ele)} mp4decrypt {r.stderr.decode()}")
        common.innerlog.get().debug(f"{get_medialog(ele)} mp4decrypt {r.stdout.decode()}")
    else:
        common.innerlog.get().debug(f"{get_medialog(ele)} mp4decrypt success {newpath}")    
    pathlib.Path(item["path"]).unlink(missing_ok=True)
    item["path"]=newpath
    return item


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_cdrm(c,pssh,licence_url,id):
    common.log.debug(f"ID:{id} using cdrm auto key helper")
    try:
        common.log.debug(f"ID:{id} pssh: {pssh!=None}")
        common.log.debug(f"ID:{id} licence: {licence_url}")
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
            httpcontent=await r.text_()
            common.log.debug(f"ID:{id} key_response: {httpcontent}")
            soup = BeautifulSoup(httpcontent, 'html.parser')
            out=soup.find("li").contents[0]          
        return out

    except Exception as E:
        common.log.traceback(E)
        common.log.traceback(traceback.format_exc())
        raise E 

     


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_cdrm2(c,pssh,licence_url,id):
    common.innerlog.get().debug(f"ID:{id} using cdrm auto key helper")
    try:
        common.innerlog.get().debug(f"ID:{id} pssh: {pssh!=None}")
        common.innerlog.get().debug(f"ID:{id} licence: {licence_url}")
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
            httpcontent=await r.text_()
            common.innerlog.get().debug(f"ID:{id} key_response: {httpcontent}")
            soup = BeautifulSoup(httpcontent, 'html.parser')
            out=soup.find("li").contents[0]
        return out
    except Exception as E:
        common.innerlog.get().traceback(E)
        common.innerlog.get().traceback(traceback.format_exc())
        raise E


@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_keydb(c,pssh,licence_url,id):
    common.innerlog.get().debug(f"ID:{id} using keydb auto key helper")
    try:
        common.innerlog.get().debug(f"ID:{id} pssh: {pssh!=None}")
        common.innerlog.get().debug(f"ID:{id} licence: {licence_url}")
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
            data=await r.json()
            common.innerlog.get().debug(f"keydb json {data}")
            if  isinstance(data,str): out=data
            elif isinstance(data["keys"][0],str):
                out=data["keys"][0]
            elif  isinstance(data["keys"][0],object):
                 out==data["keys"][0]["key"]
        return out
    except Exception as E:
        common.innerlog.get().traceback(E)
        common.innerlog.get().traceback(traceback.format_exc())
        raise E


       
@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_manual(pssh,licence_url,id):
    common.innerlog.get().debug(f"ID:{id} using manual key helper")
    async with sessionbuilder.sessionBuilder(backend="aio") as c:
        try:
            common.innerlog.get().debug(f"ID:{id} pssh: {pssh!=None}")
            common.innerlog.get().debug(f"ID:{id} licence: {licence_url}")

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
                keys = cdm.get_keys(session_id)
                cdm.close(session_id)
            keyobject=list(filter(lambda x:x.type=="CONTENT",keys))[0]
            key="{}:{}".format(keyobject.kid.hex,keyobject.key.hex())
            return key
        except Exception as E:
            common.innerlog.get().traceback(E)
            common.innerlog.get().traceback(traceback.format_exc())
            raise E 
