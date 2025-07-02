import asyncio
import json
import pathlib
import re
import traceback
from functools import partial

from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.utils.auth.request as auth_requests
import ofscraper.utils.cache as cache
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.utils.retries import (
    get_cmd_download_req_retries,
)
from ofscraper.commands.scraper.actions.utils.log import get_medialog
from ofscraper.utils.system.subprocess import run
from ofscraper.commands.scraper.actions.download.utils.ffmpeg import get_ffmpeg
import ofscraper.main.manager as manager
import ofscraper.utils.of_env.of_env as env


log = None


def setLog(input_):
    global log
    log = input_


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
            re.sub("\.part$", f".{item['ext']}", str(item["path"]), flags=re.IGNORECASE)
        )
        ffmpeg_key = get_ffmpeg_key(key)
        log.debug(f"{get_medialog(ele)} got ffmpeg key {ffmpeg_key}")
        log.debug(
            f"{get_medialog(ele)}  renaming {pathlib.Path(item['path']).absolute()} -> {newpath}"
        )
        r = run(
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
            quiet=not env.getattr("FFMPEG_OUTPUT_SUBPROCCESS"),
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
            "headers": json.dumps(headers),
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
        async with manager.Manager.get_cdm_session_manual() as c:
            async with c.requests_async(
                url=licence_url,
                method="post",
                data=challenge,
                retries=get_cmd_download_req_retries(),
                wait_min=of_env.getattr("OF_MIN_WAIT_API"),
                wait_max=of_env.getattr("OF_MAX_WAIT_API"),
                total_timeout=of_env.getattr("CDM_TIMEOUT"),
            ) as r:
                cdm.parse_license(session_id, (await r.read_()))
                keys = cdm.get_keys(session_id)
                cdm.close(session_id)
            keyobject = list(filter(lambda x: x.type == "CONTENT", keys))[0]

        key = "{}:{}".format(keyobject.kid.hex, keyobject.key.hex())
        return key
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
