"""The check table opens from the Action Menu (#425).

"Browse and pick media (check table)" asks the usual creator questions, then
which table to open, and runs that check command's code. What the check code
changes in the args is put back afterwards, and a redownload Yes from an
earlier run doesn't reach it.
"""

import asyncio
import threading
from copy import deepcopy
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.commands.check as check
import ofscraper.commands.check_menu as check_menu
import ofscraper.commands.scraper.scraper as scraper
import ofscraper.data.api.common.scan_range as scan_range
import ofscraper.prompts.promptConvert as prompt_convert
import ofscraper.prompts.prompt_groups.actions as actions_prompt
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.config.data as config_data
import ofscraper.utils.console as console_
import ofscraper.utils.menu as menu
import ofscraper.utils.settings as settings
from ofscraper.utils.args.main import AutoDotDict
from InquirerPy.separator import Separator

DOWNLOAD = "Download content from a user"
CHECK = "Browse and pick media (check table)"
TABLES = {
    "Posts": "post_check",
    "Messages": "msg_check",
    "Paid": "paid_check",
    "Stories": "story_check",
}
CREATORS = ["fake_creator_one", "fake_creator_two"]
NORMAL = (None, False, False)
REDOWNLOAD = (arrow.get("2000"), True, True)


def _args(**extra):
    return AutoDotDict(
        command="OF-Scraper",
        after=None,
        force_all=False,
        no_api_cache=False,
        redownload=False,
        actions=set(),
        daemon=None,
        scrape_paid=False,
        text=False,
        desc=True,
        before=None,
        before_original=None,
        **extra,
    )


@pytest.fixture
def session(monkeypatch):
    """One menu session: the args, prompt answers, and fake runs and tables."""
    state = SimpleNamespace(
        args=_args(),
        answers=[],
        picked=[SimpleNamespace(name=name) for name in CREATORS],
        runs=[],
        tables=[],
        selections=0,
    )
    monkeypatch.setattr(actions_prompt, "_session_values", None, raising=False)
    monkeypatch.setattr(scan_range, "_menu", False)
    monkeypatch.setattr(scan_range, "_hint_shown", False)
    def get_args(copy=False):
        return deepcopy(state.args) if copy else state.args

    def update_args(args):
        state.args = args

    monkeypatch.setattr(settings, "get_args", get_args)
    monkeypatch.setattr(settings, "get_settings", lambda: state.args)
    monkeypatch.setattr(settings, "update_args", update_args)
    monkeypatch.setattr(
        prompt_convert,
        "getChecklistSelection",
        lambda message="", **kwargs: state.answers.pop(0),
    )

    class FakeScraper:
        def runner(self, menu=False):
            args = state.args
            state.runs.append(
                ("download", (args.after, args.force_all, args.no_api_cache), args.command)
            )

    monkeypatch.setattr(scraper, "scraperManager", FakeScraper)

    def select_models():
        state.selections += 1
        return state.picked

    monkeypatch.setattr(
        check_menu.manager,
        "Manager",
        SimpleNamespace(
            current_model_manager=SimpleNamespace(select_models=select_models)
        ),
    )
    monkeypatch.setattr(check_menu, "check_auth", lambda **k: None)
    monkeypatch.setattr(check, "check_auth", lambda **k: None)
    monkeypatch.setattr(check.network, "check_cdm", lambda: None)
    # the download thread: nothing to download here
    monkeypatch.setattr(check, "process_download_queue", lambda: None)

    def fake_runner():
        # what the check code reads for the table, as the real runners do
        current = settings.get_settings()
        state.runs.append(
            (
                "table",
                current.command,
                list(current.url or []),
                list(current.check_usernames or []),
                (current.after, current.force_all, current.no_api_cache),
            )
        )
        check.ROWS = check.ROWS or []
        for name in check.check_usernames() or list(check.url_helper()):
            check.ROWS.append({"username": name, "command": current.command})

    for name in (
        "post_check_runner",
        "message_checker_runner",
        "purchase_checker_runner",
        "stories_checker_runner",
    ):
        monkeypatch.setattr(check, name, fake_runner)

    def start_table(rows):
        # the open table quiets the console and its toggles change the args
        state.tables.append(list(rows))
        console_.get_shared_console().quiet = True
        state.args.text = True

    monkeypatch.setattr(check, "start_table", start_table)
    monkeypatch.setattr(check, "ROWS", [])
    monkeypatch.setattr(check, "_download_worker", None, raising=False)
    monkeypatch.setattr(console_.get_shared_console(), "quiet", False)
    return state


class _Failed(AssertionError):
    pass


def _raise(msg, *args, **kwargs):
    raise _Failed(msg)


def main_menu(monkeypatch, runs):
    choices = iter(["action"] * runs)
    monkeypatch.setattr(prompts, "main_prompt", lambda: next(choices, "quit"))
    # the menu logs an error and asks again; here an error fails the test
    monkeypatch.setattr(menu, "log", SimpleNamespace(error=_raise, debug=lambda *a, **k: None))
    menu.main_menu_action()


def _menu_names(choices):
    return ["-" if isinstance(c, Separator) else c for c in choices]


def test_the_action_menu_lists_the_check_table_in_its_own_group(session):
    assert _menu_names(actions_prompt.action_menu_choices(session.args)) == [
        "Download content from a user",
        "Like a selection of a user's posts",
        "Unlike a selection of a user's posts",
        "-",
        "Download content from a user + Like a selection of a user's posts",
        "Download content from a user + Unlike a selection of a user's posts",
        "-",
        CHECK,
        "-",
        "Go to main menu",
        "Quit",
        "-",
    ]


def test_the_daemon_and_fansly_menus_leave_the_check_table_out(session):
    session.args.daemon = 30
    assert CHECK not in actions_prompt.action_menu_choices(session.args)
    session.args.daemon = None
    session.args.site = "fansly"
    assert CHECK not in actions_prompt.action_menu_choices(session.args)


def test_the_check_choice_returns_check(session):
    session.answers = [CHECK]
    assert prompts.action_prompt() == "check"


@pytest.mark.parametrize("table", list(TABLES))
def test_each_table_runs_its_check_command(session, monkeypatch, table):
    command = TABLES[table]
    session.answers = [CHECK, table]

    main_menu(monkeypatch, runs=1)

    assert session.answers == []
    assert session.selections == 1
    assert len(session.runs) == 1
    kind, ran, url, usernames, _ = session.runs[0]
    assert (kind, ran) == ("table", command)
    # post_check and msg_check read creators from --url, the others from -u
    if command in {"post_check", "msg_check"}:
        assert (url, usernames) == (CREATORS, [])
    else:
        assert (url, usernames) == ([], CREATORS)
    assert session.tables == [
        [{"username": name, "command": command} for name in CREATORS]
    ]


def test_the_args_are_put_back_after_the_table(session, monkeypatch):
    before = deepcopy(session.args)
    session.answers = [CHECK, "Paid"]

    main_menu(monkeypatch, runs=1)

    # the check code set these for its run: --force-all, --after 0 and the
    # creators; the open table turned "Download Text" on
    assert session.runs[0][4] == (0, True, False)
    assert session.args == before
    assert console_.get_shared_console().quiet is False


def test_runs_before_and_after_the_table_keep_their_own_settings(session, monkeypatch):
    # a redownload Yes, the table, then a normal download
    session.answers = [DOWNLOAD, True, CHECK, "Posts", DOWNLOAD, False]

    main_menu(monkeypatch, runs=3)

    assert session.answers == []
    assert session.runs[0] == ("download", REDOWNLOAD, "OF-Scraper")
    # the Yes was for the first run: no --no-api-cache on the table's
    assert session.runs[1][:2] == ("table", "post_check")
    assert session.runs[1][4] == (0, True, False)
    assert session.runs[2] == ("download", NORMAL, "OF-Scraper")
    assert session.args.url is None and session.args.check_usernames is None


def test_a_second_table_shows_only_its_own_rows(session, monkeypatch):
    session.answers = [CHECK, "Posts", CHECK, "Stories"]
    session.picked = [SimpleNamespace(name="fake_creator_one")]

    main_menu(monkeypatch, runs=2)

    assert session.tables == [
        [{"username": "fake_creator_one", "command": "post_check"}],
        [{"username": "fake_creator_one", "command": "story_check"}],
    ]


def test_no_creator_picked_opens_no_table(session, monkeypatch):
    session.answers = [CHECK]
    session.picked = []

    main_menu(monkeypatch, runs=1)

    # not even the table question
    assert session.answers == []
    assert session.runs == [] and session.tables == []


def test_run_again_loop_opens_the_table(session, monkeypatch):
    # first run from the command line's --action, then "run again" twice
    session.args.actions = {"download"}
    session.answers = [CHECK, "Messages", DOWNLOAD, False]
    again = iter(["Yes", "Yes", "No"])
    monkeypatch.setattr(prompts, "continue_prompt", lambda: next(again))
    monkeypatch.setattr(config_data, "get_InfiniteLoop", lambda: True)
    monkeypatch.setattr(menu, "get_count", lambda: 0)
    monkeypatch.setattr(menu, "update_count", lambda: None)

    scraper.process_selected_areas()

    assert session.answers == []
    assert [run[0] for run in session.runs] == ["download", "table", "download"]
    assert session.runs[1][1] == "msg_check"
    assert session.runs[2] == ("download", NORMAL, "OF-Scraper")


def test_tables_share_one_download_thread(session, monkeypatch):
    stop = threading.Event()
    started = []

    def worker():
        started.append(1)
        stop.wait(5)

    monkeypatch.setattr(check, "process_download_queue", worker)
    session.answers = [CHECK, "Posts", CHECK, "Paid"]
    try:
        main_menu(monkeypatch, runs=2)
    finally:
        stop.set()
        check._download_worker.join(5)
    assert started == [1]
    assert len(session.tables) == 2


def test_the_menu_waits_for_downloads_sent_from_the_table(session, monkeypatch):
    waited = []
    monkeypatch.setattr(check, "wait_for_downloads", lambda: waited.append(1))
    session.answers = [CHECK, "Posts"]

    main_menu(monkeypatch, runs=1)

    assert waited == [1]


def test_wait_for_downloads_returns_once_the_thread_is_idle(monkeypatch):
    class Worker:
        def is_alive(self):
            return True

    states = iter([True, True, False])
    monkeypatch.setattr(check, "_download_worker", Worker())
    monkeypatch.setattr(check, "_downloading", SimpleNamespace(is_set=lambda: next(states)))
    monkeypatch.setattr(check.app, "row_queue", SimpleNamespace(empty=lambda: True))
    monkeypatch.setattr(check.time, "sleep", lambda s: None)

    check.wait_for_downloads()

    with pytest.raises(StopIteration):
        next(states)


def test_wait_for_downloads_does_not_wait_on_a_dead_thread(monkeypatch):
    monkeypatch.setattr(check, "_download_worker", SimpleNamespace(is_alive=lambda: False))
    monkeypatch.setattr(check.app, "row_queue", SimpleNamespace(empty=lambda: False))
    assert check.downloads_pending() is False


class _TableSettings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _table_row(index):
    return {
        "index": index,
        "number": index,
        "download_cart": "[downloading]",
        "username": "fake_creator_one",
        "downloaded": False,
        "unlocked": True,
        "download_type": "normal",
        "other_posts_with_media": [],
        "post_media_count": 1,
        "mediatype": "Images",
        "post_date": "2024-01-01",
        "media": 1,
        "length": "N/A",
        "responsetype": "Timeline",
        "price": "Free",
        "post_id": 100 + index,
        "media_id": 1000 + index,
        "text": "t",
    }


def test_a_download_can_finish_after_its_table_closed(monkeypatch, tmp_path):
    # the menu waits for the downloads after the table closes; marking a row
    # done on the closed table must not raise, or the download counts as failed
    table_app = check.app
    # the table quiets the console; put it back after
    monkeypatch.setattr(console_.get_shared_console(), "quiet", False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _TableSettings(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )

    async def run():
        app = table_app.InputApp()
        app.table_data = [_table_row(1), _table_row(2)]
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(200, 50)) as pilot:
            await pilot.pause()
        return app

    closed = asyncio.run(run())
    closed.update_cell_state("2", "[downloaded]", "bold green")

    row = next(r for r in closed.table_data if r["index"] == 2)
    assert (row["download_cart"], row["downloaded"]) == ("[downloaded]", True)
