"""Prompt answers and errors still show with --output LOW and PROMPT.

Those modes quiet the shared console (#255). A few messages went straight to
the shared console although the user has to see them: the list shown by
"Print Selection", the CDM check's failures, the "another instance" warning,
the confirmations after the config and profile menus, and the warning about
Discord with DEBUG. They now print through get_console(), which stays loud.
"""

import io
import sys
from types import SimpleNamespace

import httpx
import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.args.globals as global_args
import ofscraper.utils.console as console
from ofscraper.utils.args.parse.commands.main import program

MODES = ["LOW", "PROMPT"]


@pytest.fixture
def screen(monkeypatch, request):
    """Parse --output <mode> for real and send both consoles to one buffer."""
    monkeypatch.setattr(sys, "argv", ["ofscraper", "--output", request.param])
    monkeypatch.setattr(global_args, "args", None)
    # parse_args registers the subcommands, which can only happen once a process
    if "manual" in program.commands:
        monkeypatch.setattr(program, "add_command", lambda *a, **k: None)
    monkeypatch.setattr(console, "shared_console", None)
    monkeypatch.setattr(console, "other_console", None)
    buf = io.StringIO()
    shared = console.get_shared_console()
    for con in (shared, console.get_other_console()):
        con.file = buf
        con.width = 300
    assert shared.quiet is True  # the mode really is quiet
    return SimpleNamespace(buf=buf, shared=shared)


class _Stop(Exception):
    pass


@pytest.mark.parametrize("screen", MODES, indirect=True)
def test_print_selection_shows_the_queued_names(monkeypatch, screen):
    import ofscraper.managers.model as model
    import ofscraper.utils.settings as settings

    mm = model.ModelManager()
    monkeypatch.setattr(mm, "_get_activities", lambda actions: [])
    monkeypatch.setattr(mm, "_load_all_subs_if_needed", lambda: None)
    monkeypatch.setattr(
        mm,
        "get_scrape_selected_models",
        lambda: [SimpleNamespace(name="queued_one"), SimpleNamespace(name="queued_two")],
    )
    real = settings.get_settings
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(**{**vars(real()), "actions": [], "command": None}),
    )
    monkeypatch.setattr(model.prompts, "reset_username_prompt", lambda: "Print")

    def press_enter():
        raise _Stop

    monkeypatch.setattr(model.prompts, "press_enter_to_continue", press_enter)
    with pytest.raises(_Stop):
        mm.prepare_scraper_activity()
    out = screen.buf.getvalue()
    assert "queued_one" in out and "queued_two" in out


@pytest.mark.parametrize("screen", MODES, indirect=True)
def test_cdm_check_failure_shows(monkeypatch, screen):
    import ofscraper.sites as sites
    import ofscraper.utils.system.network as network

    monkeypatch.setattr(sites, "is_fansly", lambda: False)
    monkeypatch.setattr(
        network.settings, "get_settings", lambda: SimpleNamespace(key_mode="cdrm")
    )
    monkeypatch.setattr(network.time, "sleep", lambda s: None)

    def timed_out(**kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(network.sessionManager, "sessionManager", timed_out)
    assert network.check_cdm() is False
    out = screen.buf.getvalue()
    assert "Key Mode" not in out  # the ordinary status line stays hidden
    assert "timed out and seems to be down" in out


@pytest.mark.parametrize("screen", MODES, indirect=True)
def test_cdm_check_error_status_shows(monkeypatch, screen):
    import ofscraper.sites as sites
    import ofscraper.utils.system.network as network

    monkeypatch.setattr(sites, "is_fansly", lambda: False)
    monkeypatch.setattr(
        network.settings, "get_settings", lambda: SimpleNamespace(key_mode="cdrm")
    )
    monkeypatch.setattr(network.time, "sleep", lambda s: None)

    class _Resp:
        ok = False
        status = 500
        headers = {}

        def text_(self):
            return ""

    class _Ctx:
        def __init__(self, value):
            self.value = value

        def __enter__(self):
            return self.value

        def __exit__(self, *exc):
            return False

    session = SimpleNamespace(requests=lambda **kw: _Ctx(_Resp()))
    monkeypatch.setattr(network.sessionManager, "sessionManager", lambda **kw: _Ctx(session))
    assert network.check_cdm() is False
    assert "CDM return an error" in screen.buf.getvalue()


@pytest.mark.parametrize("screen", MODES, indirect=True)
def test_cdm_check_exception_shows(monkeypatch, screen):
    import ofscraper.sites as sites
    import ofscraper.utils.system.network as network

    monkeypatch.setattr(sites, "is_fansly", lambda: False)
    monkeypatch.setattr(
        network.settings, "get_settings", lambda: SimpleNamespace(key_mode="cdrm")
    )
    monkeypatch.setattr(network.time, "sleep", lambda s: None)

    def broken(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(network.sessionManager, "sessionManager", broken)
    assert network.check_cdm() is False
    assert "has an issue boom" in screen.buf.getvalue()


@pytest.mark.parametrize("screen", MODES, indirect=True)
def test_another_instance_warning_shows(monkeypatch, screen):
    import ofscraper.managers.manager as manager

    monkeypatch.setattr(manager.system, "get_dupe_ofscraper", lambda: [object()])
    monkeypatch.setattr(manager.logs, "printStartValues", lambda: None)
    manager.mainManager.initLogs(None)
    assert "another OF-Scraper instance was detected" in screen.buf.getvalue()


@pytest.mark.parametrize("screen", MODES, indirect=True)
def test_config_menu_confirmation_shows(monkeypatch, screen):
    import ofscraper.utils.config.menu as menu

    monkeypatch.setattr(menu, "console", screen.shared, raising=False)  # only the old code has it
    monkeypatch.setattr(menu.config_file, "open_config", lambda: {})
    monkeypatch.setattr(menu.config_, "update_config_full", lambda *a, **k: None)
    monkeypatch.setattr(menu.settings, "update_settings", lambda: None)
    menu.update_config_helper({})
    assert "has been successfully edited" in screen.buf.getvalue()


@pytest.mark.parametrize("screen", MODES, indirect=True)
def test_profile_created_confirmation_shows(monkeypatch, screen):
    import ofscraper.utils.profiles.manage as manage

    monkeypatch.setattr(manage.tools, "print_profiles", lambda: None)
    monkeypatch.setattr(manage.prompts, "create_profiles_prompt", lambda: "new_profile")
    monkeypatch.setattr(manage.manage, "create_profile_path", lambda name: None)
    monkeypatch.setattr(manage.prompts, "change_selected_profile", lambda: "neither")
    if not isinstance(manage.console, type(console)):  # the old module-level alias
        monkeypatch.setattr(manage, "console", screen.shared)
    manage.create_profile()
    assert "Successfully created" in screen.buf.getvalue()


@pytest.mark.parametrize("screen", MODES, indirect=True)
def test_discord_debug_tip_shows(monkeypatch, screen):
    import ofscraper.utils.logs.logs as logs

    monkeypatch.setattr(
        logs.settings, "get_settings", lambda: SimpleNamespace(discord_level="DEBUG")
    )
    logs.discord_warning()
    assert "Warning Discord with DEBUG is not recommended" in screen.buf.getvalue()
