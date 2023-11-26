import traceback
import asyncio
import re
import pathlib
from functools import partial
import subprocess
import json
from bs4 import BeautifulSoup
from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH
from tenacity import retry_if_not_exception_type,stop_after_attempt,retry,wait_random
import ofscraper.download.common as common
import ofscraper.constants as constants
import ofscraper.utils.auth as auth
import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.config as config_
import ofscraper.utils.args as args_
from ofscraper.download.common import get_medialog
log=None
def setLog(input_):
    global log
    log=input_

async def un_encrypt(item,c,ele,input_=None):
    setLog(input_ or common.log)
    key=None
    keymode=(args_.getargs().key_mode or config_.get_key_mode(config_.read_config()) or "cdrm")
    past_key=await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.get,ele.license))
    if past_key:
        key=past_key
        log.debug(f"{get_medialog(ele)} got key from cache")
    if  keymode== "manual": key=await key_helper_manual(c,item["pssh"],ele.license,ele.id)  
    elif keymode=="keydb":key=await key_helper_keydb(c,item["pssh"],ele.license,ele.id)  
    elif keymode=="cdrm": key=await key_helper_cdrm(c,item["pssh"],ele.license,ele.id)  
    elif keymode=="cdrm2": key=await key_helper_cdrm2(c,item["pssh"],ele.license,ele.id) 
    if key==None:
        raise Exception(f"{get_medialog(ele)} Could not get key")
    await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.set,ele.license,key, expire=constants.KEY_EXPIRY))
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
    return item

@retry(retry=retry_if_not_exception_type(KeyboardInterrupt),stop=stop_after_attempt(constants.NUM_TRIES),wait=wait_random(min=constants.OF_MIN, max=constants.OF_MAX),reraise=True) 
async def key_helper_cdrm(c,pssh,licence_url,id):
    log.debug(f"ID:{id} using cdrm auto key helper")
    try:
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
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
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
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
        log.debug(f"ID:{id} pssh: {pssh!=None}")
        log.debug(f"ID:{id} licence: {licence_url}")
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
                data=await r.json_()
                log.debug(f"keydb json {data}")
                if  isinstance(data,str): out=data
                elif isinstance(data["keys"][0],str):
                    out=data["keys"][0]
                elif  isinstance(data["keys"][0],object):
                    out=data["keys"][0]["key"]
                await asyncio.get_event_loop().run_in_executor(common.cache_thread,partial( common.cache.set,licence_url,out, expire=constants.KEY_EXPIRY))
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
    async with sessionbuilder.sessionBuilder(backend="aio") as c:
        log.debug(f"ID:{id} using manual key helper")
        try:
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
            return key
        except Exception as E:
            log.traceback(E)
            log.traceback(traceback.format_exc())
            raise E