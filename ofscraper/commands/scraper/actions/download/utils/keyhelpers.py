import asyncio
import pathlib
import re
import struct
import traceback
from functools import partial
from urllib.parse import urlsplit

from pywidevine.cdm import Cdm
from pywidevine.device import Device
from pywidevine.pssh import PSSH

from ofscraper.commands.scraper.actions.download import stop
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
from ofscraper.utils.system.network import CDRM_DEPRECATED
import ofscraper.managers.manager as manager

log = None


def setLog(input_):
    global log
    log = input_


def missing_cdm_keys():
    """What manual key mode lacks to decrypt DRM videos, or None.

    A blank path becomes Path("") == "." and fails with "Is a directory"
    only after the whole video has been downloaded.
    """
    s = settings.get_settings()
    if s.key_mode != "manual":
        return None
    problems = []
    for name, value in (("client-id", s.client_id), ("private-key", s.private_key)):
        value = str(value or "").strip()
        if not value:
            problems.append(f"{name} is not set")
        elif not pathlib.Path(value).is_file():
            problems.append(f"{name} file not found: {value}")
    return "; ".join(problems) or None


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
                    # a 64-bit size cut off by the end of the file
                    if pos + 16 > end:
                        return
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


def default_kid(path):
    """
    The ID of the key an encrypted file needs (its tenc box), as lowercase
    hex, or None if the file doesn't record one.
    """
    with open(path, "rb") as f:
        while header := f.read(8):
            if len(header) < 8:
                return None
            size, typ = struct.unpack(">I4s", header)
            skip = size - 8
            if size == 1:
                # a 64-bit size cut off by the end of the file
                if len(large := f.read(8)) < 8:
                    return None
                skip = struct.unpack(">Q", large)[0] - 16
            elif size == 0:
                return None
            if typ != b"moov":
                if skip < 0:
                    return None
                f.seek(skip, 1)
                continue
            moov = f.read(skip)
            pos = moov.find(b"tenc")
            # tenc: size, type, version and flags, 4 bytes of settings, the
            # 16-byte ID, then an optional constant IV
            while pos >= 4:
                if (
                    struct.unpack(">I", moov[pos - 4 : pos])[0] >= 32
                    and len(moov) >= pos + 28
                ):
                    return moov[pos + 12 : pos + 28].hex()
                pos = moov.find(b"tenc", pos + 1)
            return None
    return None


def key_id(key):
    return key.strip().split(":")[0].replace("-", "").lower()


def pick_key(keys, kid, id):
    """
    The "kid:key" pair whose ID is kid, or the first one when the file's ID
    is unknown. A license can hold several keys (e.g. audio and video), and
    decrypting with another track's key gives scrambled video (#551).
    """
    keys = [k.strip() for k in keys if k and k.strip()]
    if not keys or not kid:
        return keys[0] if keys else None
    for key in keys:
        if key_id(key) == kid:
            return key
    raise Exception(f"ID:{id} license has no key for this file's key ID {kid}")


async def un_encrypt(item, c, ele, input_=None):
    try:
        setLog(input_ or common_globals.log)
        key = None
        keymode = settings.get_settings().key_mode
        kid = default_kid(item["path"])
        log.debug(f"{get_medialog(ele)} file key ID: {kid}")
        # Saved under the key ID too, so tracks that need different keys
        # don't share one entry, and entries saved by older versions,
        # which may hold another track's key, aren't used
        cache_name = f"{ele.license}#{kid}" if kid else ele.license
        past_key = (
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread, partial(cache.get, cache_name)
            )
            if of_env.getattr("USE_WIV_CACHE_KEY")
            else None
        )
        if past_key and kid and key_id(past_key) != kid:
            log.debug(f"{get_medialog(ele)} ignoring saved key for another key ID")
            past_key = None
        if past_key:
            key = past_key
            log.debug(f"{get_medialog(ele)} got key from cache")
        elif keymode == "manual":
            key = await key_helper_manual(c, item["pssh"], ele.license, ele.id, kid)
        elif keymode == "cdrm":
            key = await key_helper_cdrm(c, item["pssh"], ele.license, ele.id, kid)
        if not key:
            raise Exception(f"{get_medialog(ele)} Could not get key")
        key = key.strip()
        log.debug(f"{get_medialog(ele)} key ready")
        newpath = pathlib.Path(
            re.sub(
                r"\.part$", f".{item['ext']}", str(item["path"]), flags=re.IGNORECASE
            )
        )
        ffmpeg_key = get_ffmpeg_key(key)
        log.debug(f"{get_medialog(ele)} got ffmpeg key")
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
                    cache.set, cache_name, None, expire=of_env.getattr("KEY_EXPIRY")
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
            stop.check()
            # Keep encrypted Part files until all tracks have been merged.
            if pathlib.Path(item["path"]).suffix != ".part":
                pathlib.Path(item["path"]).unlink(missing_ok=True)
            item["path"] = newpath
            await asyncio.get_event_loop().run_in_executor(
                common_globals.thread,
                partial(
                    cache.set, cache_name, key, expire=of_env.getattr("KEY_EXPIRY")
                ),
            )
            return item
    except Exception as E:
        raise E


def get_ffmpeg_key(key):
    return key.split(":")[1]


def cdrm_retired(url):
    """True when url points at cdrm-project.com, which no longer works.
    It isn't sent the headers and cookies; a self-hosted server set in
    OFSC_CDRM_URL still is (#677)."""
    host = (urlsplit(str(url or "")).hostname or "").lower().rstrip(".")
    return host == "cdrm-project.com" or host.endswith(".cdrm-project.com")


def cdrm_unavailable():
    """True when key mode cdrm has no server to ask: OFSC_CDRM_URL is the
    retired cdrm-project.com, the default. Its DRM videos can't get a key,
    so they're skipped before download (#681)."""
    if settings.get_settings().key_mode != "cdrm":
        return False
    return cdrm_retired(of_env.getattr("CDRM"))


_cdrm_retired_logged = False


async def key_helper_cdrm(c, pssh, licence_url, id, kid=None):
    global _cdrm_retired_logged
    key = None
    log.debug(f"ID:{id} using cdrm auto key helper")
    if cdrm_retired(of_env.getattr("CDRM")):
        if not _cdrm_retired_logged:
            _cdrm_retired_logged = True
            log.error(f"Nothing was sent to cdrm-project.com. {CDRM_DEPRECATED}")
        log.debug(f"ID:{id} no key: key mode cdrm, cdrm-project.com not contacted")
        return None
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
            # the reply holds the content keys: log only its fields
            log.debug(
                f"ID:{id} cdrm reply fields: "
                f"{list(data) if isinstance(data, dict) else type(data).__name__}"
            )
            # one "kid:key" pair per line when the license has several
            key = pick_key(str(data["message"]).split(), kid, id)
        return key
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E


async def key_helper_manual(c, pssh, licence_url, id, kid=None):
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
        key = pick_key(
            [
                "{}:{}".format(k.kid.hex, k.key.hex())
                for k in keys
                if k.type == "CONTENT"
            ],
            kid,
            id,
        )
        return key
    except Exception as E:
        log.traceback_(E)
        log.traceback_(traceback.format_exc())
        raise E
