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
            session=SimpleNamespace(aget_ofsession=aget_ofsession),
            model_manager=model_manager,
        ),
    )


def test_live_records_each_selected_live_creator_once(monkeypatch, onlyfans_settings, tmp_path):
    onlyfans_settings(live=True, usernames=["creator_a", "creator_d"])
    install_session(monkeypatch, Client(Response(200, {"isActive": False})))

    async def online(c, checks=None):
        return live.live_subscriptions([[
            {"id": 1, "username": "creator_a", "hasStream": True},
            {"id": 2, "username": "creator_b", "hasStream": True},
            {"id": 4, "username": "creator_d", "hasStream": True},
        ]])

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
        ("creator_a", folder / "creator_a" / "Livestreams", "s" * 30, "ffmpeg", False),
        ("creator_d", folder / "creator_d" / "Livestreams", "s" * 30, "ffmpeg", False),
    ]
    assert len(reads) == 2  # auth.json is read for each recording


def test_a_missing_chromium_says_how_to_install_it(monkeypatch, onlyfans_settings, caplog):
    onlyfans_settings(live=True)
    install_session(monkeypatch, Client(Response(404)))

    async def online(c, checks=None):
        return [{"accountId": 1, "username": "creator_a"}, {"accountId": 2, "username": "creator_b"}]

    def capture(**kwargs):
        raise live_capture.BrowserMissing(live_capture.INSTALL_HINT)

    monkeypatch.setattr(live, "get_online_streams", online)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: True)
    monkeypatch.setattr(live_capture, "capture", capture)
    with caplog.at_level("WARNING", logger="shared"):
        asyncio.run(live.run(False, asyncio.Event()))
    # two creators tried, one warning: --live-watch would otherwise repeat it every poll
    warnings = [r for r in caplog.records if r.levelname == "WARNING" and "playwright install chromium" in r.getMessage()]
    assert len(warnings) == 1


def test_without_playwright_it_says_how_to_install_and_records_nothing(monkeypatch, onlyfans_settings, caplog):
    import builtins

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
    assert 'pip install "ofscraper-community[live]"' in caplog.text
    assert "playwright install chromium" in caplog.text


def test_live_chat_is_fansly_only(monkeypatch, onlyfans_settings, caplog):
    onlyfans_settings(live=True, live_chat=True)
    monkeypatch.setattr(live_capture, "playwright_ready", lambda: False)
    with caplog.at_level("WARNING", logger="shared"):
        asyncio.run(live.run(False, asyncio.Event()))
    assert "--live-chat only applies to Fansly" in caplog.text


# ------------------------------------------------------------------ search, caching & logging

def test_without_username_and_filters_it_scans_active_subscriptions(monkeypatch, onlyfans_settings):
    import ofscraper.data.api.subscriptions.subscriptions as subs
    import ofscraper.data.models.utils.retriver as retriver

    onlyfans_settings(live=True, usernames=None, excluded_username=None)
    used = []

    async def fake_active(c):
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
def test_with_username_individual_uses_retriver_and_checks_session(
    monkeypatch, onlyfans_settings, search_mode
):
    import ofscraper.data.models.utils.retriver as retriver
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

    monkeypatch.setattr(retriver, "get_models", fake_get_models)
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
    import ofscraper.data.models.utils.retriver as retriver
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

    async def fake_active(c):
        batch_calls.append(1)
        yield [
            {"id": 1, "username": "creator_a", "hasStream": True},
            {"id": 2, "username": "creator_b", "hasStream": True},
        ]

    monkeypatch.setattr(retriver, "get_models", fake_get_models)
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    main_client = Client(Response(200, {}))
    checks_client = Client(Response(200, {}))

    token = live._TARGET_CACHE.set({})
    try:
        assert asyncio.run(live.get_online_streams(main_client, checks=checks_client)) == []
        assert asyncio.run(live.get_online_streams(main_client, checks=checks_client)) == [
            {"accountId": 1, "username": "creator_a"}
        ]
    finally:
        live._TARGET_CACHE.reset(token)

    assert len(retriver_calls) == 1
    assert len(batch_calls) == 1
    assert checks_client.urls == []


def test_target_creators_are_resolved_once_across_watch_polls(monkeypatch, onlyfans_settings):
    import ofscraper.data.models.utils.retriver as retriver
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

    monkeypatch.setattr(retriver, "get_models", fake_get_models)
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
    import ofscraper.data.models.utils.retriver as retriver
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

    async def fake_active(c):
        batch_calls.append(1)
        yield [
            {"id": 1, "username": "creator_a", "hasStream": True},
            {"id": 2, "username": "creator_b", "hasStream": True},
        ]

    monkeypatch.setattr(retriver, "get_models", fake_get_models)
    monkeypatch.setattr(ModelManager, "filter_models", fake_filter_models)
    monkeypatch.setattr(subs, "scrape_subscriptions_active", fake_active)
    main_client = Client(Response(200, {}))
    checks_client = Client(Response(200, {}))

    token = live._TARGET_CACHE.set({})
    try:
        assert asyncio.run(live.get_online_streams(main_client, checks=checks_client)) == []
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


def test_concurrent_individual_checks_respect_env_concurrency_and_stream_url(
    monkeypatch, onlyfans_settings
):
    import ofscraper.data.models.utils.retriver as retriver
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

        monkeypatch.setattr(retriver, "get_models", fake_get_models)

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
