"""Alerts (main/close/alerts.py): sent when something needs a person, once per
change of state, to Discord and alert_script."""

import json
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.main.close.alerts as alerts
import ofscraper.main.close.exit_status as exit_status
import ofscraper.main.close.final.run_record as run_record
import ofscraper.utils.checkers as checkers
import ofscraper.utils.system.free as free
import ofscraper.commands.utils.command as command


@pytest.fixture
def sent(monkeypatch, tmp_path):
    """Alerts as they'd reach Discord and alert_script."""
    script = tmp_path / "alert.py"
    script.write_text("", encoding="utf-8")
    s = SimpleNamespace(discord_level="LOW", alert_script=str(script), site="onlyfans", system_free_min=0)
    monkeypatch.setattr(alerts.settings, "get_settings", lambda: s)
    monkeypatch.setattr(free.settings, "get_settings", lambda: s)
    import ofscraper.utils.profiles.data as profile_data

    monkeypatch.setattr(profile_data, "get_active_profile", lambda: "main_profile")
    out = SimpleNamespace(discord=[], script=[], settings=s)
    monkeypatch.setattr(run_record, "send_discord", lambda text: out.discord.append(text))
    import ofscraper.utils.system.subprocess as subprocess_

    monkeypatch.setattr(subprocess_, "run", lambda cmd, input=None, **k: out.script.append(json.loads(input)))
    alerts.reset()
    exit_status.reset()
    checkers.new_pass()
    yield out
    alerts.reset()
    exit_status.reset()


def test_alert_reaches_discord_and_the_script(sent):
    assert alerts.failing(alerts.LOGIN, "OnlyFans rejected the login; update the auth")
    assert sent.discord == ["⚠️ OnlyFans, main_profile: OnlyFans rejected the login; update the auth"]
    assert sent.script == [{
        "kind": "login", "message": "OnlyFans rejected the login; update the auth",
        "site": "onlyfans", "profile": "main_profile",
    }]


@pytest.mark.parametrize("level", ["LOW", "NORMAL", "DEBUG"])
def test_alert_reaches_discord_once(monkeypatch, level):
    # the alert's log line goes through the same Discord handler as the alert
    import logging
    import queue

    import ofscraper.utils.logs.utils.level as log_level
    import ofscraper.utils.profiles.data as profile_data
    from ofscraper.utils.logs.classes.classes import DiscordFormatter
    from ofscraper.utils.logs.classes.handlers.discord import DiscordHandler

    s = SimpleNamespace(discord_level=level, alert_script=None, site="onlyfans")
    monkeypatch.setattr(alerts.settings, "get_settings", lambda: s)
    monkeypatch.setattr(profile_data, "get_active_profile", lambda: "main_profile")
    handler = DiscordHandler.__new__(DiscordHandler)
    logging.Handler.__init__(handler)
    handler.close = lambda: logging.Handler.close(handler)
    handler.queue = queue.Queue()
    handler.setFormatter(DiscordFormatter("%(message)s"))
    handler.setLevel(log_level.getLevel(level))
    monkeypatch.setattr(handler, "_tasks", [], raising=False)
    shared = logging.getLogger("shared")
    shared.addHandler(handler)
    alerts.reset()
    try:
        alerts.failing(alerts.LOGIN, "OnlyFans rejected the login; update the auth")
    finally:
        shared.removeHandler(handler)
        alerts.reset()
    messages = []
    while not handler.queue.empty():
        messages.append(handler.queue.get())
    assert len(messages) == 1
    assert "rejected the login" in messages[0]


def test_no_discord_when_off_and_no_script_when_unset(sent):
    sent.settings.discord_level = "OFF"
    sent.settings.alert_script = None
    assert alerts.failing(alerts.DISK_FULL, "full")
    assert sent.discord == [] and sent.script == []


def test_summary_level_still_gets_alerts(sent):
    sent.settings.discord_level = "SUMMARY"
    alerts.failing(alerts.LOGIN, "rejected")
    assert len(sent.discord) == 1


def test_daemon_three_failing_passes_give_one_alert_then_one_recovered(sent):
    for _ in range(3):
        alerts.after_pass(exit_status.ERROR)
    assert len(sent.script) == 1 and sent.script[0]["kind"] == "daemon_pass"
    assert "unexpected error" in sent.script[0]["message"]
    alerts.after_pass(exit_status.OK)
    alerts.after_pass(exit_status.OK)
    assert len(sent.script) == 2 and "finishing again" in sent.script[1]["message"]


def test_daemon_partial_pass_is_not_an_alert(sent):
    alerts.after_pass(exit_status.PARTIAL)
    alerts.after_pass(exit_status.OK)
    assert sent.script == []


def test_login_failed_pass_gives_only_the_login_alert(sent):
    alerts.failing(alerts.LOGIN, "rejected")
    alerts.after_pass(exit_status.AUTH)
    assert [a["kind"] for a in sent.script] == ["login"]


def test_free_space_limit_alerts_once(sent, monkeypatch):
    sent.settings.system_free_min = 10
    monkeypatch.setattr(free, "get_free", lambda *a: 5)
    download = free.space_checker(lambda: "downloaded")
    for _ in range(2):
        with pytest.raises(Exception, match="Space min"):
            download()
    assert [a["kind"] for a in sent.script] == ["disk_full"]
    sent.settings.system_free_min = 0
    assert download() == "downloaded"


def test_free_space_limit_during_a_download_alerts(sent, monkeypatch):
    # the per-file check in the download manager, not only the decorator
    from ofscraper.commands.scraper.actions.download.managers.downloadmanager import (
        DownloadManager,
    )

    sent.settings.system_free_min = 10
    monkeypatch.setattr(free, "get_free", lambda *a: 5)
    with pytest.raises(Exception):
        DownloadManager(ctx=object())._downloadspace()
    assert [a["kind"] for a in sent.script] == ["disk_full"]


def test_disk_still_full_after_a_partial_pass_isnt_recovered(sent, monkeypatch):
    sent.settings.system_free_min = 10
    free_bytes = [5]
    monkeypatch.setattr(free, "get_free", lambda *a: free_bytes[0])
    download = free.space_checker(lambda: "downloaded")
    for _ in range(3):  # three daemon passes, the disk full throughout
        with pytest.raises(Exception, match="Space min"):
            download()
        alerts.after_pass(exit_status.PARTIAL)
    assert [a["kind"] for a in sent.script] == ["disk_full"]
    free_bytes[0] = 50  # space was freed
    alerts.after_pass(exit_status.OK)
    assert [a["kind"] for a in sent.script] == ["disk_full", "disk_full"]
    assert "running again" in sent.script[1]["message"]


# --- the login, at the start and mid-run ------------------------------------


def test_rejected_login_at_start_alerts_before_the_prompt(sent, monkeypatch):
    statuses = iter([("DOWN", None), ("UP", None)])
    monkeypatch.setattr(checkers.init, "auth_status", lambda: next(statuses))
    monkeypatch.setattr(checkers.sites, "is_fansly", lambda: False)
    order = []
    monkeypatch.setattr(alerts, "_send", lambda kind, message: order.append(("alert", kind, message)))
    monkeypatch.setattr(
        checkers.make, "make_auth", lambda **k: order.append(("prompt",)) or (None, "continue")
    )
    monkeypatch.setattr(checkers.auth_file, "read_auth", lambda: {})
    checkers.check_auth()
    assert order == [
        ("alert", "login", "OnlyFans rejected the login; update the auth"),
        ("prompt",),
        ("alert", "login", "OnlyFans login works again"),
    ]


class Forbidden(Exception):
    def __init__(self, status):
        super().__init__(f"{status} error")
        self.response = SimpleNamespace(status_code=status)


@pytest.mark.parametrize("status", [401, 403])
def test_creator_failing_with_rejected_login_stops_the_pass(sent, monkeypatch, status):
    asked = []
    monkeypatch.setattr(checkers.init, "auth_status", lambda: asked.append(1) or ("DOWN", None))
    monkeypatch.setattr(checkers.sites, "is_fansly", lambda: False)
    with pytest.raises(checkers.LoginRejected):
        command.log_user_failure("a creator", Forbidden(status))
    assert asked == [1]
    assert exit_status.code() == exit_status.AUTH
    assert [a["kind"] for a in sent.script] == ["login"]


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def test_rejected_login_stops_the_creator_loop(sent, monkeypatch):
    # the creator loop catches every error a creator raises; a rejected login
    # must still end the run, not carry on with the next creator
    import asyncio

    monkeypatch.setattr(checkers.init, "auth_status", lambda: ("DOWN", None))
    monkeypatch.setattr(checkers.sites, "is_fansly", lambda: False)
    monkeypatch.setattr(command.log, "traceback_", lambda *a: None, raising=False)
    tried = []

    async def process_user(self, ele, c, action_func):
        tried.append(ele.name)
        try:
            raise Forbidden(401)
        except Forbidden as e:  # as scraper.py's action loop does
            command.log_user_failure(ele.name, e, what="download")

    monkeypatch.setattr(command.CommandManager, "_process_user", process_user)
    users = [SimpleNamespace(name="a creator"), SimpleNamespace(name="another creator")]
    with pytest.raises(checkers.LoginRejected):
        asyncio.run(command.CommandManager()._process_users_normal(users, _Session(), None))
    assert tried == ["a creator"]
    assert exit_status.code() == exit_status.AUTH


def test_rejected_login_in_an_area_stops_the_scan(sent, monkeypatch):
    import asyncio
    import ofscraper.data.posts.post as post

    monkeypatch.setattr(checkers.init, "auth_status", lambda: ("DOWN", None))
    monkeypatch.setattr(checkers.sites, "is_fansly", lambda: False)
    monkeypatch.setattr(post.log, "traceback_", lambda *a: None, raising=False)

    async def timeline():  # an area catches its own errors, as post.py's do
        try:
            raise Forbidden(401)
        except Forbidden as e:
            post.log_area_failure("a creator", "Timeline", e)

    task = post.process_single_task(timeline, username="a creator", area="Timeline")
    with pytest.raises(checkers.LoginRejected):
        asyncio.run(task(sem=asyncio.Semaphore(1)))
    assert [a["kind"] for a in sent.script] == ["login"]


def test_creator_failing_with_a_block_carries_on(sent, monkeypatch):
    asked = []
    monkeypatch.setattr(checkers.init, "auth_status", lambda: asked.append(1) or ("UP", None))
    command.log_user_failure("a creator", Forbidden(403))
    command.log_user_failure("another creator", Forbidden(403))
    assert asked == [1]  # once a pass
    assert sent.script == [] and exit_status.code() == exit_status.PARTIAL


def _me_answers(sent, monkeypatch, status):
    """The real auth check, with /me answering this HTTP status."""
    import httpx

    request = httpx.Request("GET", "https://onlyfans.com/api2/v2/users/me")
    error = httpx.HTTPStatusError(
        "error", request=request, response=httpx.Response(status, request=request)
    )

    def scrape_user():
        raise error

    sent.settings.anon = False
    monkeypatch.setattr(checkers.sites, "is_fansly", lambda: False)
    monkeypatch.setattr(checkers.init.auth_requests, "get_request_auth", lambda: None)
    monkeypatch.setattr(checkers.init.me, "scrape_user", scrape_user)
    monkeypatch.setattr(checkers.init.log, "traceback_", lambda *a, **k: None, raising=False)


@pytest.mark.parametrize("status", [403, 404])
def test_me_blocked_at_start_isnt_a_rejected_login(sent, monkeypatch, status):
    # a firewall or ban answering /me with 403 isn't fixed by new auth
    _me_answers(sent, monkeypatch, status)
    monkeypatch.setattr(checkers.make, "make_auth", lambda **k: pytest.fail("auth prompt"))
    with pytest.raises(checkers.AuthCheckUnavailable) as raised:
        checkers.check_auth()
    assert f"refused the login check with {status}" in str(raised.value)
    assert sent.script == []


def test_me_blocked_mid_run_carries_on(sent, monkeypatch):
    _me_answers(sent, monkeypatch, 403)
    command.log_user_failure("a creator", Forbidden(403))
    assert sent.script == [] and exit_status.code() == exit_status.PARTIAL


@pytest.mark.parametrize("status", [400, 401])
def test_me_rejecting_the_login_mid_run_stops_the_pass(sent, monkeypatch, status):
    _me_answers(sent, monkeypatch, status)
    with pytest.raises(checkers.LoginRejected):
        command.log_user_failure("a creator", Forbidden(403))
    assert exit_status.code() == exit_status.AUTH
    assert [a["kind"] for a in sent.script] == ["login"]


def test_other_failures_dont_ask(sent, monkeypatch):
    monkeypatch.setattr(checkers.init, "auth_status", lambda: pytest.fail("asked"))
    command.log_user_failure("a creator", RuntimeError("timeout"))
    command.log_user_failure("a creator", Forbidden(500))


def test_status_found_through_the_cause():
    try:
        try:
            raise Forbidden(401)
        except Forbidden as e:
            raise RuntimeError("fetch failed") from e
    except RuntimeError as wrapped:
        assert checkers.http_status(wrapped) == 401
    aiohttp_like = Exception("x")
    aiohttp_like.status = 403
    assert checkers.http_status(aiohttp_like) == 403
    assert checkers.http_status(ValueError("x")) is None


def test_free_space_is_only_checked_when_the_disk_alert_is_open(sent, monkeypatch):
    # a good pass with no disk-full alert open doesn't stat the disk
    checked = []
    sent.settings.system_free_min = 10
    monkeypatch.setattr(free, "get_free", lambda: checked.append(1) or 50)
    alerts.after_pass(exit_status.OK)
    assert checked == [] and sent.script == []


def test_one_off_runs_announce_the_disk_alert_recovered(sent, monkeypatch, tmp_path):
    # a --profiles child is a one-off run of its profile, its alert state in
    # that profile's status.json: a later run with room again says so
    import ofscraper.main.close.final.final as final_mod
    import ofscraper.main.close.status_file as status_file
    import ofscraper.managers.stats as stats_mod

    sent.settings.daemon = None
    status = tmp_path / "status.json"
    monkeypatch.setenv("OFSC_STATUS_FILE", str(status))
    monkeypatch.setattr(final_mod, "final_script", lambda record: None)
    monkeypatch.setattr(final_mod, "printEndValues", lambda: None)
    monkeypatch.setattr(stats_mod.StatsManager, "print_summary_by_activity", lambda self: None)
    monkeypatch.setattr(stats_mod.StatsManager, "print_global_summary", lambda self: None)
    sent.settings.system_free_min = 10
    free_bytes = [5]
    monkeypatch.setattr(free, "get_free", lambda *a: free_bytes[0])
    download = free.space_checker(lambda: "downloaded")

    def one_off_run(downloads):
        # a new process: only the status file carries the alerts over
        alerts.reset(reload=True)
        status_file.reset()
        exit_status.reset()
        sm = stats_mod.StatsManager()
        monkeypatch.setattr(
            final_mod.manager, "Manager", SimpleNamespace(stats_manager=sm, _stats_manager=sm)
        )
        run_record.start()
        for _ in range(downloads):
            try:
                download()
            except Exception:
                pass
        final_mod.final_action()

    one_off_run(1)  # hits the limit
    one_off_run(0)  # the disk is still full
    assert [a["kind"] for a in sent.script] == ["disk_full"]
    free_bytes[0] = 50
    one_off_run(1)
    assert [a["kind"] for a in sent.script] == ["disk_full", "disk_full"]
    assert "running again" in sent.script[1]["message"]
    assert "failing_alerts" not in json.loads(status.read_text(encoding="utf-8"))
    one_off_run(1)  # quiet: nothing failing, nothing recovered
    free_bytes[0] = 5
    one_off_run(1)  # full again: announced again
    assert [a["kind"] for a in sent.script] == ["disk_full", "disk_full", "disk_full"]
    alerts.reset()
    status_file.reset()


def test_a_full_type_options_disk_isnt_announced_as_recovered(sent, monkeypatch, tmp_path):
    """The limit hit on a type_options disk, while save_location's has room:
    the alert stays open until that disk has room too, instead of being
    announced as over after every pass"""
    import ofscraper.classes.placeholder as placeholder
    from ofscraper.commands.scraper.actions.download.managers.downloadmanager import DownloadManager

    main, videos = tmp_path / "main", tmp_path / "videos"
    monkeypatch.setattr(free, "_save_folders", (None, {}))  # nothing cached by other tests
    sent.settings.system_free_min = 10
    room = {main: 50, videos: 5}
    monkeypatch.setattr(free, "get_free", lambda folder=None: room[folder or main])
    monkeypatch.setattr(placeholder, "default_media_root", lambda *a, **k: main)
    monkeypatch.setattr(placeholder, "media_roots", lambda: [main, videos])
    monkeypatch.setattr(placeholder, "media_templates", lambda keys, **k: (videos, "", ""))
    monkeypatch.setattr(placeholder, "type_save_location", lambda keys: str(videos))
    clip =SimpleNamespace(responsetype="Timeline", modified_responsetype="Posts", mediatype="Videos")
    for _ in range(3):
        with pytest.raises(Exception):
            DownloadManager(ctx=object())._downloadspace(clip)
        alerts.after_pass(exit_status.PARTIAL)
    assert [a["kind"] for a in sent.script] == ["disk_full"]
    assert "saved there stopped" in sent.script[0]["message"]
    room[videos] = 50
    alerts.after_pass(exit_status.OK)
    assert "running again" in sent.script[-1]["message"]
