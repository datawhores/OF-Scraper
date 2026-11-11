"""A Yes to "redownload all files" applies to that run only (#433)."""

import queue
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.commands.scraper.scraper as scraper
import ofscraper.data.api.common.scan_range as scan_range
import ofscraper.data.api.timeline as timeline
import ofscraper.prompts.promptConvert as prompt_convert
import ofscraper.prompts.prompt_groups.actions as actions_prompt
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.config.data as config_data
import ofscraper.utils.menu as menu
import ofscraper.utils.settings as settings
from ofscraper.managers.stats import StatsManager

YEAR_2000 = arrow.get("2000")
PARTIAL = arrow.get("2024-03-01").float_timestamp
DOWNLOAD = "Download content from a user"
LIKE = "Like a selection of a user's posts"
MENU_HINT = (
    '[yellow]Hint: Full rescan: answer Yes to "Would you like to redownload'
    ' all files" (this also re-downloads files)[/yellow]'
)
NORMAL = (None, False, False)
REDOWNLOAD = (YEAR_2000, True, True)


class Recorder:
    def __init__(self):
        self.lines = []

    def info(self, msg, *args, **kwargs):
        self.lines.append(str(msg))

    def hints(self):
        return [line for line in self.lines if "Hint" in line]


@pytest.fixture
def session(monkeypatch):
    """One process: command-line args, prompt answers and fake runs."""
    state = SimpleNamespace(
        args=SimpleNamespace(
            after=None,
            force_all=False,
            no_api_cache=False,
            redownload=False,
            actions=set(),
            daemon=None,
            scrape_paid=False,
            before=arrow.now().shift(days=4),
            before_original=None,
        ),
        answers=[],
        redownload_asked=0,
        runs=[],
        log=Recorder(),
        stats=StatsManager(),
    )
    monkeypatch.setattr(actions_prompt, "_session_values", None, raising=False)
    monkeypatch.setattr(scan_range, "_menu", False)
    monkeypatch.setattr(scan_range, "_hint_shown", False)
    monkeypatch.setattr(settings, "get_args", lambda copy=False: state.args)
    monkeypatch.setattr(settings, "get_settings", lambda: state.args)
    monkeypatch.setattr(settings, "update_args", lambda args: None)
    monkeypatch.setattr(timeline, "log", state.log)

    def checklist(message="", **kwargs):
        if "redownload" in message:
            state.redownload_asked += 1
        return state.answers.pop(0)

    monkeypatch.setattr(prompt_convert, "getChecklistSelection", checklist)

    class FakeScraper:
        # what one run sees: it starts like prepare() and scans a timeline
        # from --after, or from the last scan when none is set
        def runner(self, menu=False):
            args = state.args
            state.runs.append((args.after, args.force_all, args.no_api_cache))
            state.stats.clear_scraper_activity_stats()
            start = args.after.float_timestamp if args.after else PARTIAL
            timeline.time_log("user", start)

    monkeypatch.setattr(scraper, "scraperManager", FakeScraper)
    return state


def main_menu(session, monkeypatch, runs):
    choices = iter(["action"] * runs)
    # the menu loop logs an error and asks again, so never run out of answers
    monkeypatch.setattr(prompts, "main_prompt", lambda: next(choices, "quit"))
    menu.main_menu_action()


def test_main_menu_yes_then_no(session, monkeypatch):
    session.answers = [DOWNLOAD, True, DOWNLOAD, False]

    main_menu(session, monkeypatch, runs=2)

    assert session.answers == []
    assert session.runs == [REDOWNLOAD, NORMAL]
    # the No run scans incrementally again, so it gets the hint
    assert session.log.hints() == [MENU_HINT]


def test_like_only_run_after_a_yes(session, monkeypatch):
    session.answers = [DOWNLOAD, True, LIKE]

    main_menu(session, monkeypatch, runs=2)

    assert session.answers == []
    assert session.redownload_asked == 1
    assert session.runs == [REDOWNLOAD, NORMAL]


def test_run_again_loop_yes_then_no(session, monkeypatch):
    # first run from the command line's --action, then "run again" twice
    session.args.actions = {"download"}
    session.answers = [DOWNLOAD, True, DOWNLOAD, False]
    again = iter(["Yes", "Yes", "No"])
    monkeypatch.setattr(prompts, "continue_prompt", lambda: next(again))
    monkeypatch.setattr(config_data, "get_InfiniteLoop", lambda: True)
    monkeypatch.setattr(menu, "get_count", lambda: 0)
    monkeypatch.setattr(menu, "update_count", lambda: None)

    scraper.process_selected_areas()

    assert session.answers == []
    assert session.runs == [NORMAL, REDOWNLOAD, NORMAL]


def test_no_restores_the_command_line_values(session, monkeypatch):
    given = arrow.get("2023-05-01")
    session.args.after = given
    session.args.no_api_cache = True
    session.answers = [DOWNLOAD, True, DOWNLOAD, False]

    main_menu(session, monkeypatch, runs=2)

    assert session.runs == [REDOWNLOAD, (given, False, True)]


class Stop(BaseException):
    """Ends the daemon loop, which logs and carries on after an Exception."""


def run_daemon(session, monkeypatch, passes):
    """scrapper() with --daemon: the first pass, then ``passes`` more that
    the scheduler queues; the real daemon loop runs them all."""
    session.args.daemon = 30
    session.args.output_level = "NORMAL"
    jobs = queue.Queue()
    monkeypatch.setattr(scraper, "jobqueue", jobs)
    monkeypatch.setattr(scraper.exit, "sigterm_as_keyboard_interrupt", lambda: None)
    monkeypatch.setattr(scraper.checkers, "check_auth", lambda: None)
    monkeypatch.setattr(scraper.actions, "select_areas", lambda: None)
    monkeypatch.setattr(
        scraper,
        "live",
        SimpleNamespace(enabled=lambda: False, watch_enabled=lambda: False),
    )
    monkeypatch.setattr(
        scraper.manager,
        "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(sync_models=lambda: None)),
    )
    monkeypatch.setattr(
        scraper,
        "DaemonWakeup",
        lambda: SimpleNamespace(
            stopped=False, install=lambda: None, restore=lambda: None
        ),
    )

    def stop():
        raise Stop

    def schedule(*functs, wakeup=None):
        # what schedule_helper queues for each later pass, then an end
        for _ in range(passes):
            for funct in functs:
                jobs.put(funct)
        jobs.put(stop)

    monkeypatch.setattr(scraper, "set_schedule", schedule)
    with pytest.raises(Stop):
        scraper.scrapper()


def test_interactive_daemon_yes_is_for_the_first_pass(session, monkeypatch):
    session.answers = [DOWNLOAD, True]

    run_daemon(session, monkeypatch, passes=2)

    assert session.answers == []
    assert session.runs == [REDOWNLOAD, NORMAL, NORMAL]
    # the later passes scan incrementally again, so each gets the hint
    assert session.log.hints() == [MENU_HINT, MENU_HINT]


def test_command_line_daemon_keeps_its_values(session, monkeypatch):
    # --daemon --action download --after 2000 --force-all: never asked
    session.args.actions = {"download"}
    session.args.after = YEAR_2000
    session.args.force_all = True

    run_daemon(session, monkeypatch, passes=2)

    assert session.redownload_asked == 0
    assert session.runs == [(YEAR_2000, True, False)] * 3
