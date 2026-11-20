"""Content keys never reach the log.

The debug log is what people attach to bug reports, and a content key
decrypts the video for anyone who has it. un_encrypt logged the key it got
(from the cache or a key helper) and the key handed to ffmpeg, and the cdrm
helper logged its whole reply, keys included.
"""

import asyncio
import contextlib
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import ofscraper.commands.scraper.actions.download.utils.keyhelpers as keyhelpers

KID = "a7e61c373e219033c21091fa607bf3b8"
KEY = "00112233445566778899aabbccddeeff"


def _logged(log):
    return " ".join(str(a) for call in log.mock_calls for a in call.args)


@pytest.mark.parametrize("cached", [False, True])
def test_un_encrypt_logs_no_key(monkeypatch, tmp_path, cached):
    part = tmp_path / "tempvid.part"
    part.write_bytes(b"encrypted")
    saved = {"lic": f"{KID}:{KEY}"} if cached else {}
    monkeypatch.setattr(keyhelpers.settings, "get_settings", lambda: SimpleNamespace(key_mode="manual"))
    real_getattr = keyhelpers.of_env.getattr
    monkeypatch.setattr(keyhelpers.of_env, "getattr", lambda key, default=None:
                        True if key == "USE_WIV_CACHE_KEY" else real_getattr(key, default))
    monkeypatch.setattr(keyhelpers.cache, "get", lambda name: saved.get(name))
    monkeypatch.setattr(keyhelpers.cache, "set", lambda name, value, **kw: saved.__setitem__(name, value))
    monkeypatch.setattr(keyhelpers, "key_helper_manual", AsyncMock(return_value=f"{KID}:{KEY}"))
    monkeypatch.setattr(keyhelpers, "get_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(keyhelpers, "strip_pssh", Mock(return_value=0))
    monkeypatch.setattr(keyhelpers.stop, "check", lambda: None)

    async def decrypt(cmd, **kwargs):
        (tmp_path / "tempvid.mp4").write_bytes(b"clear")
        return SimpleNamespace()

    monkeypatch.setattr(keyhelpers, "async_run", decrypt)
    log = Mock()

    async def go():
        with ThreadPoolExecutor(1) as pool:
            monkeypatch.setattr(keyhelpers.common_globals, "thread", pool, raising=False)
            await keyhelpers.un_encrypt(
                {"path": part, "ext": "mp4", "pssh": "pssh"},
                None,
                SimpleNamespace(id=1, post_id=1, license="lic"),
                input_=log,
            )

    asyncio.run(go())
    assert log.debug.called
    assert KEY not in _logged(log)


def test_cdrm_reply_is_not_logged(monkeypatch):
    monkeypatch.setattr(keyhelpers.auth_requests, "make_headers", lambda: {})
    monkeypatch.setattr(keyhelpers.auth_requests, "get_cookies_str", lambda: "")
    monkeypatch.setattr(keyhelpers.auth_requests, "create_sign", lambda url, headers: None)
    monkeypatch.setattr(keyhelpers, "get_cmd_download_req_retries", lambda: 1)
    log = Mock()
    monkeypatch.setattr(keyhelpers, "log", log)

    @contextlib.asynccontextmanager
    async def requests_async(**kw):
        yield SimpleNamespace(json_=AsyncMock(return_value={"message": f"{KID}:{KEY}"}))

    c = SimpleNamespace(requests_async=requests_async)
    assert asyncio.run(keyhelpers.key_helper_cdrm(c, "pssh", "https://lic", 1)) == f"{KID}:{KEY}"

    logged = _logged(log)
    assert "message" in logged  # the reply's fields are still logged
    assert KEY not in logged
