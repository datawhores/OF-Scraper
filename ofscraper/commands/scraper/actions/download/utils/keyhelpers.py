import asyncio
import pathlib
import re
import struct
import traceback
from functools import partial

from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.utils.retries import (
    get_cmd_download_req_retries,
)
from ofscraper.commands.scraper.actions.utils.log import get_medialog
from ofscraper.utils.system.subprocess import async_run
from ofscraper.utils.system.ffmpeg import get_ffmpeg
import ofscraper.managers.manager as manager

log = None


def setLog(input_):
    global log
    log = input_


def strip_pssh(path):
    """
    Turn pssh boxes in a decrypted file into same-sized 'free' boxes.

    ffmpeg 8+ copies the source's pssh (DRM init data) into the decrypted
    output; 7.x dropped it. The media is identical either way, but a clear
    file still carrying pssh can look protected to some players. Renaming
    keeps every offset valid, so nothing else in the file changes.
    Returns the number of boxes changed.
    """
    changed = 0
    with open(path, "r+b") as f:
        f.seek(0, 2)
        file_end = f.tell()

        def walk(start, end, depth):
            nonlocal changed
            pos = start
            while pos + 8 <= end:
                f.seek(pos)
                size, typ = struct.unpack(">I4s", f.read(8))
                header = 8
                if size == 1:
                    size = struct.unpack(">Q", f.read(8))[0]
                    header = 16
                elif size == 0:
                    size = end - pos
                if size < header or pos + size > end:
                    return
                if typ == b"pssh":
                    f.seek(pos + 4)
                    f.write(b"free")
                    changed += 1
                elif depth == 0 and typ in (b"moov", b"moof"):
                    walk(pos + header, pos + size, depth + 1)
                pos += size

        walk(0, file_end, 0)
    return changed


async def un_encrypt(item, c, ele, input_=None):
    try:
        setLog(input_ or common_globals.log)
        key = None
        keymode = settings.get_settings().key_mode
        past_key = (
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread, partial(cache.get, ele.license)
            )
            if of_env.getattr("USE_WIV_CACHE_KEY")
            else None
        )
        if past_key:
            key = past_key
            log.debug(f"{get_medialog(ele)} got key rom cache: {key}")
        elif keymode == "manual":
            key = await key_helper_manual(c, item["pssh"], ele.license, ele.id)
        elif keymode == "cdrm":
            key = await key_helper_cdrm(c, item["pssh"], ele.license, ele.id)
        if not key:
            raise Exception(f"{get_medialog(ele)} Could not get key")
        key = key.strip()
        log.debug(f"{get_medialog(ele)} retrive new key: {key}")
        newpath = pathlib.Path(
            re.sub(
                r"\.part$", f".{item['ext']}", str(item["path"]), flags=re.IGNORECASE
            )
        )
        ffmpeg_key = get_ffmpeg_key(key)
        log.debug(f"{get_medialog(ele)} got ffmpeg key {ffmpeg_key}")
        log.debug(
            f"{get_medialog(ele)}  renaming {pathlib.Path(item['path']).absolute()} -> {newpath}"
        )
        r = await async_run(
            [
                get_ffmpeg(),
                "-decryption_key",
                ffmpeg_key,
                "-i",
                str(item["path"]),
                "-codec",
                "copy",
                str(newpath),
                "-y",
            ],
            level=of_env.getattr("FFMPEG_SUBPROCESS_LEVEL"),
            name="ffmpeg",
        )
        if not pathlib.Path(newpath).exists():
            log.debug(f"{get_medialog(ele)} ffmpeg {r.stderr.decode()}")
            log.debug(f"{get_medialog(ele)} ffmpeg {r.stdout.decode()}")
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread,
                partial(
                    cache.set, ele.license, None, expire=of_env.getattr("KEY_EXPIRY")
                ),
            )
            raise Exception(f"{get_medialog(ele)} ffmpeg decryption failed")
        else:
            log.debug(f"{get_medialog(ele)} ffmpeg  decrypt success {newpath}")
            try:
                if n := strip_pssh(newpath):
                    log.debug(f"{get_medialog(ele)} removed {n} pssh box(es) from {newpath}")
            except OSError as E:
                log.debug(f"{get_medialog(ele)} could not strip pssh from {newpath}: {E}")
            pathlib.Path(item["path"]).unlink(missing_ok=True)
            item["path"] = newpath
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread,
                partial(
                    cache.set, ele.license, key, expire=of_env.getattr("KEY_EXPIRY")
                ),
            )
            return item
    except Exception as E:
        raise E


def get_ffmpeg_key(key):
    return key.split(":")[1]


async def key_helper_cdrm(c, pssh, licence_url, id):
    key = None
    log.debug(f"ID:{id} using cdrm auto key helper")
    try:
        log.debug(f"ID:{id} pssh: {pssh is not None}")
        log.debug(f"ID:{id} licence: {licence_url}")
        headers = auth_requests.make_headers()
        headers["cookie"] = auth_requests.get_cookies_str()
        auth_requests.create_sign(licence_url, headers)
        json_data = {
            "licurl": licence_url,
            # cdrm-project parses this field with ast.literal_eval, which
            # needs a python dict literal rather than JSON
            "headers": repr(dict(headers)),
            "pssh": pssh,
        }
        async with c.requests_async(
            url=of_env.getattr("CDRM"),
            method="post",
            json=json_data,
            retries=get_cmd_download_req_retries(),
            wait_min=of_env.getattr("OF_MIN_WAIT_API"),
            wait_max=of_env.getattr("OF_MAX_WAIT_API"),
            total_timeout=of_env.getattr("CDM_TIMEOUT"),
            skip_expection_check=True,
        ) as r:
            data = await r.json_()
            log.debug(f"cdrm json {data}")
            key = data["message"]
        return key
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


async def key_helper_manual(c, pssh, licence_url, id):
    key = None
    log.debug(f"ID:{id} using manual key helper")
    try:
        log.debug(f"ID:{id} pssh: {pssh is not None}")
        log.debug(f"ID:{id} licence: {licence_url}")

        # prepare pssh
        pssh_obj = PSSH(pssh)

        # load device
        private_key = pathlib.Path(settings.get_settings().private_key).read_bytes()
        client_id = pathlib.Path(settings.get_settings().client_id).read_bytes()
        device = Device(
            security_level=3,
            private_key=private_key,
            client_id=client_id,
            type_="ANDROID",
            flags=None,
        )

        # load cdm
        cdm = Cdm.from_device(device)

        # open cdm session
        session_id = cdm.open()

        keys = None
        challenge = cdm.get_license_challenge(session_id, pssh_obj)
        async with manager.Manager.session.get_cdm_session_manual() as c:
            async with c.requests_async(
                url=licence_url,
                method="post",
                data=challenge,
                retries=get_cmd_download_req_retries(),
                wait_min=of_env.getattr("OF_MIN_WAIT_API"),
                wait_max=of_env.getattr("OF_MAX_WAIT_API"),
                total_timeout=of_env.getattr("CDM_TIMEOUT"),
            ) as r:
                data = await r.read_()
                cdm.parse_license(session_id, (data))
                keys = cdm.get_keys(session_id)
                cdm.close(session_id)
            keyobject = list(filter(lambda x: x.type == "CONTENT", keys))[0]

        key = "{}:{}".format(keyobject.kid.hex, keyobject.key.hex())
        return key
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
