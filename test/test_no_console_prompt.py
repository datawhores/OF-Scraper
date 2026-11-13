"""No prompt opens when there's no one to answer it (#286).

With no interactive console (output redirected, a scheduled run, a run started
from another program) a prompt can't open: prompt_toolkit raised
NoConsoleScreenBufferError on Windows and the run ended in a traceback. The
first place a scrape run hit it was the "rescan account for users" question
after a scan that found no creators.
"""

import copy
import io
import logging
import queue
from types import SimpleNamespace

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.commands.scraper.scraper as scraper
import ofscraper.main.open.run as run
import ofscraper.managers.model as model
import ofscraper.prompts.promptConvert as promptConvert
import ofscraper.prompts.prompt_groups.misc as misc
import ofscraper.utils.interactive as interactive


@pytest.fixture
def records():
    """Collect what the "shared" logger records at ERROR and above."""
    found = []
    handler = logging.Handler(level=logging.ERROR)
    handler.emit = found.append
    logger = logging.getLogger("shared")
    logger.addHandler(handler)
    yield found
    logger.removeHandler(handler)


def _empty_scan_manager(monkeypatch, daemon=None, console=True):
    """A ModelManager whose scans find no creators."""
    mm = model.ModelManager()
    scans = []

    def scan(all_main_models=False):
        scans.append(1)
        mm._last_fetched = []

    monkeypatch.setattr(mm, "_fetch_all_subs_async", scan)
    monkeypatch.setattr(
        model.settings, "get_settings", lambda: SimpleNamespace(daemon=daemon)
    )
    monkeypatch.setattr(interactive, "is_interactive", lambda: console)
    return mm, scans


def _retry_prompt_must_not_open(monkeypatch):
    def fail():
        raise AssertionError("the retry prompt opened")

    monkeypatch.setattr(model.prompts, "retry_user_scan", fail)


# --- the retry prompt (#286's checks) ---------------------------------------


def test_no_console_no_creators_raises_without_prompting(monkeypatch):
    mm, scans = _empty_scan_manager(monkeypatch, console=False)
    _retry_prompt_must_not_open(monkeypatch)
    with pytest.raises(model.NoCreatorsFound) as info:
        mm._fetch_all_subs(force_refetch=True)
    assert scans == [1]
    assert "No creators were found" in str(info.value)
    assert "no interactive console" in str(info.value)


@pytest.mark.parametrize("daemon", [None, False])
def test_no_console_no_creators_exits_1_with_a_clear_message(monkeypatch, records, daemon):
    """Outside daemon mode, an empty scan with no console still exits 1."""
    mm, _ = _empty_scan_manager(monkeypatch, daemon=daemon, console=False)
    _retry_prompt_must_not_open(monkeypatch)
    monkeypatch.setattr(run, "start_manager", lambda: mm._fetch_all_subs(True))
    monkeypatch.setattr(run.exit_manager, "shutdown", lambda: None)
    with pytest.raises(SystemExit) as exit_info:
        run.main()
    assert exit_info.value.code == 1
    messages = [r.getMessage() for r in records]
    assert any("No creators were found" in m for m in messages)
    # the message, not a traceback
    assert not any("Traceback" in m for m in messages)


def test_console_still_offers_the_retry_prompt(monkeypatch):
    mm, scans = _empty_scan_manager(monkeypatch, console=True)
    answers = iter([True, False])
    asked = []

    def retry():
        asked.append(1)
        return next(answers)

    monkeypatch.setattr(model.prompts, "retry_user_scan", retry)
    mm._fetch_all_subs(force_refetch=True)  # declining still returns normally
    assert asked == [1, 1]
    assert scans == [1, 1]


@pytest.mark.parametrize("console", [True, False])
def test_daemon_never_prompts(monkeypatch, records, console):
    """An empty scan can be a swallowed network error: log it, don't end the daemon."""
    mm, scans = _empty_scan_manager(monkeypatch, daemon=5, console=console)
    _retry_prompt_must_not_open(monkeypatch)
    mm._fetch_all_subs(force_refetch=True)
    assert scans == [1]
    assert mm.all_subs == []
    assert any("No creators were found" in r.getMessage() for r in records)


def test_creators_found_needs_no_prompt(monkeypatch):
    mm, _ = _empty_scan_manager(monkeypatch, console=False)
    _retry_prompt_must_not_open(monkeypatch)

    def scan(all_main_models=False):
        mm._last_fetched = [model.Model({"id": 1, "username": "a"})]

    monkeypatch.setattr(mm, "_fetch_all_subs_async", scan)
    mm._fetch_all_subs(force_refetch=True)
    assert [m.name for m in mm.all_subs] == ["a"]


# --- the daemon loop ----------------------------------------------------------


class _Wakeup:
    stopped = False

    def install(self):
        pass

    def restore(self):
        pass


def _daemon_loop(monkeypatch, runner, model_manager=None, run_settings=None):
    """Run daemon_process with ``runner`` as each pass; returns the job queue."""
    jobs = queue.Queue()
    monkeypatch.setattr(scraper, "jobqueue", jobs)
    monkeypatch.setattr(scraper.exit, "sigterm_as_keyboard_interrupt", lambda: None)
    monkeypatch.setattr(scraper.checkers, "check_auth", lambda: None)
    monkeypatch.setattr(scraper.actions, "select_areas", lambda: None)
    monkeypatch.setattr(scraper.live, "watch_enabled", lambda: False)
    monkeypatch.setattr(scraper, "set_schedule", lambda *a, **k: None)
    run_settings = run_settings or SimpleNamespace(output_level="NORMAL")
    monkeypatch.setattr(scraper.settings, "get_settings", lambda: run_settings)
    monkeypatch.setattr(
        scraper.manager,
        "Manager",
        SimpleNamespace(
            current_model_manager=model_manager
            or SimpleNamespace(sync_models=lambda: None)
        ),
    )
    monkeypatch.setattr(scraper, "scraperManager", lambda: SimpleNamespace(runner=runner))
    monkeypatch.setattr(scraper, "DaemonWakeup", _Wakeup)
    return jobs


def test_daemon_stops_when_a_prompt_has_no_console(monkeypatch):
    """A prompt no one can answer won't be answered next pass, so the daemon ends."""

    def runner():
        raise interactive.NoConsoleError("no console")

    _daemon_loop(monkeypatch, runner)
    with pytest.raises(interactive.NoConsoleError):
        scraper.daemon_process()


@pytest.mark.parametrize("usernames", [["ALL"], []])
@pytest.mark.parametrize("console", [True, False])
def test_daemon_retries_after_an_empty_startup_scan(monkeypatch, records, console, usernames):
    """
    The first scan finds no creators (say a network error the fetch swallowed).
    The daemon logs it, keeps running, and the next pass scans again.
    """
    mm = model.ModelManager()
    scans = []

    def scan(all_main_models=False):
        scans.append(1)
        found = [model.Model({"id": 1, "username": "a"})] if len(scans) > 1 else []
        mm._last_fetched = found

    monkeypatch.setattr(mm, "_fetch_all_subs_async", scan)
    monkeypatch.setattr(mm, "sync_models", lambda: None)
    # the filters aren't what's tested here: they keep everyone
    monkeypatch.setattr(mm, "_filtered_models", lambda: dict(mm._all_subs_dict))
    monkeypatch.setattr(interactive, "is_interactive", lambda: console)
    _retry_prompt_must_not_open(monkeypatch)

    def fail(*args, **kwargs):
        raise AssertionError("a prompt opened")

    monkeypatch.setattr(model.prompts, "decide_filters_menu", fail)
    # without -u the first non-empty pass asks which creators to scrape, as before;
    # the answer here is "all of them"
    monkeypatch.setattr(
        model.retriver, "get_selected_model", lambda models, selected: models
    )

    selections = []

    def runner():
        selections.append([m.name for m in mm.prepare_scraper_activity()])
        if len(selections) == 1:
            jobs.put(runner)
        else:
            raise KeyboardInterrupt

    run_settings = SimpleNamespace(
        output_level="NORMAL", daemon=5, usernames=usernames, actions=["download"],
        command="main",
    )
    jobs = _daemon_loop(monkeypatch, runner, model_manager=mm, run_settings=run_settings)
    args = copy.copy(model.settings.get_args())
    args.daemon = 5
    monkeypatch.setattr(model.settings, "get_args", lambda: args)
    with pytest.raises(KeyboardInterrupt):
        scraper.daemon_process()
    assert scans == [1, 1]
    assert selections == [[], ["a"]]
    assert any("No creators were found" in r.getMessage() for r in records)


def test_daemon_keeps_going_after_an_ordinary_error(monkeypatch):
    """Other errors still leave the daemon running for its next pass."""
    logged = []
    calls = []

    def runner():
        calls.append(1)
        if len(calls) == 1:
            jobs.put(runner)
            raise RuntimeError("a bad pass")
        raise KeyboardInterrupt

    jobs = _daemon_loop(monkeypatch, runner)
    monkeypatch.setattr(
        scraper,
        "log",
        SimpleNamespace(
            info=lambda *a, **k: None, warning=logged.append, traceback_=logged.append
        ),
    )
    with pytest.raises(KeyboardInterrupt):
        scraper.daemon_process()
    assert calls == [1, 1]
    assert "Daemon pass failed: RuntimeError: a bad pass" in logged


# --- every other prompt ------------------------------------------------------


def test_prompts_refuse_to_open_without_a_console(monkeypatch):
    monkeypatch.setattr(interactive, "is_interactive", lambda: False)
    built = []

    @promptConvert.wrapper
    def fake_prompt(*args, **kwargs):
        built.append(1)
        raise AssertionError("the prompt was built")

    with pytest.raises(interactive.NoConsoleError) as info:
        fake_prompt(message="Rescan account for users")
    assert built == []
    assert "Rescan account for users" in str(info.value)


def test_press_enter_refuses_to_wait_without_a_console(monkeypatch):
    monkeypatch.setattr(interactive, "is_interactive", lambda: False)

    def fail(questions):
        raise AssertionError("the prompt opened")

    monkeypatch.setattr(misc, "prompt", fail)
    with pytest.raises(interactive.NoConsoleError):
        misc.press_enter_to_continue()


def test_no_console_error_exits_1_with_a_clear_message(monkeypatch, records):
    monkeypatch.setattr(interactive, "is_interactive", lambda: False)

    @promptConvert.wrapper
    def fake_prompt(*args, **kwargs):
        raise AssertionError("the prompt was built")

    monkeypatch.setattr(run, "start_manager", lambda: fake_prompt(message="Pick one"))
    monkeypatch.setattr(run.exit_manager, "shutdown", lambda: None)
    with pytest.raises(SystemExit) as exit_info:
        run.main()
    assert exit_info.value.code == 1
    assert any("no interactive console" in r.getMessage() for r in records)


# --- loops that asked again after any error ----------------------------------


class _AskedAgain(BaseException):
    """Escapes the `except Exception` retry loops so the old code can't hang."""


def _no_console_once():
    calls = []

    def ask(*args, **kwargs):
        calls.append(1)
        if len(calls) > 1:
            raise _AskedAgain
        raise interactive.NoConsoleError("no console")

    return ask


def test_main_menu_stops_instead_of_asking_again(monkeypatch):
    import ofscraper.utils.menu as menu

    monkeypatch.setattr(menu.prompts, "main_prompt", _no_console_once())
    with pytest.raises(interactive.NoConsoleError):
        menu.main_menu_action()


def test_broken_config_stops_instead_of_asking_again(monkeypatch, tmp_path):
    import ofscraper.utils.config.utils.context as context

    config = tmp_path / "config.json"
    config.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(context.common_paths, "get_config_path", lambda: config)
    monkeypatch.setattr(context.prompts, "reset_config_prompt", _no_console_once())
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    with pytest.raises(interactive.NoConsoleError):
        with context.config_context():
            pass


def test_broken_auth_stops_instead_of_asking_again(monkeypatch):
    import json

    import ofscraper.utils.auth.utils.error as error

    monkeypatch.setattr(error.prompts, "reset_auth_prompt", _no_console_once())
    monkeypatch.setattr(error, "console", SimpleNamespace(print=lambda *a, **k: None))
    with pytest.raises(interactive.NoConsoleError):
        error.handle_auth_errors(json.JSONDecodeError("bad", "{", 0))


# --- is_interactive ----------------------------------------------------------


class _Stream(io.StringIO):
    def __init__(self, tty):
        super().__init__()
        self._tty = tty

    def isatty(self):
        if self.closed:
            raise ValueError("I/O operation on closed file")
        return self._tty


@pytest.mark.parametrize(
    "stdin, stdout, windows, others",
    [
        (_Stream(True), _Stream(True), True, True),
        (_Stream(False), _Stream(True), False, False),
        # `| tee` or `> file`: prompt_toolkit needs a console on stdout only on
        # Windows; elsewhere it falls back to plain text
        (_Stream(True), _Stream(False), False, True),
        (None, _Stream(True), False, False),  # pythonw, or a closed handle
        (_Stream(True), None, False, True),
    ],
)
@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_is_interactive_needs_stdin_on_a_terminal_and_stdout_on_windows(
    monkeypatch, platform, stdin, stdout, windows, others
):
    monkeypatch.setattr(interactive.sys, "platform", platform)
    monkeypatch.setattr(interactive.sys, "stdin", stdin)
    monkeypatch.setattr(interactive.sys, "stdout", stdout)
    expected = windows if platform == "win32" else others
    assert interactive.is_interactive() is expected


@pytest.mark.parametrize("platform", ["win32", "linux"])
@pytest.mark.parametrize("which", ["stdin", "stdout"])
def test_is_interactive_treats_a_closed_stream_as_no_console(monkeypatch, platform, which):
    monkeypatch.setattr(interactive.sys, "platform", platform)
    monkeypatch.setattr(interactive.sys, "stdin", _Stream(True))
    monkeypatch.setattr(interactive.sys, "stdout", _Stream(True))
    closed = _Stream(True)
    closed.close()
    monkeypatch.setattr(interactive.sys, which, closed)
    # stdout is only checked on Windows
    expected = which == "stdout" and platform != "win32"
    assert interactive.is_interactive() is expected
