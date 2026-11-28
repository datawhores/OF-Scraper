"""The scan range lines and the full-rescan hint (#430)."""

from types import SimpleNamespace

import arrow
import pytest

import ofscraper.commands.scraper.scraper as scraper
import ofscraper.commands.scraper.utils.prepare as prepare_mod
import ofscraper.data.api.archive as archive
import ofscraper.data.api.common.scan_range as scan_range
import ofscraper.data.api.messages as messages
import ofscraper.data.api.streams as streams
import ofscraper.data.api.timeline as timeline
import ofscraper.prompts.promptConvert as prompt_convert
import ofscraper.prompts.prompt_groups.actions as action_prompts
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.config.data as config_data
import ofscraper.utils.menu as menu
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.managers.stats import StatsManager

CLI_HINT = (
    "[yellow]Hint: Full rescan: add --after 2000"
    " (or --after 2000 --force-all to also re-download files)[/yellow]"
)
MENU_HINT = (
    '[yellow]Hint: Full rescan: answer Yes to "Would you like to redownload'
    ' all files"; it also scans every post from 2000[/yellow]'
)
YEAR_2000 = arrow.get("2000").float_timestamp
PARTIAL = arrow.get("2024-03-01").float_timestamp
AREAS = [timeline, archive, streams, messages]


class Recorder:
    def __init__(self):
        self.lines = []

    def info(self, msg, *args, **kwargs):
        self.lines.extend(str(msg).strip().splitlines())

    def hints(self):
        return [
            line
            for line in self.lines
            if not line.startswith("Setting ")
            and any(word in line.lower() for word in ("hint", "rescan", "--after"))
        ]

    def ranges(self):
        return [line for line in self.lines if line.startswith("Setting ")]


@pytest.fixture
def run(monkeypatch):
    """Settings for one run; prepare() starts each run like the scraper does."""
    state = SimpleNamespace(
        settings=SimpleNamespace(
            actions={"download"},
            after=None,
            # no --before: the cutoff is padded past now
            before=arrow.now().shift(days=4),
            before_original=None,
            redownload=False,
            daemon=None,
            scrape_paid=False,
        ),
        stats=StatsManager(),
        log=Recorder(),
    )
    # a fresh process: no prompt has chosen the actions yet
    monkeypatch.setattr(scan_range, "_menu", False)
    monkeypatch.setattr(scan_range, "_hint_shown", False)
    monkeypatch.setattr(action_prompts, "_session_values", None)
    monkeypatch.setattr(action_prompts, "_redownload_answered", False)
    monkeypatch.setattr(settings, "get_settings", lambda: state.settings)
    monkeypatch.setattr(settings, "get_args", lambda copy=False: state.settings)
    monkeypatch.setattr(settings, "update_args", lambda args: None)
    for module in AREAS:
        monkeypatch.setattr(module, "log", state.log)

    fake_manager = SimpleNamespace(
        Manager=SimpleNamespace(
            session=SimpleNamespace(aget_ofsession=lambda **kwargs: None),
            stats_manager=state.stats,
            current_model_manager=SimpleNamespace(
                prepare_scraper_activity=lambda: []
            ),
        )
    )
    monkeypatch.setattr(prepare_mod, "manager", fake_manager)
    monkeypatch.setattr(prepare_mod, "unique_name_warning", lambda: None)
    monkeypatch.setattr(
        prepare_mod, "profile_tools", SimpleNamespace(print_current_profile=lambda: None)
    )
    monkeypatch.setattr(
        prepare_mod, "init", SimpleNamespace(print_sign_status=lambda: None)
    )
    monkeypatch.setattr(
        prepare_mod,
        "actions",
        SimpleNamespace(select_areas=lambda: None, set_scrape_paid=lambda: None),
    )

    # The action prompt: "Download content from a user", then No to the
    # redownload question
    def checklist(message="", **kwargs):
        if message.startswith("Action Menu"):
            return "Download content from a user"
        assert "redownload" in message
        return False

    monkeypatch.setattr(prompt_convert, "getChecklistSelection", checklist)

    # runner() starts a run with prepare() and scans one creator's timeline
    class FakeScraper:
        def runner(self, menu=False):
            prepare_mod.prepare(menu=menu)
            timeline.time_log("user", PARTIAL)

    monkeypatch.setattr(scraper, "scraperManager", FakeScraper)

    state.start = lambda menu=False: prepare_mod.prepare(menu=menu)
    state.start()
    return state


def test_partial_scan_shows_the_command_line_hint(run):
    timeline.time_log("user", PARTIAL)

    assert run.log.hints() == [CLI_HINT]


def test_full_scan_shows_no_hint(run):
    for module in AREAS:
        module.time_log("user", YEAR_2000)
        module.time_log("user", 0)

    assert run.log.hints() == []
    assert not any("--after" in line for line in run.log.hints())


@pytest.mark.parametrize("module", [archive, streams, messages])
def test_partial_scan_of_other_areas_shows_the_hint(run, module):
    module.time_log("user", PARTIAL)

    assert run.log.hints() == [CLI_HINT]


def test_hint_once_per_run_across_areas(run):
    timeline.time_log("user", YEAR_2000)
    messages.time_log("user", PARTIAL)
    archive.time_log("user", PARTIAL)
    streams.time_log("other", PARTIAL)

    assert run.log.hints() == [CLI_HINT]


def test_main_menu_run_names_the_menu_choice_not_flags(run, monkeypatch):
    choices = iter(["action", "quit"])
    # the menu loop logs an error and asks again, so never run out of answers
    monkeypatch.setattr(prompts, "main_prompt", lambda: next(choices, "quit"))

    menu.main_menu_action()

    assert run.log.hints() == [MENU_HINT]


def test_daemon_with_prompted_actions_names_the_menu_choice(run, monkeypatch):
    run.settings.actions = set()
    run.settings.daemon = 30
    monkeypatch.setattr(scraper, "live", SimpleNamespace(enabled=lambda: False))
    # the daemon queues runner() with its default menu=False
    monkeypatch.setattr(
        scraper, "daemon_process", lambda: scraper.scraperManager().runner()
    )

    scraper.scrapper()

    assert run.settings.actions == {"download"}
    assert run.log.hints() == [MENU_HINT]


def test_run_again_after_the_action_prompt_names_the_menu_choice(run, monkeypatch):
    answers = iter(["Yes", "No"])
    monkeypatch.setattr(prompts, "continue_prompt", lambda: next(answers))
    monkeypatch.setattr(config_data, "get_InfiniteLoop", lambda: True)
    monkeypatch.setattr(menu, "get_count", lambda: 0)
    monkeypatch.setattr(menu, "update_count", lambda: None)

    # first run from the command line's --action, then "run again" asks
    scraper.process_selected_areas()

    assert run.log.hints() == [CLI_HINT, MENU_HINT]


def test_like_only_run_shows_no_hint(run):
    for actions in ({"like"}, {"unlike"}, {"like", "unlike"}):
        run.settings.actions = actions
        for module in AREAS:
            module.time_log("user", PARTIAL)

    assert run.log.hints() == []


def test_start_given_with_after_shows_no_hint(run):
    run.settings.after = arrow.get("2024-03-01")

    timeline.time_log("user", PARTIAL)

    assert run.log.hints() == []


def test_hint_once_per_run_and_again_next_run(run):
    timeline.time_log("first", PARTIAL)
    timeline.time_log("second", PARTIAL)
    assert run.log.hints() == [CLI_HINT]

    # the next run in the same session
    run.start()
    timeline.time_log("first", PARTIAL)
    timeline.time_log("second", PARTIAL)

    assert run.log.hints() == [CLI_HINT, CLI_HINT]


@pytest.mark.parametrize(
    "module, area", [(timeline, "timeline"), (archive, "archived")]
)
def test_range_ends_now_without_before(run, module, area):
    module.time_log("user", YEAR_2000)

    start = arrow.get(YEAR_2000).format(of_env.getattr("API_DATE_FORMAT"))
    assert run.log.lines[0] == (
        f"Setting {area} scan range for user from {start} to now (full scan)"
    )


@pytest.mark.parametrize("module", [timeline, archive])
def test_range_ends_at_the_given_before(run, module):
    before = arrow.get("2025-06-01T12:00:00")
    run.settings.before = before
    run.settings.before_original = before

    module.time_log("user", YEAR_2000)

    end = before.format(of_env.getattr("API_DATE_FORMAT"))
    assert run.log.lines[0].endswith(f" to {end} (full scan)")



def test_range_says_a_partial_scan_starts_where_the_last_scan_left_off(run):
    timeline.time_log("user", PARTIAL)

    assert run.log.ranges() == [
        "Setting timeline scan range for user from 2024-03-01 00:00:00 to now"
        " (where the last scan left off)"
    ]


def test_range_says_the_start_came_from_after(run):
    run.settings.after = arrow.get("2023-05-01")

    for module in AREAS:
        module.time_log("user", run.settings.after.float_timestamp)

    assert [line.split(" from ")[1] for line in run.log.ranges()] == [
        "2023-05-01 00:00:00 to now (--after)"
    ] * 4


def test_range_says_the_start_came_from_redownload(run):
    # --redownload sets --after 2000 for the run
    run.settings.redownload = True
    run.settings.after = arrow.get("2000")

    messages.time_log("user", YEAR_2000)

    assert run.log.ranges()[0].endswith(" to now (--redownload)")


def test_range_says_the_start_came_from_the_redownload_question(run, monkeypatch):
    def checklist(message="", **kwargs):
        if message.startswith("Action Menu"):
            return "Download content from a user"
        return True  # Yes to "Would you like to redownload all files"

    monkeypatch.setattr(prompt_convert, "getChecklistSelection", checklist)
    choices = iter(["action", "quit"])
    monkeypatch.setattr(prompts, "main_prompt", lambda: next(choices, "quit"))

    menu.main_menu_action()

    assert run.log.ranges() == [
        "Setting timeline scan range for user from 2024-03-01 00:00:00 to now"
        " (the redownload question)"
    ]


def test_after_from_the_command_line_is_named_in_a_menu_run(run, monkeypatch):
    # --after on the command line, then No to the redownload question
    run.settings.after = arrow.get("2024-03-01")
    choices = iter(["action", "quit"])
    monkeypatch.setattr(prompts, "main_prompt", lambda: next(choices, "quit"))

    menu.main_menu_action()

    assert run.log.ranges()[0].endswith(" to now (--after)")


def test_a_check_command_scan_is_a_full_scan(run):
    # post_check and msg_check set after=0 themselves: no --after was given
    import ofscraper.commands.check as check

    check.set_after_check_mode()
    timeline.time_log("user", 0)

    assert run.log.ranges()[0].endswith(" to now (full scan)")


def test_the_menu_check_table_is_a_full_scan(run):
    # "Browse and pick media" never asks the redownload question
    import ofscraper.commands.check as check

    action_prompts._apply_action("Browse and pick media (check table)")
    check.set_after_check_mode()
    messages.time_log("user", 0)

    assert run.log.ranges()[0].endswith(" to now (full scan)")
