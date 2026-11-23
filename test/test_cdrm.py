import ast
import asyncio
import contextlib
import logging
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ofscraper.commands.scraper.actions.download.utils.keyhelpers as keyhelpers


class _Response:
    ok = True
    status = 200
    headers = {}

    def text_(self):
        return ""

    async def json_(self):
        return {"message": "kid:key"}


class _Session:
    def __init__(self):
        self.calls = []

    @contextlib.asynccontextmanager
    async def requests_async(self, **kw):
        self.calls.append(kw)
        yield _Response()

    @contextlib.contextmanager
    def requests(self, **kw):
        self.calls.append(kw)
        yield _Response()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


OWN_SERVER = "https://cdrm.example.test/api/decrypt"


def use_cdrm_url(monkeypatch, url=OWN_SERVER):
    """Point key mode cdrm at url, as OFSC_CDRM_URL does."""
    real_getattr = keyhelpers.of_env.getattr
    monkeypatch.setattr(
        keyhelpers.of_env,
        "getattr",
        lambda key, default=None: url if key == "CDRM" else real_getattr(key, default),
    )


def test_default_cdrm_address_is_not_contacted(monkeypatch, tmp_path):
    # cdrm-project.com no longer works: the headers and cookies aren't sent
    # to it, and the video fails like any other missing key (#677)
    monkeypatch.delenv("OFSC_CDRM_URL", raising=False)
    monkeypatch.setattr(keyhelpers, "_cdrm_retired_logged", False, raising=False)
    make_headers = Mock(return_value={})
    monkeypatch.setattr(keyhelpers.auth_requests, "make_headers", make_headers)
    monkeypatch.setattr(keyhelpers.auth_requests, "get_cookies_str", Mock(return_value="a=1"))
    monkeypatch.setattr(keyhelpers.auth_requests, "create_sign", Mock())
    monkeypatch.setattr(keyhelpers, "get_cmd_download_req_retries", lambda: 1)
    monkeypatch.setattr(keyhelpers.settings, "get_settings", lambda: SimpleNamespace(key_mode="cdrm"))
    monkeypatch.setattr(keyhelpers.cache, "get", lambda name: None)
    log = Mock()
    monkeypatch.setattr(keyhelpers, "log", log)
    session = _Session()
    part = tmp_path / "tempvid.part"
    part.write_bytes(b"")

    async def go():
        with ThreadPoolExecutor(1) as pool:
            monkeypatch.setattr(keyhelpers.common_globals, "thread", pool, raising=False)
            assert await keyhelpers.key_helper_cdrm(session, "pssh", "https://lic", 1) is None
            assert await keyhelpers.key_helper_cdrm(session, "pssh", "https://lic", 2) is None
            with pytest.raises(Exception, match="Could not get key"):
                await keyhelpers.un_encrypt(
                    {"path": part, "ext": "mp4", "pssh": "pssh"},
                    session,
                    SimpleNamespace(id=3, post_id=3, license="lic"),
                    input_=log,
                )

    asyncio.run(go())
    assert session.calls == []
    make_headers.assert_not_called()
    keyhelpers.auth_requests.get_cookies_str.assert_not_called()
    # told once per run how to fix it, not once per video
    assert log.error.call_count == 1
    assert "key mode manual" in log.error.call_args.args[0]


def test_own_cdrm_server_is_still_used(monkeypatch):
    # a server set in OFSC_CDRM_URL is the user's choice: it is still asked
    use_cdrm_url(monkeypatch)
    monkeypatch.setattr(keyhelpers.auth_requests, "make_headers", lambda: {})
    monkeypatch.setattr(keyhelpers.auth_requests, "get_cookies_str", lambda: "a=1")
    monkeypatch.setattr(keyhelpers.auth_requests, "create_sign", lambda url, headers: None)
    monkeypatch.setattr(keyhelpers, "get_cmd_download_req_retries", lambda: 1)
    monkeypatch.setattr(keyhelpers, "log", logging.getLogger("test"))
    session = _Session()

    key = asyncio.run(keyhelpers.key_helper_cdrm(session, "pssh", "https://lic", 1))

    assert key == "kid:key"
    assert [call["url"] for call in session.calls] == [OWN_SERVER]


def test_cdrm_headers_are_a_python_literal(monkeypatch):
    use_cdrm_url(monkeypatch)
    monkeypatch.setattr(
        keyhelpers.auth_requests,
        "make_headers",
        lambda: {"user-agent": "ua", "x-bc": "abc"},
    )
    monkeypatch.setattr(keyhelpers.auth_requests, "get_cookies_str", lambda: "a=1; b=2")
    monkeypatch.setattr(
        keyhelpers.auth_requests,
        "create_sign",
        lambda url, headers: headers.update({"sign": "s"}),
    )
    monkeypatch.setattr(keyhelpers, "get_cmd_download_req_retries", lambda: 1)
    monkeypatch.setattr(keyhelpers, "log", logging.getLogger("test"))
    session = _Session()

    key = asyncio.run(keyhelpers.key_helper_cdrm(session, "pssh", "https://lic", 1))

    assert key == "kid:key"
    sent = session.calls[0]["json"]["headers"]
    # cdrm-project reads this field with ast.literal_eval (#43)
    assert ast.literal_eval(sent) == {
        "user-agent": "ua",
        "x-bc": "abc",
        "cookie": "a=1; b=2",
        "sign": "s",
    }


class _Started(Exception):
    pass


def _run_drm_item(monkeypatch):
    """Run one DRM item through the protected media downloader, in key mode
    cdrm. Starting a transfer raises _Started."""
    import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
    import ofscraper.commands.scraper.actions.download.managers.alt_download as alt_download

    monkeypatch.setattr(
        keyhelpers.settings,
        "get_settings",
        lambda: SimpleNamespace(key_mode="cdrm", client_id=None, private_key=None),
    )
    monkeypatch.setattr(alt_download.stop, "started", lambda ele: None)
    monkeypatch.setattr(alt_download.common_logs, "get_medialog", lambda ele: "media")
    monkeypatch.setattr(
        alt_download.host_allowlist, "ensure_allowed_download_url", lambda *a: None
    )
    placeholders = Mock(side_effect=_Started)
    monkeypatch.setattr(alt_download.placeholder, "Placeholders", placeholders)
    log = Mock()
    manager = SimpleNamespace(ctx=SimpleNamespace(log=log), _force_download=Mock())
    ele = SimpleNamespace(mpd="https://cdn/x.mpd", license="https://lic")
    session = _Session()

    result = asyncio.run(
        alt_download.AltDownloadManager._alt_download_item(
            manager, session, ele, "a creator", 1
        )
    )
    return result, ele, log, placeholders, session


def test_default_cdrm_address_skips_drm_before_download(monkeypatch):
    # nothing can give the key, so the video isn't downloaded first and
    # left as .part files on every run (#681)
    monkeypatch.delenv("OFSC_CDRM_URL", raising=False)

    result, ele, log, placeholders, session = _run_drm_item(monkeypatch)

    assert result == ("forced_skipped", 0)  # counted as skipped, not failed
    placeholders.assert_not_called()
    assert session.calls == []
    assert ele.download_reason == "key mode cdrm has no server"
    log.info.assert_called_once()
    assert "DRM video skipped: key mode cdrm has no server" in log.info.call_args.args[0]


def test_own_cdrm_server_still_downloads(monkeypatch):
    use_cdrm_url(monkeypatch)
    with pytest.raises(_Started):
        _run_drm_item(monkeypatch)


def test_cdrm_unavailable_only_for_the_retired_default(monkeypatch):
    mode = SimpleNamespace(key_mode="cdrm")
    monkeypatch.setattr(keyhelpers.settings, "get_settings", lambda: mode)
    monkeypatch.delenv("OFSC_CDRM_URL", raising=False)
    assert keyhelpers.cdrm_unavailable() is True
    mode.key_mode = "manual"
    assert keyhelpers.cdrm_unavailable() is False
    mode.key_mode = "cdrm"
    use_cdrm_url(monkeypatch)
    assert keyhelpers.cdrm_unavailable() is False


@pytest.mark.parametrize(
    "url, retired",
    [
        ("https://cdrm-project.com/api/decrypt", True),
        ("https://CDRM-Project.com:443/api/decrypt", True),
        ("https://cdrm-project.com./api/decrypt", True),
        ("https://x.cdrm-project.com/api/decrypt", True),
        ("https://evilcdrm-project.com/api/decrypt", False),
        ("https://cdrm-project.com.example.test/api/decrypt", False),
        ("https://cdrm.example.test/api/decrypt", False),
        (None, False),
        ("", False),
    ],
)
def test_cdrm_retired_matches_only_the_retired_host(url, retired):
    assert keyhelpers.cdrm_retired(url) is retired
