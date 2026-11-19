import asyncio
import contextlib
import shutil
import struct
import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import ofscraper.commands.scraper.actions.download.utils.keyhelpers as keyhelpers

VIDEO_KID = "a7e61c373e219033c21091fa607bf3b8"
AUDIO_KID = "0123456789abcdef0123456789abcdef"
VIDEO_KEY = "00112233445566778899aabbccddeeff"
AUDIO_KEY = "ffeeddccbbaa99887766554433221100"


def _box(typ, payload=b""):
    return struct.pack(">I4s", 8 + len(payload), typ) + payload


def _encrypted_file(path, kid):
    # the boxes default_kid walks: moov > ... > tenc with the key ID
    tenc = _box(b"tenc", b"\x00\x00\x00\x00" + b"\x00\x00\x01\x08" + bytes.fromhex(kid))
    sinf = _box(b"sinf", _box(b"frma", b"avc1") + _box(b"schi", tenc))
    moov = _box(b"moov", _box(b"mvhd", b"\x00" * 100) + _box(b"trak", _box(b"encv", sinf)))
    path.write_bytes(_box(b"ftyp", b"isom") + moov + _box(b"mdat", b"tenc" * 10))
    return path


def test_default_kid_reads_the_tenc_box(tmp_path):
    assert keyhelpers.default_kid(_encrypted_file(tmp_path / "v.part", VIDEO_KID)) == VIDEO_KID


def test_default_kid_is_none_for_a_clear_file(tmp_path):
    f = tmp_path / "a.mp4"
    f.write_bytes(_box(b"ftyp", b"isom") + _box(b"moov", _box(b"mvhd", b"\x00" * 100)))
    assert keyhelpers.default_kid(f) is None


FFMPEG = shutil.which("ffmpeg")


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg not installed")
def test_default_kid_reads_an_ffmpeg_encrypted_file(tmp_path):
    plain, enc = tmp_path / "plain.mp4", tmp_path / "enc.mp4"
    run = lambda *a: subprocess.run([FFMPEG, "-v", "error", "-y", *a], check=True)
    run("-f", "lavfi", "-i", "testsrc=duration=1:size=64x64:rate=5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(plain))
    run("-i", str(plain), "-c", "copy", "-encryption_scheme", "cenc-aes-ctr",
        "-encryption_key", VIDEO_KEY, "-encryption_kid", VIDEO_KID, str(enc))
    assert keyhelpers.default_kid(enc) == VIDEO_KID


def test_pick_key_matches_the_file_key_id():
    keys = [f"{AUDIO_KID}:{AUDIO_KEY}", f"{VIDEO_KID}:{VIDEO_KEY}"]
    assert keyhelpers.pick_key(keys, VIDEO_KID, 1) == f"{VIDEO_KID}:{VIDEO_KEY}"
    assert keyhelpers.pick_key(keys, None, 1) == keys[0]
    with pytest.raises(Exception, match="no key"):
        keyhelpers.pick_key(keys[:1], VIDEO_KID, 1)


def _license_keys():
    # the audio key comes first, as when a license holds both tracks' keys
    return [
        SimpleNamespace(type="SIGNING", kid=uuid.UUID(int=0), key=b"\x00" * 16),
        SimpleNamespace(type="CONTENT", kid=uuid.UUID(AUDIO_KID), key=bytes.fromhex(AUDIO_KEY)),
        SimpleNamespace(type="CONTENT", kid=uuid.UUID(VIDEO_KID), key=bytes.fromhex(VIDEO_KEY)),
    ]


def test_manual_key_helper_returns_the_key_for_the_file(monkeypatch, tmp_path):
    cdm = Mock()
    cdm.get_keys.return_value = _license_keys()
    monkeypatch.setattr(keyhelpers, "PSSH", Mock())
    monkeypatch.setattr(keyhelpers, "Device", Mock())
    monkeypatch.setattr(keyhelpers.Cdm, "from_device", Mock(return_value=cdm))
    (tmp_path / "k").write_bytes(b"k")
    monkeypatch.setattr(keyhelpers.settings, "get_settings",
                        lambda: SimpleNamespace(private_key=tmp_path / "k", client_id=tmp_path / "k"))
    monkeypatch.setattr(keyhelpers, "get_cmd_download_req_retries", lambda: 1)
    monkeypatch.setattr(keyhelpers, "log", Mock())

    response = SimpleNamespace(read_=AsyncMock(return_value=b"license"))

    @contextlib.asynccontextmanager
    async def requests_async(**kw):
        yield response

    @contextlib.asynccontextmanager
    async def session():
        yield SimpleNamespace(requests_async=requests_async)

    monkeypatch.setattr(keyhelpers.manager, "Manager",
                        SimpleNamespace(session=SimpleNamespace(get_cdm_session_manual=session)))

    key = asyncio.run(keyhelpers.key_helper_manual(None, "pssh", "https://lic", 1, VIDEO_KID))
    assert key == f"{VIDEO_KID}:{VIDEO_KEY}"


def test_cdrm_key_helper_returns_the_key_for_the_file(monkeypatch):
    monkeypatch.setattr(keyhelpers.auth_requests, "make_headers", lambda: {})
    monkeypatch.setattr(keyhelpers.auth_requests, "get_cookies_str", lambda: "")
    monkeypatch.setattr(keyhelpers.auth_requests, "create_sign", lambda url, headers: None)
    monkeypatch.setattr(keyhelpers, "get_cmd_download_req_retries", lambda: 1)
    monkeypatch.setattr(keyhelpers, "log", Mock())
    message = f"{AUDIO_KID}:{AUDIO_KEY}\n{VIDEO_KID}:{VIDEO_KEY}"

    @contextlib.asynccontextmanager
    async def requests_async(**kw):
        yield SimpleNamespace(json_=AsyncMock(return_value={"message": message}))

    c = SimpleNamespace(requests_async=requests_async)
    key = asyncio.run(keyhelpers.key_helper_cdrm(c, "pssh", "https://lic", 1, VIDEO_KID))
    assert key == f"{VIDEO_KID}:{VIDEO_KEY}"


def test_saved_key_for_another_track_is_not_used(monkeypatch, tmp_path):
    # an older version saved the audio key under the license URL alone;
    # the video must get its own key, and decrypt with it
    part = _encrypted_file(tmp_path / "tempvid.part", VIDEO_KID)
    saved = {"lic": f"{AUDIO_KID}:{AUDIO_KEY}"}
    monkeypatch.setattr(keyhelpers.settings, "get_settings", lambda: SimpleNamespace(key_mode="manual"))
    real_getattr = keyhelpers.of_env.getattr
    monkeypatch.setattr(keyhelpers.of_env, "getattr", lambda key, default=None:
                        True if key == "USE_WIV_CACHE_KEY" else real_getattr(key, default))
    monkeypatch.setattr(keyhelpers.cache, "get", lambda name: saved.get(name))
    monkeypatch.setattr(keyhelpers.cache, "set", lambda name, value, **kw: saved.__setitem__(name, value))
    helper = AsyncMock(return_value=f"{VIDEO_KID}:{VIDEO_KEY}")
    monkeypatch.setattr(keyhelpers, "key_helper_manual", helper)
    monkeypatch.setattr(keyhelpers, "get_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(keyhelpers, "strip_pssh", Mock(return_value=0))
    monkeypatch.setattr(keyhelpers.stop, "check", lambda: None)
    used = []

    async def decrypt(cmd, **kwargs):
        used.append(cmd[cmd.index("-decryption_key") + 1])
        (tmp_path / "tempvid.mp4").write_bytes(b"clear")
        return SimpleNamespace()

    monkeypatch.setattr(keyhelpers, "async_run", decrypt)
    item = {"path": part, "ext": "mp4", "pssh": "pssh"}

    async def go():
        with ThreadPoolExecutor(1) as pool:
            monkeypatch.setattr(keyhelpers.common_globals, "thread", pool, raising=False)
            await keyhelpers.un_encrypt(item, None, SimpleNamespace(id=1, post_id=1, license="lic"), input_=Mock())

    asyncio.run(go())
    assert used == [VIDEO_KEY]
    assert helper.await_args.args[-1] == VIDEO_KID
    assert saved[f"lic#{VIDEO_KID}"] == f"{VIDEO_KID}:{VIDEO_KEY}"
