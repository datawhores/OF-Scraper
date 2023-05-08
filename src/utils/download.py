r"""
                                                             
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/         
"""

import asyncio
import math
import pathlib
import platform
import sys
import shutil
import traceback
import re
import httpx
import os
import contextvars

from rich.console import Console
console=Console()
from tqdm.asyncio import tqdm
import arrow
from  devine.core.manifests import DASH
from devine.core.utils.xml import load_xml
try:
    from win32_setctime import setctime  # pylint: disable=import-error
except ModuleNotFoundError:
    pass
from tenacity import retry,stop_after_attempt,wait_random,retry_if_result

from .auth import add_cookies
from .config import read_config
from .separate import separate_by_id
from ..db import operations
from .paths import set_directory,getmediadir
from ..utils import auth
from ..constants import NUM_TRIES,FILE_FORMAT_DEFAULT,DATE_DEFAULT,TEXTLENGTH_DEFAULT,FILE_SIZE_DEFAULT
from ..utils.profiles import get_current_profile
from .dates import convert_local_time
attempt = contextvars.ContextVar("attempt")

config = read_config()['config']
import src.utils.logger as logger


async def process_dicts(username, model_id, medialist,forced=False):
    if medialist:
        if not forced:
            media_ids = set(operations.get_media_ids(model_id,username))
            medialist = separate_by_id(medialist, media_ids)
            console.print(f"Skipping previously downloaded\nMedia left for download {len(medialist)}")
        else:
            print("forcing all downloads")
        file_size_limit = config.get('file_size_limit') or FILE_SIZE_DEFAULT
        global sem
        sem = asyncio.Semaphore(8)
      
        aws=[]
        photo_count = 0
        video_count = 0
        audio_count=0
        skipped = 0
        total_bytes_downloaded = 0
        data = 0
        desc = 'Progress: ({p_count} photos, {v_count} videos, {a_count} audios,  {skipped} skipped || {sumcount}/{mediacount}||{data})'    

        with tqdm(desc=desc.format(p_count=photo_count, v_count=video_count,a_count=audio_count, skipped=skipped,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped,data=data), total=len(aws), colour='cyan', leave=True) as main_bar:   
            for ele in medialist:
                with set_directory(getmediadir(ele,username,model_id)):

                    aws.append(asyncio.create_task(download(ele,pathlib.Path(".").absolute() ,model_id, username,file_size_limit
                                                            )))
            for coro in asyncio.as_completed(aws):
                    try:
                        media_type, num_bytes_downloaded = await coro
                    except Exception as e:
                        media_type = "skipped"
                        num_bytes_downloaded = 0

                    total_bytes_downloaded += num_bytes_downloaded
                    data = convert_num_bytes(total_bytes_downloaded)
                    if media_type == 'images':
                        photo_count += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count, a_count=audio_count,skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=True)

                    elif media_type == 'videos':
                        video_count += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count, a_count=audio_count ,skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=True)

                    elif media_type == 'audios':
                        audio_count += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count,a_count=audio_count , skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=True)

                    elif media_type == 'skipped':
                        skipped += 1
                        main_bar.set_description(
                            desc.format(
                                p_count=photo_count, v_count=video_count,a_count=audio_count , skipped=skipped, data=data,mediacount=len(medialist), sumcount=video_count+audio_count+photo_count+skipped), refresh=True)

                    main_bar.update()


def retry_required(value):
    return value == ('skipped', 1)

@retry(retry=retry_if_result(retry_required),stop=stop_after_attempt(NUM_TRIES),wait=wait_random(min=20, max=40),reraise=True) 
async def download(ele,path,model_id,username,file_size_limit,id_=None):
    bar=None
    temp=None
    attempt.set(attempt.get(0) + 1)
    log=logger.getlogger()
    try:
        if ele.url:
           return await main_download_helper(ele,path,file_size_limit,username,model_id)
        elif ele.mpd:        
            return 
            return alt_download_helper(path,ele)
        else:
            return "skipped",1
    except Exception as e:
        log.debug(f"[attempt {attempt.get()}/{NUM_TRIES}] exception {e}")   
        log.debug(f"[attempt {attempt.get()}/{NUM_TRIES}] exception {traceback.format_exc()}")   
        return 'skipped', 1
async def main_download_helper(ele,path,file_size_limit,username,model_id):
    url=ele.url
    log=logger.getlogger()
    log.debug(f"Attempting to download media {ele.filename} with {url or 'no url'}")
    async with sem:
            async with httpx.AsyncClient(http2=True, headers = auth.make_headers(auth.read_auth()), follow_redirects=True, timeout=None) as c: 
                auth.add_cookies(c)        
                async with c.stream('GET',url) as r:
                    if not r.is_error:
                        rheaders=r.headers
                        total = int(rheaders['Content-Length'])
                        if file_size_limit and total > int(file_size_limit): 
                                return 'skipped', 1       
                        content_type = rheaders.get("content-type").split('/')[-1]
                        filename=createfilename(ele,username,model_id,content_type)
                        path_to_file = trunicate(pathlib.Path(path,f"{filename}"))                 
                        pathstr=str(path_to_file)
                        temp=trunicate(f"{path_to_file}.part")
                        pathlib.Path(temp).unlink(missing_ok=True)
                        with tqdm(desc=f"{attempt.get()}/{NUM_TRIES} {(pathstr[:50] + '....') if len(pathstr) > 50 else pathstr}" ,total=total, unit_scale=True, unit_divisor=1024, unit='B', leave=False) as bar:
                            with open(temp, 'wb') as f:                           
                                num_bytes_downloaded = r.num_bytes_downloaded
                                async for chunk in r.aiter_bytes(chunk_size=1024):
                                    f.write(chunk)
                                    bar.update(r.num_bytes_downloaded - num_bytes_downloaded)
                                    num_bytes_downloaded = r.num_bytes_downloaded 
                        return finalizer_helper(ele,total,temp,model_id,username)
                    else:
                        r.raise_for_status()


def alt_download_helper(path,ele):
    track=ele.mpd
    if not session:
        session = Session()
    elif not isinstance(session, Session):
        raise TypeError(f"Expected session to be a {Session}, not {session!r}")


    manifest_url, representation, adaptation_set, period = track.url

    track.drm = DASH.get_drm(
        representation.findall("ContentProtection") +
        adaptation_set.findall("ContentProtection")
    )

    manifest = load_xml(session.get(manifest_url).text)
    manifest_url_query = urlparse(manifest_url).query

    manifest_base_url = manifest.findtext("BaseURL")
    if not manifest_base_url or not re.match("^https?://", manifest_base_url, re.IGNORECASE):
        manifest_base_url = urljoin(manifest_url, "./", manifest_base_url)
    period_base_url = urljoin(manifest_base_url, period.findtext("BaseURL"))
    rep_base_url = urljoin(period_base_url, representation.findtext("BaseURL"))

    period_duration = period.get("duration") or manifest.get("mediaPresentationDuration")
    init_data: Optional[bytes] = None

    segment_template = representation.find("SegmentTemplate")
    if segment_template is None:
        segment_template = adaptation_set.find("SegmentTemplate")

    segment_list = representation.find("SegmentList")
    if segment_list is None:
        segment_list = adaptation_set.find("SegmentList")

    if segment_template is None and segment_list is None and rep_base_url:
        # If there's no SegmentTemplate and no SegmentList, then SegmentBase is used or just BaseURL
        # Regardless which of the two is used, we can just directly grab the BaseURL
        # Players would normally calculate segments via Byte-Ranges, but we don't care
        track.url = rep_base_url
        track.descriptor = track.Descriptor.URL
    else:
        segments: list[tuple[str, Optional[str]]] = []
        track_kid: Optional[UUID] = None

        if segment_template is not None:
            segment_template = copy(segment_template)
            start_number = int(segment_template.get("startNumber") or 1)
            segment_timeline = segment_template.find("SegmentTimeline")

            for item in ("initialization", "media"):
                value = segment_template.get(item)
                if not value:
                    continue
                if not re.match("^https?://", value, re.IGNORECASE):
                    if not rep_base_url:
                        raise ValueError("Resolved Segment URL is not absolute, and no Base URL is available.")
                    value = urljoin(rep_base_url, value)
                if not urlparse(value).query and manifest_url_query:
                    value += f"?{manifest_url_query}"
                segment_template.set(item, value)

            init_url = segment_template.get("initialization")
            if init_url:
                res = session.get(DASH.replace_fields(
                    init_url,
                    Bandwidth=representation.get("bandwidth"),
                    RepresentationID=representation.get("id")
                ))
                res.raise_for_status()
                init_data = res.content
                track_kid = track.get_key_id(init_data)

            if segment_timeline is not None:
                seg_time_list = []
                current_time = 0
                for s in segment_timeline.findall("S"):
                    if s.get("t"):
                        current_time = int(s.get("t"))
                    for _ in range(1 + (int(s.get("r") or 0))):
                        seg_time_list.append(current_time)
                        current_time += int(s.get("d"))
                seg_num_list = list(range(start_number, len(seg_time_list) + start_number))

                for t, n in zip(seg_time_list, seg_num_list):
                    segments.append((
                        DASH.replace_fields(
                            segment_template.get("media"),
                            Bandwidth=representation.get("bandwidth"),
                            Number=n,
                            RepresentationID=representation.get("id"),
                            Time=t
                        ), None
                    ))
            else:
                if not period_duration:
                    raise ValueError("Duration of the Period was unable to be determined.")
                period_duration = DASH.pt_to_sec(period_duration)
                segment_duration = float(segment_template.get("duration"))
                segment_timescale = float(segment_template.get("timescale") or 1)
                total_segments = math.ceil(period_duration / (segment_duration / segment_timescale))

                for s in range(start_number, start_number + total_segments):
                    segments.append((
                        DASH.replace_fields(
                            segment_template.get("media"),
                            Bandwidth=representation.get("bandwidth"),
                            Number=s,
                            RepresentationID=representation.get("id"),
                            Time=s
                        ), None
                    ))
        elif segment_list is not None:
            init_data = None
            initialization = segment_list.find("Initialization")
            if initialization is not None:
                source_url = initialization.get("sourceURL")
                if source_url is None:
                    source_url = rep_base_url

                if initialization.get("range"):
                    headers = {"Range": f"bytes={initialization.get('range')}"}
                else:
                    headers = None

                res = session.get(url=source_url, headers=headers)
                res.raise_for_status()
                init_data = res.content
                track_kid = track.get_key_id(init_data)

            segment_urls = segment_list.findall("SegmentURL")
            for segment_url in segment_urls:
                media_url = segment_url.get("media")
                if media_url is None:
                    media_url = rep_base_url

                segments.append((
                    media_url,
                    segment_url.get("mediaRange")
                ))
        else:
            log.error("Could not find a way to get segments from this MPD manifest.")
            log.debug(manifest_url)
            sys.exit(1)

        if not track.drm and isinstance(track, (Video, Audio)):
            try:
                track.drm = [Widevine.from_init_data(init_data)]
            except Widevine.Exceptions.PSSHNotFound:
                # it might not have Widevine DRM, or might not have found the PSSH
                log.warning("No Widevine PSSH was found for this track, is it DRM free?")

        if track.drm:
            # last chance to find the KID
            track_kid = track_kid or track.get_key_id(url=segments[0], session=session)
            # license and grab content keys
            drm = track.drm[0]  # just use the first supported DRM system for now
            if isinstance(drm, Widevine):
                if not license_widevine:
                    raise ValueError("license_widevine func must be supplied to use Widevine DRM")
                license_widevine(drm, track_kid=track_kid)
        else:
            drm = None
def finalizer_helper(ele,total,temp,model_id,username):
    log=logger.getlogger()
    path_to_file=re.sub("\.part$","",str(temp))
    if not pathlib.Path(temp).exists():
        log.debug(f"[attempt {attempt.get()}/{NUM_TRIES}] {temp} was not created") 
        return "skipped",1
    elif abs(total-pathlib.Path(temp).absolute().stat().st_size)>500:
        log.debug(f"[attempt {attempt.get()}/{NUM_TRIES}] {ele.filename} size mixmatch target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}")   
        return "skipped",1 
    else:
        log.debug(f"[attempt {attempt.get()}/{NUM_TRIES}] {ele.filename} size match target: {total} vs actual: {pathlib.Path(temp).absolute().stat().st_size}")   
        log.debug(f"[attempt {attempt.get()}/{NUM_TRIES}] renaming {pathlib.Path(temp).absolute()} -> {path_to_file}")   
        shutil.move(temp,path_to_file)
        if ele.postdate:
            set_time(path_to_file, convert_local_time(ele.postdate))
        if ele.id:
            operations.write_media_table(ele,path_to_file,model_id,username)
        return ele.mediatype,total
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
def createfilename(ele,username,model_id,ext):
    if ele.responsetype =="profile":
        return "{filename}.{ext}".format(ext=ext,filename=ele.filename)
    return (config.get('file_format') or FILE_FORMAT_DEFAULT).format(filename=ele.filename,sitename="Onlyfans",site_name="Onlyfans",post_id=ele.id_,media_id=ele.id,first_letter=username[0],mediatype=ele.mediatype,value=ele.value,text=ele.text_,date=arrow.get(ele.postdate).format(config.get('date') or DATE_DEFAULT),ext=ext,model_username=username,model_id=model_id,responsetype=ele.responsetype) 


def trunicate(path):
    if platform.system() == 'Windows' and len(str(path))>256:
        return _windows_trunicateHelper(path)
    elif platform.system() == 'Linux':
        return _linux_trunicateHelper(path)
    else:
        return path
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



