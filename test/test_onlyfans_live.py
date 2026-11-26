"""OnlyFans livestream recording: who is live, when to stop, and the app glue.

No request goes to OnlyFans and no browser starts: the browser recording
itself (``live_capture.capture``) is replaced where the glue is tested.
"""

import asyncio
import contextlib
import datetime
import threading
from types import SimpleNamespace

import pytest

import ofscraper.managers.manager as manager
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
import ofscraper.utils.system.ffmpeg as ffmpeg_finder
from ofscraper.sites.fansly import live as shared
from ofscraper.sites.onlyfans import live, live_capture

AUTH = {"auth_id": "12345", "sess": "s" * 30, "auth_uid": "", "user_agent": "UA/1", "x-bc": "b" * 40}


# ------------------------------------------------------------------ who is live

def test_only_subscriptions_with_a_stream_count_as_live():
    pages = [
        [{"id": 1, "username": "creator_a", "hasStream": True},
         {"id": 2, "username": "creator_b", "hasStream": False}],
        [{"id": 3, "username": "creator_c"},
         {"id": 4, "username": "creator_d", "hasStream": True}],
    ]
    assert live.live_subscriptions(pages) == [
        {"accountId": 1, "username": "creator_a"},
        {"accountId": 4, "username": "creator_d"},
    ]


def test_a_creator_listed_twice_is_recorded_once():
    pages = [
        [{"id": 1, "username": "creator_a", "hasStream": True}],
        [{"id": 1, "username": "creator_a", "hasStream": True},
         {"username": "creator_e", "hasStream": True}],
    ]
    assert live.live_subscriptions(pages) == [
        {"accountId": 1, "username": "creator_a"},
        {"accountId": "creator_e", "username": "creator_e"},
    ]


def test_live_creators_go_through_the_usual_username_selection():
    online = live.live_subscriptions([[
        {"id": 1, "username": "creator_a", "hasStream": True},
        {"id": 4, "username": "creator_d", "hasStream": True},
    ]])
    assert shared.select_streams(online, ["Creator_D"], None) == [{"accountId": 4, "username": "creator_d"}]
    assert shared.select_streams(online, None, ["creator_a"]) == [{"accountId": 4, "username": "creator_d"}]


@pytest.mark.parametrize("data, expected", [
    ({"isActive": True, "isFinished": False}, True),
    ({"isActive": True, "isFinished": True}, False),
    ({"isActive": False}, False),
    ({"error": {"code": 0}}, False),
    ([], None),
    (None, None),
])
def test_stream_is_active(data, expected):
    assert live.stream_is_active(data) is expected


class Response:
    def __init__(self, status, data=None, error=None):
        self.status = status
        self.data = data
        self.error = error

    async def json_(self):
        if self.error:
            raise self.error
        return self.data


class Client:
    def __init__(self, response):
        self.response = response
        self.urls = []

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, **kwargs):
        self.urls.append(url)
        yield self.response


class PagedClient(Client):
    def __init__(self, *responses):
        super().__init__(iter(responses))

    @contextlib.asynccontextmanager
    async def requests_async(self, url=None, **kwargs):
        self.urls.append(url)
        yield next(self.response)


@pytest.mark.parametrize("response, expected", [
    (Response(200, {"isActive": True}), True),
    (Response(200, {"isActive": True, "isFinished": True}), False),
    (Response(404), False),
    (Response(500), None),
    (Response(200, error=ValueError("not json")), None),
])
def test_still_live_asks_the_creators_active_stream(response, expected):
    client = Client(response)
    assert asyncio.run(live.still_live(client, "creator_a")) is expected
    assert client.urls == ["https://onlyfans.com/api2/v2/users/creator_a/streams/active?view=full_with_check"]


def test_recording_path_mirrors_the_fansly_layout(tmp_path):
    when = datetime.datetime(2026, 11, 23, 8, 5, 9, tzinfo=datetime.timezone.utc)
    assert live.recording_path(tmp_path, "creator_a", when) == (
        tmp_path / "OnlyFans" / "creator_a" / "Livestreams" / "creator_a_20261123_080509_live.webm"
    )


def test_recording_path_stays_in_the_save_folder(tmp_path):
    when = datetime.datetime(2026, 11, 23, 8, 5, 9, tzinfo=datetime.timezone.utc)
    out = live.recording_path(tmp_path, "../creator_a.", when)
    assert out.resolve().is_relative_to((tmp_path / "OnlyFans").resolve())
    assert ".." not in out.parts


# ------------------------------------------------------------------ the browser login

def test_login_cookies_carry_the_auth_json_login():
    cookies = {c["name"]: c["value"] for c in live_capture.login_cookies(AUTH)}
    assert cookies == {"auth_id": "12345", "sess": "s" * 30, "auth_uid_": "12345"}
    assert {c["domain"] for c in live_capture.login_cookies(AUTH)} == {".onlyfans.com"}


def test_the_2fa_cookie_is_added_only_when_auth_uid_is_set():
    cookies = {c["name"]: c["value"] for c in live_capture.login_cookies({**AUTH, "auth_uid": "999"})}
    assert cookies["auth_uid_"] == "999" and cookies["auth_uid_12345"] == "999"


def test_x_bc_is_put_where_the_web_app_reads_it():
    script = live_capture.xbc_script(AUTH)
    assert "localStorage.setItem('bcTokenSha', \"" + "b" * 40 + "\")" in script
    assert live_capture.xbc_script({**AUTH, "x-bc": ""}) == ""


@pytest.mark.parametrize("url, expected", [
    ("https://onlyfans.com/creator_a/live", True),
    ("https://onlyfans.com/Creator_A/live/", True),
    ("https://onlyfans.com/?return_to=%2Fcreator_a%2Flive", False),
    ("https://onlyfans.com/creator_a", False),
    ("https://onlyfans.com/creator_b/live", False),
    ("", False),
])
def test_is_live_page(url, expected):
    assert live_capture.is_live_page(url, "creator_a") is expected


@pytest.mark.parametrize("proxy, expected", [
    ("http://proxy.example.invalid:8080", {"server": "http://proxy.example.invalid:8080"}),
    ("http://user%40x:p%3Ass@proxy.example.invalid:8080",
     {"server": "http://proxy.example.invalid:8080", "username": "user@x", "password": "p:ss"}),
    ("http://user:pass@[::1]:8080", {"server": "http://[::1]:8080", "username": "user", "password": "pass"}),
    ("http://[::1]:8080", {"server": "http://[::1]:8080"}),
])
def test_the_browser_uses_the_same_proxy(proxy, expected):
    assert live_capture.browser_proxy(proxy) == expected


# ------------------------------------------------------------------ when to stop

class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_two_not_live_answers_in_a_row_stop_the_recording():
    clock = Clock()
    answers = iter([False, True, False, False])
    watch = live_capture.EndWatch(lambda: next(answers), clock)
    for expected in (None, None, None, "OnlyFans says the stream has ended"):
        clock.now += live_capture.LIVE_CHECK_SECONDS
        watch.got_data()
        assert watch.reason() == expected


def test_a_failed_check_starts_the_count_again():
    clock = Clock()
    answers = iter([False, None, False])
    watch = live_capture.EndWatch(lambda: next(answers), clock)
    results = []
    for _ in range(3):
        clock.now += live_capture.LIVE_CHECK_SECONDS
        watch.got_data()
        results.append(watch.reason())
    assert results == [None, None, None]


def test_the_end_message_stops_only_when_onlyfans_agrees():
    clock = Clock()
    answers = iter([True, False])
    watch = live_capture.EndWatch(lambda: next(answers), clock)
    watch.page_shows_ended(True)
    assert watch.reason() is None  # still live: the words could be in chat
    clock.now += live_capture.PAGE_ENDED_CHECK_SECONDS
    assert watch.reason() == "the page says the live video has ended and OnlyFans agrees"


def test_the_end_message_stops_after_a_while_when_onlyfans_cant_be_asked():
    clock = Clock()
    watch = live_capture.EndWatch(lambda: None, clock)
    watch.page_shows_ended(True)
    assert watch.reason() is None
    clock.now += live_capture.PAGE_ENDED_STOP_SECONDS
    watch.got_data()
    assert "live video ended" in watch.reason()


def test_the_end_message_check_also_counts_as_the_minute_check():
    clock = Clock()
    calls = []

    def check():
        calls.append(clock.now)
        return False

    watch = live_capture.EndWatch(check, clock)
    clock.now += live_capture.LIVE_CHECK_SECONDS - 1
    watch.page_shows_ended(True)
    assert watch.reason() == "the page says the live video has ended and OnlyFans agrees"
    assert len(calls) == 1
    watch.page_shows_ended(False)
    clock.now += 1
    watch.got_data()
    assert watch.reason() is None and len(calls) == 1  # no second check in the same minute


def test_no_data_for_five_minutes_stops_the_recording():
    clock = Clock()
    watch = live_capture.EndWatch(lambda: True, clock)
    clock.now += live_capture.NO_DATA_STOP_SECONDS - 1
    assert watch.reason() is None
    clock.now += 1
    assert watch.reason() == "no new data for 5 minutes"


# ------------------------------------------------------------------ app glue

def test_stop_reaches_the_recording_thread():
    started = threading.Event()

    def capture(halt, name):
        started.set()
        assert halt.wait(10)
        return name

    async def main():
        stop = asyncio.Event()
        task = asyncio.ensure_future(live.record_in_thread(capture, stop, name="done"))
        await asyncio.to_thread(started.wait, 10)
        stop.set()
        return await asyncio.wait_for(task, 10)

    assert asyncio.run(main()) == "done"


def test_cancelling_lets_the_recording_save_first():
    saved = threading.Event()

    def capture(halt):
        halt.wait(10)
        saved.set()

    async def main():
        task = asyncio.ensure_future(live.record_in_thread(capture, asyncio.Event()))
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(main())
    assert saved.is_set()


def test_cancelling_waits_for_the_recording_to_save():
    saved = threading.Event()

    def capture(halt):
        halt.wait(10)
        threading.Event().wait(0.5)  # the browser writing out the file
        saved.set()

    async def main():
        task = asyncio.ensure_future(live.record_in_thread(capture, asyncio.Event()))
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return saved.is_set()

    assert asyncio.run(main())  # saved before record_in_thread gave up, not after


@pytest.fixture
def onlyfans_settings(monkeypatch, tmp_path):
    def apply(**values):
        real = settings.get_settings()
        stub = SimpleNamespace(**{
            **dict(real),
            "site": "onlyfans",
            "usernames": None,
            "excluded_username": None,
            "live": False,
            "live_watch": False,
            "live_interval": None,
            "live_max": None,
            "live_chat": False,
            "username_search": None,
            "userlist": None,
            "blacklist": None,
            **values,
        })
        monkeypatch.setattr(settings, "get_settings", lambda: stub)
        monkeypatch.setattr(settings, "get_args", lambda copy=False: stub)
        return stub

    import ofscraper.utils.auth.file as auth_file

    monkeypatch.setattr(auth_file, "read_auth", lambda: dict(AUTH))
    monkeypatch.setattr(common_paths, "get_save_location", lambda config=None: str(tmp_path))
    monkeypatch.setattr(ffmpeg_finder, "get_ffmpeg", lambda: "ffmpeg")
    return apply

def install_session(monkeypatch, client, model_manager=None):
    @contextlib.asynccontextmanager
    async def aget_ofsession(*args, **kwargs):
        yield client

    monkeypatch.setattr(
        manager,
        "Manager",
        SimpleNamespace(
            session=SimpleNamespace(
                aget_ofsession=aget_ofsession, aget_subscription_session=aget_ofsession
            ),
            model_manager=model_manager,
        ),
    )


@pytest.mark.parametrize("use_model_id", [False, True])
def test_live_records_each_selected_live_creator_once(monkeypatch, onlyfans_settings, tmp_path, use_model_id):
    onlyfans_settings(live=True, usernames=["creator_a", "creator_d"])
    install_session(monkeypatch, Client(Response(200, {"isActive": False})))

    async def online(c, checks=None):
        return live.live_subscriptions([[
            {"id": 1, "username": "creator_a", "hasStream": True},
            {"id": 2, "username": "creator_b", "hasStream": True},
            {"id": 4, "username": "creator_d", "hasStream": True},
        ]])

    if use_model_id:
        import ofscraper.utils.config.file as config_file
        monkeypatch.setattr(config_file, "open_config", lambda: {
            "live_options": {"dir_format": "{sitename}/{model_id}/Livestreams"}})

    recorded = []
    reads = []
    import ofscraper.utils.auth.file as auth_file

    monkeypatch.setattr(auth_file, "read_auth", lambda: reads.append(1) or dict(AUTH))

    def capture(halt, username, out, auth, still_live, ffmpeg, proxy):
        recorded.append((username, out.parent, auth["sess"], ffmpeg, still_live()))
        return out

    monkeypatch.setattr(live, "get_online_streams", online)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: True)
    monkeypatch.setattr(live_capture, "capture", capture)
    asyncio.run(live.run(False, asyncio.Event()))
    folder = tmp_path / "OnlyFans"
    assert sorted(recorded) == [
        ("creator_a", folder / ("1" if use_model_id else "creator_a") / "Livestreams", "s" * 30, "ffmpeg", False),
        ("creator_d", folder / ("4" if use_model_id else "creator_d") / "Livestreams", "s" * 30, "ffmpeg", False),
    ]
    assert len(reads) == 2  # auth.json is read for each recording


def test_a_timed_out_live_check_is_cancelled(monkeypatch, onlyfans_settings):
    onlyfans_settings(live=True)
    install_session(monkeypatch, Client(Response(200, {})))
    real_getattr = of_env.getattr
    monkeypatch.setattr(of_env, "getattr",
                        lambda key, default=None: 1 if key == "LIVE_CHECK_TIMEOUT" else real_getattr(key, default))
    cancelled = threading.Event()

    async def never_answers(c, username):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def online(c, checks=None):
        return [{"accountId": 1, "username": "creator_a"}]

    results = []

    def capture(halt, username, out, auth, still_live, ffmpeg, proxy):
        results.append(still_live())
        results.append(cancelled.wait(5))  # the check doesn't keep running on the loop

    monkeypatch.setattr(live, "still_live", never_answers)
    monkeypatch.setattr(live, "get_online_streams", online)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: True)
    monkeypatch.setattr(live_capture, "capture", capture)
    asyncio.run(live.run(False, asyncio.Event()))
    assert results == [None, True]


def test_the_browser_gets_the_sessions_proxy(monkeypatch, onlyfans_settings):
    from ofscraper.managers.sessionmanager.sessionmanager import sessionManager

    onlyfans_settings(live=True)
    install_session(monkeypatch, sessionManager(proxy="http://proxy.invalid:8080"))

    async def online(c, checks=None):
        return [{"accountId": 1, "username": "creator_a"}]

    proxies = []

    def capture(halt, username, out, auth, still_live, ffmpeg, proxy):
        proxies.append(proxy)

    monkeypatch.setattr(live, "get_online_streams", online)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: True)
    monkeypatch.setattr(live_capture, "capture", capture)
    asyncio.run(live.run(False, asyncio.Event()))
    assert proxies == ["http://proxy.invalid:8080"]


def test_a_missing_chromium_says_how_to_install_it(monkeypatch, onlyfans_settings, caplog):
    onlyfans_settings(live=True)
    install_session(monkeypatch, Client(Response(404)))

    async def online(c, checks=None):
        return [{"accountId": 1, "username": "creator_a"}, {"accountId": 2, "username": "creator_b"}]

    def capture(**kwargs):
        raise live_capture.BrowserMissing(live_capture.install_hint())

    monkeypatch.setattr(live, "get_online_streams", online)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: True)
    monkeypatch.setattr(live_capture, "capture", capture)
    with caplog.at_level("WARNING", logger="shared"):
        asyncio.run(live.run(False, asyncio.Event()))
    # two creators tried, one warning: --live-watch would otherwise repeat it every poll
    warnings = [r for r in caplog.records if r.levelname == "WARNING" and "playwright install chromium" in r.getMessage()]
    assert len(warnings) == 1


@pytest.mark.parametrize("dist", ["ofscraper-community", "ofscraper"])
def test_without_playwright_it_says_how_to_install_and_records_nothing(monkeypatch, onlyfans_settings, caplog, dist):
    import builtins

    import ofscraper.__version__ as version

    # the hint names the package that is installed: datawhores publishes "ofscraper"
    monkeypatch.setattr(version, "__dist_name__", dist)
    onlyfans_settings(live=True)
    real_import = builtins.__import__

    def no_playwright(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_playwright)
    monkeypatch.setattr(manager, "Manager", None)  # never reached
    with caplog.at_level("WARNING", logger="shared"):
        asyncio.run(live.run(False, asyncio.Event()))
    assert f'pip install "{dist}[live]"' in caplog.text
    assert "playwright install chromium" in caplog.text


@pytest.fixture
def first_use(monkeypatch):
    """Playwright and Chromium missing; installing them makes them present."""
    from ofscraper.utils.system import extras

    state = SimpleNamespace(playwright=False, chromium=False, calls=[], works=True)

    def install(extra):
        state.calls.append(extra)
        state.playwright = state.works
        return state.works

    def install_chromium():
        state.calls.append("chromium")
        state.chromium = state.works
        return state.works

    monkeypatch.setattr(live_capture, "has_playwright", lambda: state.playwright)
    monkeypatch.setattr(live_capture, "chromium_installed", lambda: state.chromium)
    monkeypatch.setattr(extras, "install", install)
    monkeypatch.setattr(extras, "install_chromium", install_chromium)
    return state


def test_the_first_run_installs_playwright_and_chromium(first_use):
    assert live_capture.playwright_ready() is True
    assert first_use.calls == ["live", "chromium"]


def test_nothing_is_installed_when_both_are_there(first_use):
    first_use.playwright = first_use.chromium = True
    assert live_capture.playwright_ready() is True
    assert first_use.calls == []


def test_only_chromium_is_downloaded_when_playwright_is_there(first_use):
    first_use.playwright = True
    assert live_capture.playwright_ready() is True
    assert first_use.calls == ["chromium"]


def test_a_failed_install_says_how_to_install_and_records_nothing(first_use, caplog):
    first_use.works = False
    with caplog.at_level("WARNING", logger="shared"):
        assert live_capture.playwright_ready() is False
    assert "playwright install chromium" in caplog.text


def test_the_standalone_download_is_not_told_to_pip_install(monkeypatch, onlyfans_settings, caplog):
    import builtins
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    onlyfans_settings(live=True)
    real_import = builtins.__import__

    def no_playwright(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_playwright)
    monkeypatch.setattr(manager, "Manager", None)  # never reached
    with caplog.at_level("WARNING", logger="shared"):
        asyncio.run(live.run(False, asyncio.Event()))
    assert "standalone download" in caplog.text
    assert "pip install" not in caplog.text


def test_live_chat_is_fansly_only(monkeypatch, onlyfans_settings, caplog):
    onlyfans_settings(live=True, live_chat=True)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: False)
    with caplog.at_level("WARNING", logger="shared"):
        asyncio.run(live.run(False, asyncio.Event()))
    assert "--live-chat only applies to Fansly" in caplog.text


def test_the_install_hint_is_logged_once(monkeypatch, onlyfans_settings, caplog):
    onlyfans_settings(live=True)

    def not_ready():  # as playwright_ready: it logs the hint itself
        live_capture.log.warning("install it with: playwright install chromium")
        return False

    monkeypatch.setattr(live_capture, "playwright_ready", not_ready)
    with caplog.at_level("WARNING", logger="shared"):
        asyncio.run(live.run(False, asyncio.Event()))
    assert caplog.text.count("playwright install chromium") == 1


# ------------------------------------------------------------------ search, caching & logging

def serve_models(monkeypatch, fake_get_models, by_name=None, lists=None, expired=()):
    """Answer the creator lookups from ``fake_get_models``: the subscription
    list read (each one an active subscription) and, unless ``by_name`` answers
    them, the lookups of -u names one by one. ``lists`` maps a list name to its
    members; ``expired`` are the expired subscriptions. The scraper's
    retriever, with its screen, must not run."""
    import ofscraper.data.api.subscriptions.individual as individual
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.data.models.utils import retriver

    async def listed(*_, **kwargs):
        return [m.model for m in await fake_get_models()]

    async def expired_subs(*_, **kwargs):
        return list(expired)

    async def members(names):
        return [u for n in names or () for u in (lists or {}).get(n, [])]

    async def no_retriever(*_, **__):
        pytest.fail("the live watcher must not run the scraper's retriever")

    monkeypatch.setattr(subs, "activeHelper", listed)
    monkeypatch.setattr(subs, "expiredHelper", expired_subs)
    monkeypatch.setattr(individual, "get_subscription", by_name or listed)
    monkeypatch.setattr(live, "_list_members", members)
    monkeypatch.setattr(retriver, "get_models", no_retriever)


def test_without_username_and_filters_it_scans_active_subscriptions(monkeypatch, onlyfans_settings):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.data.models.utils import retriver

    onlyfans_settings(live=True, usernames=None, excluded_username=None)
    used = []

    async def fake_active(c, strict=False):
        used.append("active_subs")
        yield [
            {"id": 1, "username": "creator_a", "hasStream": True},
            {"id": 2, "username": "creator_b", "hasStream": False},
        ]

    async def fail_retriver():
        pytest.fail("retriver.get_models() must not run when --username is omitted without filters")

    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    monkeypatch.setattr(retriver, "get_models", fail_retriver)

    result = asyncio.run(live.get_online_streams(Client(Response(200, {}))))
    assert used == ["active_subs"]
    assert result == [{"accountId": 1, "username": "creator_a"}]


@pytest.mark.parametrize("search_mode", ["individual", None])
def test_with_username_individual_looks_up_by_name_and_checks_session(
    monkeypatch, onlyfans_settings, search_mode
):
    from ofscraper.classes.of.models import Model

    onlyfans_settings(
        live=True,
        usernames=["creator_a"],
        excluded_username=None,
        username_search=search_mode,
    )
    seen_modes = []

    async def fake_get_models():
        seen_modes.append(settings.get_settings().username_search)
        return [
            Model({"id": 1, "username": "creator_a", "hasStream": False}),
            Model({"id": 2, "username": "creator_b", "hasStream": True}),
        ]

    serve_models(monkeypatch, fake_get_models)
    main_client = Client(Response(200, {}))
    checks_client = Client(Response(200, {"isActive": True, "isFinished": False}))

    result = asyncio.run(live.get_online_streams(main_client, checks=checks_client))
    assert seen_modes == [search_mode]
    assert result == [{"accountId": 1, "username": "creator_a"}]
    assert main_client.urls == []
    assert checks_client.urls == [
        "https://onlyfans.com/api2/v2/users/creator_a/streams/active?view=full_with_check"
    ]


def test_with_username_list_search_uses_batch_subscriptions_across_polls(
    monkeypatch, onlyfans_settings
):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.classes.of.models import Model

    onlyfans_settings(
        live_watch=True,
        usernames=["creator_a"],
        excluded_username=None,
        username_search="list",
    )
    retriver_calls = []
    batch_calls = []

    async def fake_get_models():
        retriver_calls.append(1)
        return [
            Model({"id": 1, "username": "creator_a", "hasStream": False}),
            Model({"id": 2, "username": "creator_b", "hasStream": True}),
        ]

    async def fake_active(c, strict=False):
        batch_calls.append(1)
        yield [
            {"id": 1, "username": "creator_a", "hasStream": True},
            {"id": 2, "username": "creator_b", "hasStream": True},
        ]

    serve_models(monkeypatch, fake_get_models)
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    main_client = Client(Response(200, {}))
    checks_client = Client(Response(200, {}))

    token = live._TARGET_CACHE.set({})
    try:
        # the first poll reads the active list too, so it finds the live creator straight away
        assert asyncio.run(live.get_online_streams(main_client, checks=checks_client)) == [
            {"accountId": 1, "username": "creator_a"}
        ]
        assert asyncio.run(live.get_online_streams(main_client, checks=checks_client)) == [
            {"accountId": 1, "username": "creator_a"}
        ]
    finally:
        live._TARGET_CACHE.reset(token)

    assert len(retriver_calls) == 1
    assert len(batch_calls) == 2
    assert checks_client.urls == []


@pytest.mark.parametrize("search_mode", ["individual", "list"])
def test_a_renamed_creator_is_found_by_the_old_name(monkeypatch, onlyfans_settings, search_mode):
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live=True, usernames=["creator_old"], username_search=search_mode)

    async def fake_get_models():
        return [
            Model({"id": 1, "username": "creator_new", "hasStream": True,
                   "looked_up_as": ["creator_old"]}),
            Model({"id": 2, "username": "creator_b", "hasStream": True}),
        ]

    recorded = []

    def capture(halt, username, out, auth, still_live, ffmpeg, proxy):
        recorded.append(username)

    serve_models(monkeypatch, fake_get_models)
    install_session(monkeypatch, Client(Response(200, {"isActive": True})))
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: True)
    monkeypatch.setattr(live_capture, "capture", capture)
    asyncio.run(live.run(False, asyncio.Event()))
    assert recorded == ["creator_new"]


def test_a_skip_flag_counts_as_a_user_filter(monkeypatch, onlyfans_settings):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.classes.of.models import Model

    # --promo-skip sets promo to False, which is a filter, not "no filter"
    onlyfans_settings(live_watch=True, usernames=None, promo=False)
    resolved = []

    async def fake_get_models():
        resolved.append(1)
        return [Model({"id": 1, "username": "creator_a", "hasStream": True})]

    async def fake_active(c, strict=False):
        yield [{"id": 2, "username": "creator_b", "hasStream": True}]

    serve_models(monkeypatch, fake_get_models)
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    install_session(monkeypatch, Client(Response(200, {})),
                    model_manager=SimpleNamespace(filter_models=lambda models: list(models)))
    token = live._TARGET_CACHE.set({})
    try:
        asyncio.run(live.get_online_streams(Client(Response(200, {}))))
    finally:
        live._TARGET_CACHE.reset(token)
    assert resolved == [1]


def test_the_built_in_list_names_come_from_of_env(monkeypatch, onlyfans_settings):
    from ofscraper.managers.model import ModelManager

    onlyfans_settings(live=True, userlist=["everyone"])
    real_getattr = of_env.getattr
    monkeypatch.setattr(of_env, "getattr",
                        lambda key, default=None: "everyone" if key == "OFSCRAPER_RESERVED_LIST_ALT" else real_getattr(key, default))
    assert not ModelManager.has_active_filters()


def test_renew_off_filters_the_named_creators(monkeypatch, onlyfans_settings):
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live=True, usernames=["creator_a", "creator_b"],
                      username_search="individual", renewal=False)

    async def fake_get_models():
        return [Model({"id": 1, "username": "creator_a", "hasStream": True}),
                Model({"id": 2, "username": "creator_b", "hasStream": True})]

    filtered = []

    def filter_models(models):
        filtered.append([m.name for m in models])
        return [m for m in models if m.name == "creator_a"]

    serve_models(monkeypatch, fake_get_models)
    install_session(monkeypatch, Client(Response(200, {})),
                    model_manager=SimpleNamespace(filter_models=filter_models))
    token = live._TARGET_CACHE.set({})
    try:
        result = asyncio.run(live.get_online_streams(Client(Response(200, {}))))
    finally:
        live._TARGET_CACHE.reset(token)
    assert filtered == [["creator_a", "creator_b"]]
    assert result == [{"accountId": 1, "username": "creator_a"}]


@pytest.mark.parametrize("search_mode", ["individual", "list"])
def test_a_creator_not_found_at_first_is_looked_up_again(
    monkeypatch, onlyfans_settings, caplog, search_mode
):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live_watch=True, usernames=["creator_a", "creator_b"],
                      username_search=search_mode)

    async def fake_get_models():
        return [Model({"id": 1, "username": "creator_a", "hasStream": False})]

    looked_up = []

    async def fake_individual(accounts=None):
        looked_up.append(list(accounts))
        if len(looked_up) == 1:  # creator_b's lookup failed this time (the lookup logs and goes on)
            return [m.model for m in await fake_get_models()]
        return [{"id": 2, "username": "creator_b", "hasStream": True, "looked_up_as": ["creator_b"]}]

    async def fake_active(c, strict=False):
        yield [{"id": 2, "username": "creator_b", "hasStream": True}]

    serve_models(monkeypatch, fake_get_models, by_name=fake_individual)
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    checks = Client(Response(200, {"isActive": False}))
    token = live._TARGET_CACHE.set({})
    try:
        with caplog.at_level("WARNING", logger="shared"):
            first = asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=checks))
            second = asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=checks))
            third = asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=checks))
    finally:
        live._TARGET_CACHE.reset(token)
    assert first == []
    assert [s["username"] for s in second] == ["creator_b"]
    assert [s["username"] for s in third] == (["creator_b"] if search_mode == "list" else [])
    assert looked_up[1:] == [["creator_b"]]  # once found, it isn't looked up again
    assert caplog.text.count("creator_b") == 1  # one warning while it's missing


def test_list_targets_missing_from_active_subscriptions_are_asked_directly(
    monkeypatch, onlyfans_settings
):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live_watch=True, usernames=["creator_a", "creator_b"], username_search="list")

    async def fake_get_models():  # creator_a is an expired subscription
        return [Model({"id": 1, "username": "creator_a", "hasStream": False}),
                Model({"id": 2, "username": "creator_b", "hasStream": False})]

    async def fake_active(c, strict=False):
        yield [{"id": 2, "username": "creator_b", "hasStream": False}]

    serve_models(monkeypatch, fake_get_models)
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    checks = Client(Response(200, {"isActive": True}))
    token = live._TARGET_CACHE.set({})
    try:
        asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=checks))
        second = asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=checks))
    finally:
        live._TARGET_CACHE.reset(token)
    assert second == [{"accountId": 1, "username": "creator_a"}]
    assert checks.urls == ["https://onlyfans.com/api2/v2/users/creator_a/streams/active?view=full_with_check"] * 2


def test_many_named_creators_are_checked_from_the_subscription_list(monkeypatch, onlyfans_settings):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.classes.of.models import Model

    names = ["creator_a", "creator_b", "creator_c"]
    onlyfans_settings(live_watch=True, usernames=names, username_search="individual")

    async def fake_get_models():
        return [Model({"id": i, "username": n, "hasStream": False}) for i, n in enumerate(names, 1)]

    scans = []

    async def fake_active(c, strict=False):
        scans.append(1)
        yield [{"id": 1, "username": "creator_a", "hasStream": False},
               {"id": 2, "username": "creator_b", "hasStream": True},
               {"id": 3, "username": "creator_c", "hasStream": False}]

    real_getattr = of_env.getattr
    monkeypatch.setattr(of_env, "getattr",
                        lambda key, default=None: 2 if key == "LIVE_INDIVIDUAL_MAX" else real_getattr(key, default))
    serve_models(monkeypatch, fake_get_models)
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    checks = Client(Response(200, {"isActive": True}))
    token = live._TARGET_CACHE.set({})
    try:
        result = asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=checks))
    finally:
        live._TARGET_CACHE.reset(token)
    assert result == [{"accountId": 2, "username": "creator_b"}]
    assert scans == [1]
    assert checks.urls == []  # one list scan, not a request per creator


def test_failed_live_checks_warn_once_per_failure_streak(monkeypatch, onlyfans_settings, caplog):
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live_watch=True, usernames=["creator_a"], username_search="individual")

    async def fake_get_models():
        return [Model({"id": 1, "username": "creator_a", "hasStream": False})]

    serve_models(monkeypatch, fake_get_models)
    refused = Client(Response(429))
    token = live._TARGET_CACHE.set({})
    try:
        with caplog.at_level("WARNING", logger="shared"):
            for client in (refused, refused, Client(Response(200, {"isActive": False})), refused):
                asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=client))
    finally:
        live._TARGET_CACHE.reset(token)
    warnings = [r for r in caplog.records if "live check failed" in r.getMessage()]
    assert len(warnings) == 2  # once per streak of failed checks


def _direct_check_run(monkeypatch, onlyfans_settings, active_pages, polls=3, members=None, most=None,
                      expired=False, **values):
    """Poll a few times over 3 creators missing from the active list (expired
    subscriptions with ``expired``); returns the usernames asked directly on
    each poll. ``active_pages`` None: reading the active list fails."""
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live_watch=True, **values)
    creators = [Model({"id": i, "username": f"creator_{i}", "hasStream": False}) for i in (1, 2, 3)]

    async def fake_get_models():
        return [] if expired else creators

    async def fake_active(c, strict=False):
        if active_pages is None:
            raise RuntimeError("active subscriptions: HTTP 500")
        for page in active_pages:
            yield page

    on_list = [{"id": i, "username": f"creator_{i}"} for i in (members or [])]
    serve_models(monkeypatch, fake_get_models, lists={n: on_list for n in values.get("userlist") or []},
                 expired=[m.model for m in creators] if expired else ())
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    if most is not None:
        real_getattr = of_env.getattr
        monkeypatch.setattr(of_env, "getattr",
                            lambda key, default=None: most if key == "LIVE_INDIVIDUAL_MAX" else real_getattr(key, default))
    install_session(monkeypatch, Client(Response(200, {})),
                    model_manager=SimpleNamespace(filter_models=lambda models: list(models)))
    asked = []
    token = live._TARGET_CACHE.set({})
    try:
        for _ in range(polls):
            checks = Client(Response(200, {"isActive": False}))
            try:
                asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=checks))
            except RuntimeError:
                pass  # a failed poll: the watcher warns and polls again later
            asked.append(sorted(u.split("/users/")[1].split("/")[0] for u in checks.urls))
    finally:
        live._TARGET_CACHE.reset(token)
    return asked


OTHER_ACTIVE = [[{"id": 99, "username": "creator_99", "hasStream": False}]]


def test_the_first_list_poll_asks_named_creators_missing_from_active_subscriptions(
    monkeypatch, onlyfans_settings
):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live=True, usernames=["creator_a"], username_search="list")

    async def fake_get_models():  # an expired subscription; its record has no hasStream
        return [Model({"id": 1, "username": "creator_a"})]

    async def fake_active(c, strict=False):
        yield [{"id": 99, "username": "creator_99", "hasStream": False}]

    serve_models(monkeypatch, fake_get_models)
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    checks = Client(Response(200, {"isActive": True}))
    token = live._TARGET_CACHE.set({})
    try:
        first = asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=checks))
    finally:
        live._TARGET_CACHE.reset(token)
    assert first == [{"accountId": 1, "username": "creator_a"}]


def test_filters_without_names_watch_active_subscriptions_only(monkeypatch, onlyfans_settings, caplog):
    with caplog.at_level("INFO", logger="shared"):
        asked = _direct_check_run(monkeypatch, onlyfans_settings, OTHER_ACTIVE, promo=False)
    assert asked[1:] == [[], []]
    assert caplog.text.count("only active subscriptions are checked") == 1


def test_members_of_a_chosen_user_list_are_asked_directly(monkeypatch, onlyfans_settings):
    asked = _direct_check_run(monkeypatch, onlyfans_settings, OTHER_ACTIVE, members=[1], userlist=["vip"])
    assert asked[1:] == [["creator_1"], ["creator_1"]]


def test_direct_checks_take_turns_above_the_cap(monkeypatch, onlyfans_settings):
    asked = _direct_check_run(monkeypatch, onlyfans_settings, OTHER_ACTIVE, most=2,
                              usernames=["creator_1", "creator_2", "creator_3"], username_search="list")
    assert all(len(a) <= 2 for a in asked)
    assert set(asked[1]) | set(asked[2]) == {"creator_1", "creator_2", "creator_3"}


def test_a_failed_active_scan_asks_nobody_directly(monkeypatch, onlyfans_settings):
    asked = _direct_check_run(monkeypatch, onlyfans_settings, None,
                              usernames=["creator_1", "creator_2", "creator_3"], username_search="list")
    assert asked == [[], [], []]


def test_with_no_active_subscriptions_named_creators_are_still_asked(monkeypatch, onlyfans_settings):
    # an account with only expired subscriptions: the active list is read fine and empty
    asked = _direct_check_run(monkeypatch, onlyfans_settings, [],
                              usernames=["creator_1", "creator_2", "creator_3"], username_search="list")
    assert asked == [["creator_1", "creator_2", "creator_3"]] * 3


def test_with_the_expired_list_expired_subscriptions_are_asked(monkeypatch, onlyfans_settings):
    asked = _direct_check_run(monkeypatch, onlyfans_settings, [], expired=True, userlist=["expired"])
    assert asked == [["creator_1", "creator_2", "creator_3"]] * 3


def test_the_active_list_is_read_strictly(monkeypatch):
    import ofscraper.data.api.subscriptions.subscriptions as subs

    async def scan(strict):
        return [page async for page in subs.scrape_subscriptions_active(Client(Response(500)), strict=strict)]

    assert asyncio.run(scan(False)) == []  # the scraper's read ends quietly
    with pytest.raises(Exception):
        asyncio.run(scan(True))


def test_a_partial_subscription_lookup_is_retried(monkeypatch, onlyfans_settings):
    onlyfans_settings(live_watch=True, usernames=["ALL"], userlist=["active"],
                      blacklist=[], renewal=True)
    first = Response(200, {"list": [{"id": 1, "username": "first"}], "hasMore": True})
    last = Response(200, {"list": [{"id": 2, "username": "second", "hasStream": True}]})
    client = PagedClient(first, Response(500), first, last, first, last)
    install_session(monkeypatch, client,
                    model_manager=SimpleNamespace(filter_models=list))

    async def check():
        token = live._TARGET_CACHE.set({})
        try:
            with pytest.raises(RuntimeError, match="HTTP 500"):
                await live.get_online_streams(client)
            assert await live.get_online_streams(client) == [{"accountId": 2, "username": "second"}]
        finally:
            live._TARGET_CACHE.reset(token)

    asyncio.run(check())


@pytest.mark.parametrize("member_lookup_fails", [False, True])
def test_a_failed_blacklist_lookup_is_retried(monkeypatch, onlyfans_settings, member_lookup_fails):
    import ofscraper.data.api.subscriptions.individual as individual

    onlyfans_settings(live_watch=True, usernames=["first", "second"],
                      username_search="individual", blacklist=["blocked"])
    creators = [{"id": i, "username": name, "hasStream": True}
                for i, name in [(1, "first"), (2, "second")]]

    async def profiles(_):
        return creators

    lists = Response(200, {"list": [{"id": 7, "name": "blocked"}]})
    members = Response(200, {"list": [creators[0]]})
    failure = Response(500, error=asyncio.TimeoutError())
    failed_scan = [lists, failure] if member_lookup_fails else [failure]
    client = PagedClient(*failed_scan, lists, members)
    monkeypatch.setattr(individual, "get_subscription", profiles)
    install_session(monkeypatch, client,
                    model_manager=SimpleNamespace(filter_models=list))

    async def check():
        token = live._TARGET_CACHE.set({})
        try:
            with pytest.raises((RuntimeError, asyncio.TimeoutError)):
                await live.get_online_streams(client)
            assert await live.get_online_streams(client) == [{"accountId": 2, "username": "second"}]
        finally:
            live._TARGET_CACHE.reset(token)

    asyncio.run(check())


def test_a_named_creator_on_a_black_list_is_left_out_not_looked_up_again(
    monkeypatch, onlyfans_settings, caplog
):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live_watch=True, usernames=["creator_a", "creator_b"],
                      username_search="list", blacklist=["blocked"])

    async def fake_get_models():
        return [Model({"id": 1, "username": "creator_a", "hasStream": False}),
                Model({"id": 2, "username": "creator_b", "hasStream": True})]

    looked_up = []

    async def fake_individual(accounts=None):
        looked_up.append(list(accounts))
        return [{"id": 2, "username": "creator_b", "hasStream": True, "looked_up_as": ["creator_b"]}]

    async def fake_active(c, strict=False):
        yield [{"id": 1, "username": "creator_a", "hasStream": False},
               {"id": 2, "username": "creator_b", "hasStream": True}]

    serve_models(monkeypatch, fake_get_models, by_name=fake_individual,
                 lists={"blocked": [{"id": 2, "username": "creator_b"}]})
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    install_session(monkeypatch, Client(Response(200, {})),
                    model_manager=SimpleNamespace(filter_models=lambda models: list(models)))
    token = live._TARGET_CACHE.set({})
    try:
        with caplog.at_level("WARNING", logger="shared"):
            results = [asyncio.run(live.get_online_streams(Client(Response(200, {})),
                                                           checks=Client(Response(200, {}))))
                       for _ in range(3)]
    finally:
        live._TARGET_CACHE.reset(token)
    assert results == [[], [], []]
    assert looked_up == []
    assert "Could not look up" not in caplog.text


@pytest.mark.parametrize("blacklist", [
    "ofscraper.active", "active", "ofscraper.expired", "expired", "ofscraper.main", "main",
])
def test_individual_targets_respect_builtin_blacklists(monkeypatch, onlyfans_settings, blacklist):
    import ofscraper.data.api.subscriptions.individual as individual

    onlyfans_settings(live_watch=True, usernames=["creator_a", "creator_b"],
                      username_search="individual", blacklist=[blacklist])
    creators = [{"id": i, "username": name, "hasStream": True}
                for i, name in [(1, "creator_a"), (2, "creator_b")]]

    async def profiles(_):
        return creators

    class BlacklistClient(Client):
        @contextlib.asynccontextmanager
        async def requests_async(self, url=None, **kwargs):
            self.urls.append(url)
            subscription_urls = [of_env.getattr(key).format(0) for key in
                                 ("subscriptionsActiveEP", "subscriptionsExpiredEP")]
            yield Response(200, {"list": creators[:1] if url in subscription_urls else []})

    client = BlacklistClient(None)
    monkeypatch.setattr(individual, "get_subscription", profiles)
    install_session(monkeypatch, client, model_manager=SimpleNamespace(filter_models=list))

    async def check():
        token = live._TARGET_CACHE.set({})
        try:
            for _ in range(2):
                assert await live.get_online_streams(
                    client, checks=Client(Response(200, {"isActive": True}))
                ) == [{"accountId": 2, "username": "creator_b"}]
        finally:
            live._TARGET_CACHE.reset(token)

    asyncio.run(check())


def test_a_name_that_keeps_missing_is_looked_up_less_often(monkeypatch, onlyfans_settings, caplog):
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live_watch=True, usernames=["creator_a", "no_such_name"], username_search="individual")

    async def fake_get_models():
        return [Model({"id": 1, "username": "creator_a", "hasStream": False})]

    looked_up = []

    async def fake_individual(accounts=None):
        looked_up.append(list(accounts))
        return [m.model for m in await fake_get_models() if m.name in accounts]

    serve_models(monkeypatch, fake_get_models, by_name=fake_individual)
    token = live._TARGET_CACHE.set({})
    try:
        with caplog.at_level("WARNING", logger="shared"):
            for _ in range(25):
                asyncio.run(live.get_online_streams(Client(Response(200, {})),
                                                    checks=Client(Response(200, {"isActive": False}))))
    finally:
        live._TARGET_CACHE.reset(token)
    # three misses in a row (the first lookup and two more), then every 10th poll
    assert looked_up[0] == ["creator_a", "no_such_name"]
    assert len(looked_up[1:]) == 4
    assert caplog.text.count("every 10th check") == 1


@pytest.mark.parametrize("watch", [True, False])
def test_a_missed_lookup_promises_a_retry_only_when_watching(monkeypatch, onlyfans_settings, caplog, watch):
    onlyfans_settings(live=not watch, live_watch=watch, usernames=["no_such_name"], username_search="individual")

    async def nobody():
        return []

    serve_models(monkeypatch, nobody)
    token = live._TARGET_CACHE.set({})
    try:
        with caplog.at_level("WARNING", logger="shared"):
            asyncio.run(live.get_online_streams(Client(Response(200, {}))))
    finally:
        live._TARGET_CACHE.reset(token)
    assert "Could not look up no_such_name" in caplog.text
    assert ("next check" in caplog.text) == watch


def test_a_lookup_that_raised_is_tried_again_next_poll(monkeypatch, onlyfans_settings):
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live_watch=True, usernames=["creator_a"], username_search="individual")
    calls = []

    async def fake_get_models():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("lookup failed")
        return [Model({"id": 1, "username": "creator_a", "hasStream": True})]

    serve_models(monkeypatch, fake_get_models)
    checks = Client(Response(200, {"isActive": True}))
    token = live._TARGET_CACHE.set({})
    try:
        with pytest.raises(RuntimeError):
            asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=checks))
        second = asyncio.run(live.get_online_streams(Client(Response(200, {})), checks=checks))
    finally:
        live._TARGET_CACHE.reset(token)
    assert second == [{"accountId": 1, "username": "creator_a"}]
    assert len(calls) == 2


def test_all_with_filters_looks_up_again_when_nothing_came_back(monkeypatch, onlyfans_settings):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.classes.of.models import Model

    onlyfans_settings(live_watch=True, usernames=None, promo=False)
    answers = [[], [Model({"id": 1, "username": "creator_a", "hasStream": True})]]
    calls = []

    async def fake_get_models():
        calls.append(1)
        return answers[len(calls) - 1]

    async def fake_active(c, strict=False):
        yield []

    serve_models(monkeypatch, fake_get_models)
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    install_session(monkeypatch, Client(Response(200, {})),
                    model_manager=SimpleNamespace(filter_models=lambda models: list(models)))
    token = live._TARGET_CACHE.set({})
    try:
        first = asyncio.run(live.get_online_streams(Client(Response(200, {}))))
        second = asyncio.run(live.get_online_streams(Client(Response(200, {}))))
    finally:
        live._TARGET_CACHE.reset(token)
    assert first == []
    assert second == [{"accountId": 1, "username": "creator_a"}]
    assert len(calls) == 2


def test_all_with_filters_finding_nobody_is_looked_up_less_often(monkeypatch, onlyfans_settings, caplog):
    onlyfans_settings(live_watch=True, usernames=None, promo=False)
    calls = []

    async def fake_get_models():
        calls.append(1)
        return []

    serve_models(monkeypatch, fake_get_models)
    install_session(monkeypatch, Client(Response(200, {})),
                    model_manager=SimpleNamespace(filter_models=lambda models: list(models)))
    token = live._TARGET_CACHE.set({})
    try:
        with caplog.at_level("WARNING", logger="shared"):
            for _ in range(25):
                asyncio.run(live.get_online_streams(Client(Response(200, {}))))
    finally:
        live._TARGET_CACHE.reset(token)
    assert len(calls) == 5  # polls 1 to 3, then every 10th poll
    assert caplog.text.count("every 10th check") == 1


def test_target_creators_are_resolved_once_across_watch_polls(monkeypatch, onlyfans_settings):
    from ofscraper.classes.of.models import Model

    onlyfans_settings(
        live_watch=True,
        usernames=["creator_a"],
        excluded_username=None,
        username_search="individual",
    )
    retriver_calls = []

    async def fake_get_models():
        retriver_calls.append(1)
        return [Model({"id": 1, "username": "creator_a", "hasStream": False})]

    serve_models(monkeypatch, fake_get_models)
    main_client = Client(Response(200, {}))
    checks_client = Client(Response(200, {"isActive": False}))

    token = live._TARGET_CACHE.set({})
    try:
        assert asyncio.run(live.get_online_streams(main_client, checks=checks_client)) == []
        assert asyncio.run(live.get_online_streams(main_client, checks=checks_client)) == []
        assert asyncio.run(live.get_online_streams(main_client, checks=checks_client)) == []
    finally:
        live._TARGET_CACHE.reset(token)

    assert len(retriver_calls) == 1
    assert main_client.urls == []
    assert len(checks_client.urls) == 3


def test_all_with_user_filters_caches_targets_and_uses_batch_subscriptions(
    monkeypatch, onlyfans_settings
):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    from ofscraper.classes.of.models import Model
    from ofscraper.managers.model import ModelManager

    onlyfans_settings(live_watch=True, usernames=None, excluded_username=[], userlist=["vip"])
    retriver_calls = []
    batch_calls = []

    async def fake_get_models():
        retriver_calls.append(1)
        return [
            Model({"id": 1, "username": "creator_a", "hasStream": False}),
            Model({"id": 2, "username": "creator_b", "hasStream": False}),
        ]

    def fake_filter_models(self, models):
        return [m for m in models if m.id == 1]

    async def fake_active(c, strict=False):
        batch_calls.append(1)
        yield [
            {"id": 1, "username": "creator_a", "hasStream": True},
            {"id": 2, "username": "creator_b", "hasStream": True},
        ]

    serve_models(monkeypatch, fake_get_models)
    monkeypatch.setattr(ModelManager, "filter_models", fake_filter_models)
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    main_client = Client(Response(200, {}))
    checks_client = Client(Response(200, {}))

    token = live._TARGET_CACHE.set({})
    try:
        for _ in range(3):  # the first poll reads the active list too
            assert asyncio.run(live.get_online_streams(main_client, checks=checks_client)) == [
                {"accountId": 1, "username": "creator_a"}
            ]
    finally:
        live._TARGET_CACHE.reset(token)

    assert len(retriver_calls) == 1
    assert len(batch_calls) == 3
    assert checks_client.urls == []


def test_concurrent_individual_checks_respect_env_concurrency_and_stream_url(
    monkeypatch, onlyfans_settings
):
    from ofscraper.classes.of.models import Model

    monkeypatch.setenv("OFSC_LIVE_CHECK_CONCURRENCY", "2")
    monkeypatch.setenv("OFSC_STREAM_ACTIVE_URL", "https://example.invalid/custom/{}/live")
    of_env.get_all_configs(forced=True)

    try:
        onlyfans_settings(
            live=True,
            usernames=["u1", "u2", "u3", "u4"],
            username_search="individual",
        )

        async def fake_get_models():
            return [
                Model({"id": idx, "username": f"u{idx}", "hasStream": False})
                for idx in range(1, 5)
            ]

        serve_models(monkeypatch, fake_get_models)

        in_flight = 0
        max_seen = 0
        seen_urls = []

        class TrackingClient:
            @contextlib.asynccontextmanager
            async def requests_async(self, url=None, **kwargs):
                nonlocal in_flight, max_seen
                seen_urls.append(url)
                in_flight += 1
                max_seen = max(max_seen, in_flight)
                try:
                    await asyncio.sleep(0.02)
                    yield Response(200, {"isActive": url.endswith("/u2/live")})
                finally:
                    in_flight -= 1

        result = asyncio.run(
            live.get_online_streams(Client(Response(200, {})), checks=TrackingClient())
        )
        assert result == [{"accountId": 2, "username": "u2"}]
        assert max_seen == 2
        assert sorted(seen_urls) == [
            f"https://example.invalid/custom/u{idx}/live" for idx in range(1, 5)
        ]
    finally:
        monkeypatch.delenv("OFSC_LIVE_CHECK_CONCURRENCY", raising=False)
        monkeypatch.delenv("OFSC_STREAM_ACTIVE_URL", raising=False)
        of_env.get_all_configs(forced=True)


def test_a_recording_is_announced_only_when_something_was_captured(monkeypatch, onlyfans_settings, caplog):
    onlyfans_settings(live=True)
    install_session(monkeypatch, Client(Response(404)))

    async def online(c, checks=None):
        return [{"accountId": 1, "username": "creator_a"}, {"accountId": 2, "username": "creator_b"}]

    def capture(username, out, **kwargs):
        # creator_b's page showed nothing to record (a ticketed stream, the login page)
        return out if username == "creator_a" else None

    monkeypatch.setattr(live, "get_online_streams", online)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: True)
    monkeypatch.setattr(live_capture, "capture", capture)
    with caplog.at_level("DEBUG", logger="shared"):
        asyncio.run(live.run(False, asyncio.Event()))
    info = [r.getMessage() for r in caplog.records if r.levelname == "INFO" and "OnlyFans livestream" in r.getMessage()]
    assert any("creator_a" in m for m in info)
    assert not any("creator_b" in m for m in info)


def test_idle_and_live_status_logs_announce_transitions_once(monkeypatch, onlyfans_settings, caplog):
    onlyfans_settings(live_watch=True, live_interval=10, usernames=["creator_a"])
    install_session(monkeypatch, Client(Response(404)))

    polls = iter([
        [],
        [],
        [{"accountId": 1, "username": "creator_a"}],
        [{"accountId": 1, "username": "creator_a"}],
        [],
        [],
    ])
    stop = asyncio.Event()
    recording_started = threading.Event()
    finish_recording = threading.Event()

    async def fake_online(c, checks=None):
        try:
            return next(polls)
        except StopIteration:
            stop.set()
            return []

    def fake_capture(halt, username, out, auth, still_live, ffmpeg, proxy):
        recording_started.set()
        finish_recording.wait(5)
        return out

    monkeypatch.setattr(live, "get_online_streams", fake_online)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: True)
    monkeypatch.setattr(live_capture, "capture", fake_capture)

    class FastWatcher(shared.LiveWatcher):
        def __init__(self, fetch_online, record, **kwargs):
            super().__init__(
                fetch_online,
                record,
                max_concurrent=kwargs.get("max_concurrent", 2),
                interval=0.01,
                jitter=0,
                once=kwargs.get("once", False),
            )

    monkeypatch.setattr(shared, "LiveWatcher", FastWatcher)

    async def run_watch():
        task = asyncio.ensure_future(live.run(True, stop))
        await asyncio.to_thread(recording_started.wait, 5)
        await asyncio.sleep(0.05)
        finish_recording.set()
        await asyncio.wait_for(task, 5)

    with caplog.at_level("INFO", logger="shared"):
        asyncio.run(run_watch())

    info_messages = [r.getMessage() for r in caplog.records if r.levelname == "INFO"]
    idle_logs = [m for m in info_messages if "No active OnlyFans livestreams" in m]
    live_logs = [m for m in info_messages if "Live now (1): creator_a" in m]

    # Once before stream starts, once after stream ends (not repeated on consecutive empty polls)
    assert len(idle_logs) == 2
    # Once when creator_a goes live (not repeated while still recording)
    assert len(live_logs) == 1


def test_live_now_does_not_repeat_when_queued_or_capture_missing(
    monkeypatch, onlyfans_settings, caplog
):
    onlyfans_settings(live_watch=True, live_interval=10, live_max=1)
    install_session(monkeypatch, Client(Response(404)))

    streams = [
        {"accountId": 1, "username": "creator_a"},
        {"accountId": 2, "username": "creator_b"},
    ]
    polls = iter([streams, streams, streams])
    stop = asyncio.Event()
    started = threading.Event()
    finish = threading.Event()

    async def fake_online(c, checks=None):
        try:
            return next(polls)
        except StopIteration:
            stop.set()
            return []

    def fake_capture(halt, username, out, auth, still_live, ffmpeg, proxy):
        started.set()
        finish.wait(5)
        return out

    monkeypatch.setattr(live, "get_online_streams", fake_online)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: True)
    monkeypatch.setattr(live_capture, "capture", fake_capture)

    class FastWatcher(shared.LiveWatcher):
        def __init__(self, fetch_online, record, **kwargs):
            super().__init__(
                fetch_online,
                record,
                max_concurrent=kwargs.get("max_concurrent", 2),
                interval=0.01,
                jitter=0,
                once=kwargs.get("once", False),
            )

    monkeypatch.setattr(shared, "LiveWatcher", FastWatcher)

    async def run_watch():
        task = asyncio.ensure_future(live.run(True, stop))
        await asyncio.to_thread(started.wait, 5)
        await asyncio.sleep(0.05)
        finish.set()
        await asyncio.wait_for(task, 5)

    with caplog.at_level("INFO", logger="shared"):
        asyncio.run(run_watch())

    live_logs = [
        r.getMessage()
        for r in caplog.records
        if r.levelname == "INFO" and r.getMessage().startswith("Live now")
    ]
    # creator_b waited in queue because live_max=1, yet "Live now" logged only once
    assert live_logs == ["Live now (2): creator_a, creator_b"]


def test_failed_polls_warn_once_per_failure_streak(monkeypatch, onlyfans_settings, caplog):
    onlyfans_settings(live_watch=True, live_interval=10)
    install_session(monkeypatch, Client(Response(404)))

    outcomes = iter([
        RuntimeError("network down"),
        RuntimeError("network down"),
        [],
        RuntimeError("network down again"),
    ])
    stop = asyncio.Event()

    async def fake_online(c, checks=None):
        try:
            item = next(outcomes)
        except StopIteration:
            stop.set()
            return []
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(live, "get_online_streams", fake_online)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: True)

    class FastWatcher(shared.LiveWatcher):
        def __init__(self, fetch_online, record, **kwargs):
            super().__init__(
                fetch_online,
                record,
                max_concurrent=kwargs.get("max_concurrent", 2),
                interval=0.01,
                jitter=0,
                once=kwargs.get("once", False),
            )

    monkeypatch.setattr(shared, "LiveWatcher", FastWatcher)

    with caplog.at_level("WARNING", logger="shared"):
        asyncio.run(asyncio.wait_for(live.run(True, stop), timeout=5))

    warnings = [
        r.getMessage()
        for r in caplog.records
        if r.levelname == "WARNING" and "OnlyFans livestream check failed:" in r.getMessage()
    ]
    assert warnings == [
        "OnlyFans livestream check failed: network down",
        "OnlyFans livestream check failed: network down again",
    ]




def test_live_options_and_type_options_override_onlyfans_path(monkeypatch, tmp_path):
    import ofscraper.utils.config.file as config_file

    when = datetime.datetime(2026, 11, 23, 8, 5, 9, tzinfo=datetime.timezone.utc)
    cfg = {
        "live_options": {
            "save_location": str(tmp_path / "live_root"),
            "dir_format": "{sitename}/streams/{model_username}",
            "file_format": "rec_{model_username}_{date}",
        },
        "type_options": {},
    }
    monkeypatch.setattr(config_file, "open_config", lambda: cfg)
    assert live.recording_path(tmp_path, "creator_a", when) == (
        tmp_path / "live_root" / "OnlyFans" / "streams" / "creator_a" / "rec_creator_a_20261123_080509.webm"
    )

    cfg["type_options"] = {
        "livestreams": {
            "save_location": str(tmp_path / "type_live"),
            "dir_format": "{model_username}/VODs",
        }
    }
    assert live.recording_path(tmp_path, "creator_a", when) == (
        tmp_path / "type_live" / "creator_a" / "VODs" / "rec_creator_a_20261123_080509.webm"
    )
