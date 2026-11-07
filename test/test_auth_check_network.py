import json
import logging
import queue
from types import SimpleNamespace

import httpx
import pytest

import ofscraper.commands.scraper.scraper as scraper
import ofscraper.data.api.init as init
import ofscraper.main.open.run as run
import ofscraper.utils.checkers as checkers


class AuthPrompted(Exception):
    pass


@pytest.fixture
def fail_auth_check(monkeypatch):
    """Make the /me request in the real auth check fail with the given error."""
    monkeypatch.setattr(
        init.settings,
        "get_settings",
        lambda: SimpleNamespace(anon=False, output_level="NORMAL"),
    )
    monkeypatch.setattr(checkers.auth_file, "read_auth", lambda: {})
    # traceback_ is added to loggers by the app's log setup
    monkeypatch.setattr(init.log, "traceback_", lambda *a, **k: None, raising=False)

    def make_auth(*args, **kwargs):
        raise AuthPrompted

    monkeypatch.setattr(checkers.make, "make_auth", make_auth)
    calls = []

    def set_error(error):
        def scrape_user():
            calls.append(1)
            raise error

        monkeypatch.setattr(init.me, "scrape_user", scrape_user)
        return calls

    return set_error


def _request(url):
    return httpx.Request("GET", url)


def _status_error(status, url="https://onlyfans.com/api2/v2/users/me"):
    request = _request(url)
    return httpx.HTTPStatusError(
        "error", request=request, response=httpx.Response(status, request=request)
    )


TIMEOUT = httpx.ConnectTimeout(
    "timed out", request=_request("https://raw.githubusercontent.com/rules.json")
)


@pytest.mark.parametrize(
    "error,message",
    [
        (TIMEOUT, "Couldn't reach raw.githubusercontent.com (timed out)"),
        (
            httpx.ConnectError(
                "connection refused",
                request=_request("https://onlyfans.com/api2/v2/users/me"),
            ),
            "Couldn't reach onlyfans.com (connection failed)",
        ),
        (_status_error(429), "onlyfans.com is rate limiting requests"),
        (_status_error(500), "onlyfans.com returned 500: the server had an error"),
        (_status_error(502), "onlyfans.com returned 502: the server had an error"),
        (
            _status_error(500, "https://raw.githubusercontent.com/rules.json"),
            "raw.githubusercontent.com returned 500: the server had an error",
        ),
        (
            json.JSONDecodeError("Expecting value", "<html>Sign in</html>", 0),
            "Got a reply that isn't JSON",
        ),
    ],
)
def test_network_and_server_errors_do_not_ask_for_auth(
    fail_auth_check, caplog, error, message
):
    fail_auth_check(error)
    with caplog.at_level(logging.INFO, logger="shared"):
        with pytest.raises(checkers.AuthCheckUnavailable):
            checkers.check_auth()

    assert message in caplog.text
    assert "Auth Failed" not in caplog.text


@pytest.mark.parametrize("status", [400, 401, 403])
def test_rejected_auth_still_asks_for_auth(fail_auth_check, caplog, status):
    fail_auth_check(_status_error(status))
    with caplog.at_level(logging.INFO, logger="shared"):
        with pytest.raises(AuthPrompted):
            checkers.check_auth()

    assert "Auth Failed" in caplog.text
    assert "Couldn't reach" not in caplog.text
    assert "the server had an error" not in caplog.text


class InterruptWhenIdle(queue.Queue):
    # stop the daemon once it has run every queued pass
    def get(self, *args, **kwargs):
        if self.empty():
            raise KeyboardInterrupt
        return super().get(*args, **kwargs)


def test_daemon_keeps_running_after_a_network_failure(
    fail_auth_check, monkeypatch, caplog
):
    calls = fail_auth_check(TIMEOUT)
    jobs = InterruptWhenIdle()
    # the real scraper runner for every pass; the daemon queues one more itself
    jobs.put(scraper.scraperManager().runner)
    jobs.put(scraper.scraperManager().runner)
    monkeypatch.setattr(scraper, "jobqueue", jobs)
    monkeypatch.setattr(scraper.exit, "sigterm_as_keyboard_interrupt", lambda: None)
    # the start-up check passes; the network fails on each scheduled pass,
    # where the runner calls the real check
    real_check = checkers.check_auth
    monkeypatch.setattr(scraper.checkers, "check_auth", lambda: None)
    monkeypatch.setattr(scraper, "check_auth", real_check)
    monkeypatch.setattr(scraper.log, "traceback_", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(
        scraper.manager,
        "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(sync_models=lambda: None)),
    )
    monkeypatch.setattr(scraper.actions, "select_areas", lambda: None)
    monkeypatch.setattr(scraper, "set_schedule", lambda *args, **kwargs: None)

    # only the idle interrupt ends the loop, not the failed passes
    with caplog.at_level(logging.INFO, logger="shared"):
        with pytest.raises(KeyboardInterrupt):
            scraper.daemon_process()
    assert len(calls) == 3
    assert "Auth Failed" not in caplog.text
    assert jobs.unfinished_tasks == 0


def test_one_off_run_shuts_down_cleanly_after_a_network_failure(
    fail_auth_check, monkeypatch, caplog
):
    fail_auth_check(TIMEOUT)
    shutdowns = []
    monkeypatch.setattr(run, "start_manager", lambda: scraper.scraperManager().runner())
    monkeypatch.setattr(run.exit_manager, "shutdown", lambda: shutdowns.append(1))

    with caplog.at_level(logging.INFO, logger="shared"):
        try:
            run.main()
        except SystemExit as e:
            # a run that fails may exit with status 1 once #149 lands
            assert e.code == 1
    assert shutdowns == [1]
    assert "Couldn't reach raw.githubusercontent.com (timed out)" in caplog.text
