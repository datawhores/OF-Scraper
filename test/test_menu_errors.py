"""A failed main-menu action says so on screen (#307).

The main menu caught every error and wrote it only to the debug log, so at the
normal output level the menu just came back with no sign that anything failed.
"""

import io
import logging
from types import SimpleNamespace

import pytest
from rich.console import Console

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.managers.manager as manager
import ofscraper.prompts.promptConvert as prompt_classes
import ofscraper.sites as sites
import ofscraper.utils.args.accessors.areas as areas
import ofscraper.utils.args.globals as global_args
import ofscraper.utils.interactive as interactive
import ofscraper.utils.logs.stdout as stdout_logs
import ofscraper.utils.menu as menu
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.profiles.data as profile_data
import ofscraper.utils.settings as settings
from ofscraper.managers.utils.state import EActivity
from ofscraper.utils.args.main import AutoDotDict
from ofscraper.utils.args.parse.commands.main import program

ERROR_TEXT = r"could not open logs\[old] [bold]x[/bold]"


@pytest.fixture
def screen(monkeypatch):
    """The "shared" logger with the app's real console handlers at the
    normal output level, printing to a buffer; yields that buffer."""
    out = io.StringIO()
    fake_console = Console(file=out, markup=True, width=500, color_system=None)
    monkeypatch.setattr(stdout_logs.console, "get_console", lambda: fake_console)
    monkeypatch.setattr(stdout_logs.console, "get_shared_console", lambda: fake_console)
    monkeypatch.setattr(
        stdout_logs.settings, "get_settings", lambda: SimpleNamespace(output_level="NORMAL")
    )
    monkeypatch.setattr(sites, "init_session_site", lambda: None)
    logger = logging.getLogger("shared")
    old_handlers, old_level = logger.handlers[:], logger.level
    stdout_logs.add_stdout_handler(logger, clear=True)
    try:
        yield out
    finally:
        logger.handlers[:] = old_handlers
        logger.setLevel(old_level)


@pytest.fixture
def records():
    """Everything the "shared" logger records, debug included."""
    found = []
    handler = logging.Handler(level=logging.DEBUG)
    handler.emit = found.append
    logger = logging.getLogger("shared")
    logger.addHandler(handler)
    yield found
    logger.removeHandler(handler)


def _menu(monkeypatch, merge_runner):
    """Answer the main menu with Merge Databases, then Quit."""
    answers = ["merge", "quit"]
    asked = []

    def main_prompt():
        asked.append(answers[0])
        return answers.pop(0)

    monkeypatch.setattr(menu.prompts, "main_prompt", main_prompt)
    monkeypatch.setattr(menu.merge, "merge_runner", merge_runner)
    return asked


@pytest.fixture
def menu_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(common_paths, "get_config_home", lambda: tmp_path)
    monkeypatch.setattr(sites, "_session_site", None)
    monkeypatch.setattr(sites, "_session_profile", None)
    monkeypatch.setattr(settings, "settings", {})
    parsed, command = program.main([], standalone_mode=False, prog_name="OF-Scraper")
    args = AutoDotDict(parsed, command=command, profile="main_profile")
    monkeypatch.setattr(global_args, "args", args)
    monkeypatch.setattr(manager, "Manager", manager.mainManager())
    return args


@pytest.mark.parametrize("scope", ["session", "profile"])
def test_switch_site_discards_the_previous_creator_manager(monkeypatch, menu_profile, scope):
    previous = manager.Manager.current_model_manager
    previous.state.set_queue(EActivity.ScrapeActivity.DOWNLOAD, ["a creator"])
    monkeypatch.setattr(prompt_classes, "getChecklistSelection", lambda **kwargs: scope)

    menu.switch_site_helper()

    assert sites.current_site() == sites.FANSLY
    new_manager = manager.Manager.current_model_manager
    assert new_manager is not previous
    assert new_manager.state.get_all_queued_usernames() == []
    stored_site = sites.read_profile_site(common_paths.get_profile_path())
    assert stored_site == (sites.FANSLY if scope == "profile" else sites.ONLYFANS)


def test_switch_site_clears_command_line_posts(monkeypatch, menu_profile):
    menu_profile.posts = ["Pinned"]
    settings.update_settings()
    assert areas.get_download_area() == {"Pinned"}
    monkeypatch.setattr(prompt_classes, "getChecklistSelection", lambda **kwargs: "session")
    menu.switch_site_helper()
    assert areas.get_download_area() == set()


def test_switch_site_refreshes_the_signed_in_account(monkeypatch, menu_profile):
    import ofscraper.data.api.me as me

    monkeypatch.setattr(profile_data, "currentData", None)
    monkeypatch.setattr(profile_data, "currentProfile", None)
    monkeypatch.setattr(me, "scrape_user", lambda: {"id": sites.current_site()})
    monkeypatch.setattr(prompt_classes, "getChecklistSelection", lambda **kwargs: "session")
    assert profile_data.get_my_info()["id"] == sites.ONLYFANS

    menu.switch_site_helper()
    assert profile_data.get_my_info()["id"] == sites.FANSLY


def _fail(exc):
    def runner():
        raise exc

    return runner


def test_failed_action_is_shown_and_the_menu_comes_back(monkeypatch, screen, records):
    asked = _menu(monkeypatch, _fail(RuntimeError(ERROR_TEXT)))
    assert menu.main_menu_action() is True
    assert asked == ["merge", "quit"]  # the menu came back after the error
    shown = screen.getvalue()
    # names the action and the error, brackets and backslash printed as is
    assert f"Merge Databases failed: RuntimeError: {ERROR_TEXT}" in shown
    # no traceback at the normal level
    assert "Traceback" not in shown
    tracebacks = [r for r in records if "Traceback" in r.getMessage()]
    assert tracebacks and all(r.levelno == logging.DEBUG for r in tracebacks)
    assert "RuntimeError" in tracebacks[0].getMessage()


def test_failing_menu_prompt_is_shown_too(monkeypatch, screen):
    calls = []

    def main_prompt():
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("bad [answer]")
        return "quit"

    monkeypatch.setattr(menu.prompts, "main_prompt", main_prompt)
    assert menu.main_menu_action() is True
    assert "Main Menu failed: ValueError: bad [answer]" in screen.getvalue()


def test_successful_action_shows_no_error(monkeypatch, screen, records):
    ran = []
    asked = _menu(monkeypatch, lambda: ran.append(1))
    assert menu.main_menu_action() is True
    assert ran == [1]
    assert asked == ["merge", "quit"]
    assert "failed" not in screen.getvalue()
    assert not [r for r in records if r.levelno >= logging.WARNING]


@pytest.mark.parametrize(
    "exc", [interactive.NoConsoleError("no console"), KeyboardInterrupt(), SystemExit(2)]
)
def test_no_console_interrupt_and_exit_still_end_the_menu(monkeypatch, screen, exc):
    asked = _menu(monkeypatch, _fail(exc))
    with pytest.raises(type(exc)):
        menu.main_menu_action()
    assert asked == ["merge"]
    assert "failed" not in screen.getvalue()


# --- the main menu says which database is in use ---


def _main_menu_instruction(monkeypatch):
    import ofscraper.prompts.prompt_groups.menu as menu_prompts

    shown = {}

    def selection(**kwargs):
        shown.update(kwargs)
        return "Quit"

    monkeypatch.setattr(menu_prompts.promptClasses, "getChecklistSelection", selection)
    assert menu_prompts.main_prompt() == "quit"
    return shown["instruction"]


def test_main_menu_names_the_postgresql_server_without_the_login(monkeypatch, menu_profile):
    import ofscraper.db.postgres as postgres

    monkeypatch.setattr(
        postgres, "url", lambda: "postgresql://scraper:s3cret-word@db.example:5433/library"
    )
    try:
        import psycopg  # noqa: F401
    except ImportError:  # without the driver the address isn't read
        where = "the configured database"
    else:
        where = "db.example:5433/library"
    instruction = _main_menu_instruction(monkeypatch)
    assert f"| DB: PostgreSQL ({where}))" in instruction
    assert "s3cret-word" not in instruction and "scraper:" not in instruction


def test_main_menu_names_the_sqlite_database(monkeypatch, menu_profile):
    import ofscraper.db.postgres as postgres
    import ofscraper.utils.config.data as data

    def unreadable(*args, **kwargs):
        raise AssertionError("the config was read")

    monkeypatch.setattr(postgres, "url", lambda: "")
    # Naming the database doesn't require loading the metadata setting.
    monkeypatch.setattr(data, "get_metadata", unreadable)
    assert "| DB: user_data.db)" in _main_menu_instruction(monkeypatch)


def test_main_menu_counts_each_queued_creator_once(monkeypatch, menu_profile):
    state = manager.Manager.current_model_manager.state
    state.set_queue(EActivity.ScrapeActivity.DOWNLOAD, ["a creator"])
    state.set_queue(EActivity.ScrapeActivity.LIKE, ["a creator", "another creator"])
    assert "| Users: 2 selected |" in _main_menu_instruction(monkeypatch)


def _profile_switch_setup(monkeypatch, tmp_path, args, stored_site, override=None):
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(common_paths, "get_config_path", lambda: config)
    sites.write_profile_site(tmp_path / "main_profile", stored_site)
    args.posts = ["Pinned"]
    args.download_area = ["Archived"]
    args.like_area = ["Featured"]
    args.scrape_paid = True
    settings.update_settings()
    if override:
        sites.set_active_site(override)
        settings.update_settings()


@pytest.mark.parametrize("choice", ["active", "default"])
@pytest.mark.parametrize("source,target", [(sites.ONLYFANS, sites.FANSLY), (sites.FANSLY, sites.ONLYFANS)])
def test_profile_site_change_clears_all_areas(monkeypatch, tmp_path, menu_profile, choice, source, target):
    _profile_switch_setup(monkeypatch, tmp_path, menu_profile, source)
    sites.write_profile_site(tmp_path / "other_profile", target)
    monkeypatch.setattr(menu.prompts, "get_profile_prompt", lambda *args: "other_profile")

    menu.profile_menu_helper(choice)

    assert profile_data.get_active_profile() == "other_profile"
    assert sites.current_site() == target
    args = settings.get_args()
    assert not args.posts
    assert not args.download_area
    assert not args.like_area
    assert args.scrape_paid is None
    assert areas.get_download_area() == set()


@pytest.mark.parametrize("choice", ["active", "default"])
@pytest.mark.parametrize("selection", ["main_profile", None])
def test_profile_noop_keeps_site_override_and_areas(monkeypatch, tmp_path, menu_profile, choice, selection):
    _profile_switch_setup(monkeypatch, tmp_path, menu_profile, sites.FANSLY, sites.ONLYFANS)
    monkeypatch.setattr(menu.prompts, "get_profile_prompt", lambda *args: selection)

    menu.profile_menu_helper(choice)

    assert profile_data.get_active_profile() == "main_profile"
    assert sites.current_site() == sites.ONLYFANS
    assert sites._session_site == sites.ONLYFANS
    assert settings.get_args().posts == ["Pinned"]
    assert settings.get_args().download_area == ["Archived"]
    assert settings.get_args().like_area == ["Featured"]
    assert settings.get_args().scrape_paid is True


@pytest.mark.parametrize("choice", ["active", "default"])
def test_profile_change_compares_effective_sites(monkeypatch, tmp_path, menu_profile, choice):
    _profile_switch_setup(monkeypatch, tmp_path, menu_profile, sites.FANSLY, sites.ONLYFANS)
    sites.write_profile_site(tmp_path / "other_profile", sites.ONLYFANS)
    monkeypatch.setattr(menu.prompts, "get_profile_prompt", lambda *args: "other_profile")

    menu.profile_menu_helper(choice)

    assert profile_data.get_active_profile() == "other_profile"
    assert sites.current_site() == sites.ONLYFANS
    assert sites._session_site is None
    assert settings.get_args().posts == ["Pinned"]
    assert settings.get_args().download_area == ["Archived"]
    assert settings.get_args().like_area == ["Featured"]
    assert settings.get_args().scrape_paid is True


def test_switch_site_preserves_each_site_creator_manager(monkeypatch, menu_profile):
    of_manager = manager.Manager.current_model_manager
    of_manager.state.set_queue(EActivity.ScrapeActivity.DOWNLOAD, ["a creator"])
    monkeypatch.setattr(prompt_classes, "getChecklistSelection", lambda **kwargs: "session")

    menu.switch_site_helper()
    assert sites.current_site() == sites.FANSLY
    fansly_manager = manager.Manager.current_model_manager
    assert fansly_manager is not of_manager
    fansly_manager.state.set_queue(EActivity.ScrapeActivity.DOWNLOAD, ["another creator"])

    menu.switch_site_helper()
    assert sites.current_site() == sites.ONLYFANS
    assert manager.Manager.current_model_manager is of_manager
    assert manager.Manager.current_model_manager.state.get_all_queued_usernames() == ["a creator"]

    menu.switch_site_helper()
    assert sites.current_site() == sites.FANSLY
    assert manager.Manager.current_model_manager is fansly_manager
    assert manager.Manager.current_model_manager.state.get_all_queued_usernames() == ["another creator"]


@pytest.mark.parametrize(
    "stored_site,override,activation,should_clear",
    [
        (sites.FANSLY, None, "active", True),
        (sites.FANSLY, None, "default", True),
        (sites.FANSLY, sites.ONLYFANS, "active", False),
        (sites.FANSLY, None, "no", False),
    ],
)
def test_create_profile_clears_areas_only_when_effective_site_changes(
    monkeypatch, tmp_path, menu_profile, stored_site, override, activation, should_clear
):
    _profile_switch_setup(monkeypatch, tmp_path, menu_profile, stored_site, override)
    monkeypatch.setattr(menu.prompts, "create_profiles_prompt", lambda: "fresh")
    monkeypatch.setattr(menu.prompts, "change_selected_profile", lambda: activation)

    menu.profile_menu_helper("create")

    expected_profile = "main_profile" if activation == "no" else "fresh_profile"
    assert profile_data.get_active_profile() == expected_profile
    if should_clear:
        assert sites.current_site() == sites.ONLYFANS
        args = settings.get_args()
        assert not args.posts
        assert not args.download_area
        assert not args.like_area
        assert args.scrape_paid is None
        assert areas.get_download_area() == set()
    else:
        assert settings.get_args().posts == ["Pinned"]
        assert settings.get_args().download_area == ["Archived"]
        assert settings.get_args().like_area == ["Featured"]
        assert settings.get_args().scrape_paid is True


@pytest.mark.parametrize("is_default", [False, True])
def test_rename_active_profile_preserves_session_site_override(
    monkeypatch, tmp_path, menu_profile, is_default
):
    config = tmp_path / "config.json"
    config.write_text('{"main_profile": "main_profile"}', encoding="utf-8")
    monkeypatch.setattr(common_paths, "get_config_path", lambda: config)
    (tmp_path / "main_profile").mkdir(exist_ok=True)
    if is_default:
        menu_profile.profile = None
    settings.update_settings()

    of_manager = manager.Manager.current_model_manager
    of_manager.state.set_queue(EActivity.ScrapeActivity.DOWNLOAD, ["a creator"])

    sites.set_active_site(sites.FANSLY)
    settings.update_settings()
    assert sites.current_site() == sites.FANSLY
    fansly_manager = manager.Manager.current_model_manager
    fansly_manager.state.set_queue(EActivity.ScrapeActivity.DOWNLOAD, ["another creator"])

    manager.Manager.profile_manager.rename_profile("main_profile", "renamed_profile")
    settings.update_settings()

    assert profile_data.get_active_profile() == "renamed_profile"
    assert sites.current_site() == sites.FANSLY
    assert sites._session_site == sites.FANSLY
    assert sites._session_profile == "renamed_profile"
    assert manager.Manager.current_model_manager is fansly_manager
    sites.set_active_site(sites.ONLYFANS)
    settings.update_settings()
    assert manager.Manager.current_model_manager is of_manager


def test_delete_profile_from_the_menu_removes_its_folder_and_creator_managers(
    monkeypatch, tmp_path, menu_profile
):
    """The Profile menu's Delete called ProfileManager.delete_profile() without
    the profile's name: a TypeError after the folder was already removed, so
    the creator managers kept for that profile were never dropped."""
    import ofscraper.utils.profiles.manage as profile_manage

    (tmp_path / "main_profile").mkdir(exist_ok=True)
    other = tmp_path / "other_profile"
    other.mkdir()
    settings.update_settings()
    kept = manager.Manager.current_model_manager
    profile_manager = manager.Manager.profile_manager
    profile_manager.model_managers[("other_profile", sites.ONLYFANS)] = object()
    profile_manager.model_managers[("other_profile", sites.FANSLY)] = object()
    monkeypatch.setattr(profile_manage.tools, "print_profiles", lambda: None)
    monkeypatch.setattr(profile_manage.profile_data, "get_profile_names", lambda: [])
    monkeypatch.setattr(profile_manage.prompts, "get_profile_prompt", lambda names: "other_profile")

    profile_manage.delete_profile()

    assert not other.exists()
    assert [k for k in profile_manager.model_managers if k[0] == "other_profile"] == []
    assert manager.Manager.current_model_manager is kept
