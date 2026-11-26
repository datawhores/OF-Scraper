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
        stub = SimpleNamespace(**{**dict(real), "site": "onlyfans", "usernames": None,
                                  "excluded_username": None, "live": False, "live_watch": False,
                                  "live_interval": None, "live_max": None, "live_chat": False,
                                  **values})
        monkeypatch.setattr(settings, "get_settings", lambda: stub)
        return stub

    import ofscraper.utils.auth.file as auth_file

    monkeypatch.setattr(auth_file, "read_auth", lambda: dict(AUTH))
    monkeypatch.setattr(common_paths, "get_save_location", lambda config=None: str(tmp_path))
    monkeypatch.setattr(ffmpeg_finder, "get_ffmpeg", lambda: "ffmpeg")
    return apply


def install_session(monkeypatch, client):
    @contextlib.asynccontextmanager
    async def aget_ofsession(*args, **kwargs):
        yield client

    monkeypatch.setattr(manager, "Manager",
                        SimpleNamespace(session=SimpleNamespace(aget_ofsession=aget_ofsession)))


def test_live_records_each_selected_live_creator_once(monkeypatch, onlyfans_settings, tmp_path):
    onlyfans_settings(live=True, usernames=["creator_a", "creator_d"])
    install_session(monkeypatch, Client(Response(200, {"isActive": False})))

    async def online(c):
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

    async def online(c):
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
