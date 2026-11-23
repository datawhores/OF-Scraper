"""The OnlyFans login goes only to allowed media hosts.

The download session sends the session cookies and the signed login headers
with every file request, and DRM segments add the cookies to their Cookie
header. Both went to whatever host the API named. Now a plain file on a host
outside the list downloads without the login, and a DRM video on one fails
before any request. The downloads run through the real download session
against a local server, which is outside the built-in list.
"""

import asyncio
import contextvars
import logging
from types import SimpleNamespace

import pytest
from aiohttp import web
from tenacity import stop_after_attempt, wait_none

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.commands.scraper.actions.download.managers.main_download as md
import ofscraper.commands.scraper.actions.download.utils.retries as retries
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.managers.sessionmanager.sessionmanager as sm
import ofscraper.sites as sites
import ofscraper.utils.host_allowlist as host_allowlist
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager.ofsession import download_session

BODY = b"x" * 1000
SESSION = "made-up-session-value"


async def _noop(*args, **kwargs):
    return None


class _Log:
    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(
            auto_resume=True,
            download_limit=0,
            command="download",
            ssl_verify="false",
            cached_disabled=True,
            anon=False,
            site="onlyfans",
        ),
    )
    monkeypatch.setattr(common_globals, "log", _Log(), raising=False)
    for name in ("attempt", "attempt2"):
        monkeypatch.setattr(
            common_globals, name, contextvars.ContextVar(name, default=0), raising=False
        )
    for module in (md, ad):
        monkeypatch.setattr(
            module,
            "download_retry",
            lambda: retries.download_retry(stop=stop_after_attempt(1), wait=wait_none()),
        )
        monkeypatch.setattr(module, "get_download_retries", lambda: 1)
        monkeypatch.setattr(module, "send_chunk_msg", lambda *a, **k: None)
    monkeypatch.setattr(md.common_logs, "path_to_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(md.common_logs, "get_medialog", lambda ele: "")
    monkeypatch.setattr(dm, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad, "temp_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(ad, "path_to_file_logger", lambda *a, **k: None)
    monkeypatch.setattr(ad, "get_alt_params", lambda ele: {})
    monkeypatch.setattr(ad, "get_medialog", lambda ele: "")
    monkeypatch.setattr(ad.keyhelpers, "missing_cdm_keys", lambda: None)
    monkeypatch.setattr(ad.keyhelpers, "cdrm_unavailable", lambda: False)
    # the login the session and the DRM downloader add (made-up values)
    monkeypatch.setattr(sm.auth_requests, "add_cookies", lambda: {"sess": SESSION})
    monkeypatch.setattr(sm.auth_requests, "make_headers", lambda: {"user-id": "1", "x-bc": "made-up"})
    monkeypatch.setattr(sm.auth_requests, "create_sign", lambda url, headers: headers.update(sign="made-up"))
    monkeypatch.setattr(ad.auth_requests, "get_cookies_str", lambda: f"auth_id=1;sess={SESSION};")
    host_allowlist._warned.clear()


def _extra_hosts(monkeypatch, value):
    real = of_env.getattr

    def getattr_(key, default=None):
        if key == "MEDIA_HOST_SUFFIXES":
            return value
        return real(key, default)

    monkeypatch.setattr(of_env, "getattr", getattr_)


def _manager(cls):
    mgr = cls()
    mgr._check_forced_skip = _noop
    mgr._add_download_job_task = _noop
    mgr._remove_download_job_task = _noop
    mgr._total_change_helper = _noop
    mgr._downloadspace = lambda: None
    mgr._get_data = _noop
    mgr._set_data = _noop
    return mgr


def _placeholder(tmp_path, part):
    class _Placeholder:
        def __init__(self, *a):
            pass

        async def init(self):
            return SimpleNamespace(
                tempfilepath=part, trunicated_filepath=tmp_path / "f.mp4"
            )

    return _Placeholder


def _run(download):
    """Serve BODY; return (result or exception, the requests' headers)."""
    seen = []

    async def handler(request):
        seen.append(dict(request.headers))
        return web.Response(body=BODY, content_type="video/mp4")

    async def go():
        app = web.Application()
        app.router.add_get("/{name}", handler)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        base = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        try:
            async with download_session(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                try:
                    return await download(c, base), seen
                except Exception as E:
                    return E, seen
        finally:
            await runner.cleanup()

    return asyncio.run(go())


def _main(tmp_path, monkeypatch):
    part = tmp_path / "f.part"
    mgr = _manager(md.MainDownloadManager)
    ph = _placeholder(tmp_path, part)
    monkeypatch.setattr(md.placeholder, "tempFilePlaceholder", ph)
    monkeypatch.setattr(md.placeholder, "Placeholders", ph)

    async def download(c, base):
        ele = SimpleNamespace(url=f"{base}/f", id=1, post_id=1, username="u", filename="f")
        return await mgr._main_download_downloader(c, ele)

    return _run(download)


def _awaitable(value):
    """Like the Media properties: awaited, and only then fetched."""

    class _Value:
        def __await__(self):
            async def get():
                return value

            return get().__await__()

    return _Value()


def _drm(tmp_path, monkeypatch):
    part = tmp_path / "v.part"
    mgr = _manager(ad.AltDownloadManager)
    monkeypatch.setattr(ad.placeholder, "tempFilePlaceholder", _placeholder(tmp_path, part))
    monkeypatch.setattr(ad.placeholder, "Placeholders", _placeholder(tmp_path, part))


    async def download(c, base):
        ele = SimpleNamespace(
            mpd=f"{base}/x.mpd",
            license=f"{base}/licence",
            hls_header="",
            id=1,
            username="u",
            filename="f",
            mediatype="Videos",
            url=None,
            add_size=lambda size: None,
            mpd_audio=_awaitable(None),
            mpd_video=_awaitable({"origname": "v", "type": "video", "name": "v"}),
        )
        # only the transfer matters here: stop after it
        mgr._media_item_post_process_alt = lambda *a: _done()
        return await mgr._alt_download_item(c, ele, "u", 1)

    async def _done():
        return "done", 0

    return _run(download)


def _cookies(headers):
    return headers.get("Cookie", "")


def test_plain_file_on_an_unlisted_host_downloads_without_the_login(tmp_path, monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="shared"):
        result, seen = _main(tmp_path, monkeypatch)
    assert not isinstance(result, Exception), result
    assert result[0] == len(BODY)  # still downloaded
    assert len(seen) == 1
    assert SESSION not in _cookies(seen[0])
    assert "x-bc" not in {k.lower() for k in seen[0]}
    assert "sign" not in {k.lower() for k in seen[0]}
    # the host only, never the link
    assert "127.0.0.1" in caplog.text and "/f" not in caplog.text


def _metadata(monkeypatch):
    """The metadata command's request for a file's headers."""
    import ofscraper.commands.metadata.manager as mm

    monkeypatch.setattr(mm, "get_medialog", lambda ele: "")
    monkeypatch.setattr(mm.placeholder, "Placeholders", lambda ele, ext=None: ext)

    async def fetch(c, base):
        ele = SimpleNamespace(url=f"{base}/f", mpd=None, id=1, content_type="video", responsetype="timeline")
        return await mm.MetaDataManager()._metadata_helper(c, ele)

    return _run(fetch)


def test_metadata_request_to_an_unlisted_host_has_no_login(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="shared"):
        result, seen = _metadata(monkeypatch)
    assert not isinstance(result, Exception), result
    assert len(seen) == 1
    assert SESSION not in _cookies(seen[0])
    assert "x-bc" not in {k.lower() for k in seen[0]}
    assert "127.0.0.1" in caplog.text


def test_metadata_request_to_a_user_added_host_gets_the_login(monkeypatch):
    _extra_hosts(monkeypatch, ["127.0.0.1"])
    result, seen = _metadata(monkeypatch)
    assert not isinstance(result, Exception), result
    assert SESSION in _cookies(seen[0])


def _metadata_drm(monkeypatch):
    """The metadata command on a DRM video, through the real Media item: the
    file name's quality comes from its manifest (Media.parse_mpd)."""
    import ofscraper.classes.of.posts as posts_
    import ofscraper.commands.metadata.manager as mm
    import ofscraper.managers.manager as manager
    from ofscraper.classes.of.media import Media
    from ofscraper.managers.sessionHandler import SessionHandler

    monkeypatch.setattr(mm, "get_medialog", lambda ele: "")
    monkeypatch.setattr(mm, "get_alt_params", lambda ele: {})
    monkeypatch.setattr(mm.cache, "get", lambda *a, **k: None)
    monkeypatch.setattr(common_globals, "thread", None, raising=False)
    monkeypatch.setattr(manager, "Manager", SimpleNamespace(session=SessionHandler()))
    saved = []

    async def _mark(*a, **k):
        saved.append(k)

    async def _prev(*a, **k):
        return {}

    monkeypatch.setattr(mm, "mark_media_as_downloaded", _mark)
    monkeypatch.setattr(mm, "prev_download_media_data", _prev)

    class _Placeholder:
        def __init__(self, ele, ext=None):
            self.ele = ele

        async def init(self, create=True):
            # as Placeholders.init does, for the {quality} placeholder
            await self.ele.selected_quality_placeholder
            return self

    monkeypatch.setattr(mm.placeholder, "Placeholders", _Placeholder)

    async def fetch(c, base):
        post = posts_.Post({"id": 5, "responseType": "post"}, 1, "model")
        ele = Media(
            {
                "id": 7,
                "type": "video",
                "canView": True,
                "files": {
                    "drm": {
                        "manifest": {"dash": f"{base}/x.mpd"},
                        "signature": {
                            "dash": {
                                "CloudFront-Policy": "made-up",
                                "CloudFront-Key-Pair-Id": "made-up",
                                "CloudFront-Signature": "made-up",
                            }
                        },
                    }
                },
            },
            0,
            post,
        )
        return await mm.MetaDataManager().metadata(c, ele, 1, "model")

    result, seen = _run(fetch)
    return result, seen, saved


def test_metadata_on_a_drm_video_on_an_unlisted_host_sends_no_login(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="shared"):
        result, seen, saved = _metadata_drm(monkeypatch)
    # the item is skipped, as the download command refuses it, and nothing
    # about it is saved
    assert result == "skipped"
    assert saved == []
    # only the request for the file's headers, which goes without the login;
    # the manifest isn't fetched with it
    assert len(seen) == 1
    for headers in seen:
        assert SESSION not in _cookies(headers)
        assert not {"x-bc", "sign"} & {k.lower() for k in headers}
    assert "127.0.0.1" in caplog.text and "x.mpd" not in caplog.text


def test_metadata_on_a_drm_video_on_a_user_added_host_reads_the_manifest(monkeypatch):
    _extra_hosts(monkeypatch, ["127.0.0.1"])
    result, seen, saved = _metadata_drm(monkeypatch)
    # the headers request, then the manifest with the login. The test
    # server's reply isn't a manifest, so the item still ends skipped
    assert len(seen) == 2
    assert SESSION in _cookies(seen[1]) and seen[1].get("x-bc") == "made-up"


def test_plain_file_on_a_user_added_host_gets_the_login(tmp_path, monkeypatch):
    _extra_hosts(monkeypatch, ["127.0.0.1"])
    result, seen = _main(tmp_path, monkeypatch)
    assert result[0] == len(BODY)
    assert SESSION in _cookies(seen[0])
    assert seen[0].get("x-bc") == "made-up"


def test_drm_video_on_an_unlisted_host_fails_before_any_request(tmp_path, monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="shared"):
        result, seen = _drm(tmp_path, monkeypatch)
    assert isinstance(result, host_allowlist.RefusedHost)
    assert seen == []
    assert "127.0.0.1" in caplog.text and "x.mpd" not in caplog.text


def test_drm_video_on_a_user_added_host_is_downloaded(tmp_path, monkeypatch):
    _extra_hosts(monkeypatch, ["127.0.0.1"])
    result, seen = _drm(tmp_path, monkeypatch)
    assert result == ("done", 0)
    assert len(seen) == 1 and SESSION in _cookies(seen[0])


def test_fansly_files_are_not_checked(tmp_path, monkeypatch):
    # Fansly's token never goes to a file's host, so nothing is held back
    monkeypatch.setattr(sites, "is_fansly", lambda: True)
    assert host_allowlist.download_actions("https://cdn.example.invalid/f.mp4") is None


@pytest.mark.parametrize(
    "url",
    [
        "https://onlyfans.com/api2/v2/users/media/1/drm/post/2?type=widevine",
        "https://cdn2.onlyfans.com/files/a/b/c.jpg?Policy=p&Signature=s",
        "https://cdn3.onlyfans.com/dash/files/x.mpd",
        "https://public.onlyfans.com/files/a.jpg",
        "https://CDN2.OnlyFans.com./files/a.jpg",
    ],
)
def test_listed_hosts_and_subdomains_are_allowed(url):
    assert host_allowlist.is_allowed(url)
    assert host_allowlist.download_actions(url) is None
    assert host_allowlist.ensure_allowed_download_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://evil-onlyfans.com/a.mpd",
        # a shared domain anyone can get a host under
        "http://d1234.cloudfront.net/a.mp4",
        "https://onlyfans.com.evil.example/a.mpd",
        "https://notonlyfans.com/a.mpd",
        "https://onlyfans.com@evil.example/a.mpd",
        "https://evil.example\\@cdn2.onlyfans.com/a.mpd",
        "ftp://cdn2.onlyfans.com/a.mpd",
        "file:///etc/a.mpd",
        "//cdn2.onlyfans.com/a.mpd",
        "",
        None,
    ],
)
def test_lookalikes_and_other_schemes_are_refused(url, caplog):
    assert not host_allowlist.is_allowed(url)
    with caplog.at_level(logging.WARNING, logger="shared"):
        with pytest.raises(host_allowlist.RefusedHost):
            host_allowlist.ensure_allowed_download_url(url, "DRM manifest")
    assert "a.mpd" not in caplog.text


def test_user_added_suffix(monkeypatch):
    url = "https://media.cdn.example/a.mp4"
    assert not host_allowlist.is_allowed(url)
    _extra_hosts(monkeypatch, [" .CDN.example ", ""])
    assert host_allowlist.is_allowed(url)
    assert host_allowlist.is_allowed("https://cdn.example/a.mp4")
    assert not host_allowlist.is_allowed("https://evilcdn.example/a.mp4")
    # the built-in hosts stay
    assert host_allowlist.is_allowed("https://cdn2.onlyfans.com/a.mp4")


def test_env_variable_adds_hosts(monkeypatch):
    monkeypatch.setenv("OFSC_MEDIA_HOST_SUFFIXES", "cdn.example, other.example")
    from ofscraper.utils.of_env.values.url.other_url import load_other_urls_config

    assert load_other_urls_config()["MEDIA_HOST_SUFFIXES"] == ["cdn.example", "other.example"]
    monkeypatch.delenv("OFSC_MEDIA_HOST_SUFFIXES")
    assert load_other_urls_config()["MEDIA_HOST_SUFFIXES"] == []


def test_unlisted_host_warned_once(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="shared"):
        for _ in range(3):
            assert host_allowlist.download_actions("https://cdn.example.invalid/a.jpg") == host_allowlist.NO_CREDENTIALS
    assert caplog.text.count("cdn.example.invalid") == 1
