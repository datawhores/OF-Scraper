"""On-screen messages print outside text (names, paths, errors) as text,
not as Rich markup, so brackets in it can't crash or restyle the line."""

import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from rich.console import Console

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.commands.db as db
import ofscraper.utils.auth.utils.warning.warning as auth_warning
import ofscraper.utils.me as me
import ofscraper.utils.paths.manage as manage
import ofscraper.utils.profiles.manage as profile_manage
import ofscraper.utils.profiles.tools as profile_tools
from ofscraper.utils.markup import escape_text

TRICKY = "Jo [/b] [red]x[/red]"


def _console():
    buf = io.StringIO()
    return Console(file=buf, width=300, color_system=None, markup=True), buf


def test_welcome_line_with_brackets_in_the_name(monkeypatch):
    con, buf = _console()
    monkeypatch.setattr(me.console, "get_shared_console", lambda: con)
    me.print_user(TRICKY, "user[1]")
    assert f"Welcome, {TRICKY} | user[1]" in buf.getvalue()


def test_deleted_log_file_path_with_brackets(monkeypatch, tmp_path):
    con, buf = _console()
    # "/" isn't allowed in Windows names, so use tags that restyle instead
    folder = tmp_path / "logs [red]"
    folder.mkdir()
    old = folder / "old [bold].log"
    old.write_text("x")
    import os

    os.utime(old, (0, 0))
    monkeypatch.setattr(manage, "console", con)
    monkeypatch.setattr(manage.common_paths, "get_log_folder", lambda: tmp_path)
    monkeypatch.setattr(
        manage.settings, "get_settings", lambda: SimpleNamespace(logs_expire_time=1)
    )
    manage.delete_old_logs()
    manage.delete_empty_folders()
    out = buf.getvalue()
    assert not old.exists()
    assert "old [bold].log" in out
    assert "logs [red]" in out


def test_profile_names_with_brackets(monkeypatch):
    con, buf = _console()
    monkeypatch.setattr(profile_tools, "console", con)
    monkeypatch.setattr(
        profile_tools.profile_data, "get_profile_names", lambda: [TRICKY]
    )
    monkeypatch.setattr(
        profile_tools.profile_data, "get_active_profile", lambda: "a[/x]"
    )
    monkeypatch.setattr(
        profile_tools.profile_data, "get_current_config_profile", lambda: "b[/y]"
    )
    profile_tools.print_profiles()
    out = buf.getvalue()
    assert f"Profile: {TRICKY}" in out
    assert "Active profile: a[/x]" in out
    assert "Default config profile: b[/y]" in out


@pytest.mark.parametrize(
    "value",
    [
        "plain text",
        r"C:\Users\me\logs\[2024]\x.log",
        r"C:\logs\[Old] x\a",
        r"D:\media\[old]",
        r"\[old]",
        "a [/b] b",
        "x[red]_profile",
        "/data/[archive]/OF",
        "a [ b ] c",
    ],
)
@pytest.mark.parametrize("wrap", ["{}", "[bold]{}[/bold] tail"])
def test_escape_text_prints_exactly_as_typed(value, wrap):
    con, buf = _console()
    con.print(wrap.format(escape_text(value)))
    want = wrap.replace("[bold]", "").replace("[/bold]", "").format(value)
    assert buf.getvalue().rstrip("\n") == want


def test_deleted_profile_name_with_brackets(monkeypatch):
    con, buf = _console()
    monkeypatch.setattr(profile_manage, "print", con.print)
    monkeypatch.setattr(profile_manage.tools, "print_profiles", lambda: None)
    monkeypatch.setattr(profile_manage.prompts, "get_profile_prompt", lambda names: "x[red]_profile")
    monkeypatch.setattr(profile_manage.profile_data, "get_profile_names", lambda: ["x[red]_profile"])
    monkeypatch.setattr(profile_manage.profile_data, "get_active_profile", lambda: "main")
    monkeypatch.setattr(profile_manage.common_paths, "get_config_home", lambda: Path("cfg"))
    monkeypatch.setattr(profile_manage.shutil, "rmtree", lambda p: None)
    monkeypatch.setattr(
        profile_manage.manager,
        "Manager",
        SimpleNamespace(profile_manager=SimpleNamespace(delete_profile=lambda: None)),
    )
    profile_manage.delete_profile()
    assert "Successfully deleted x[red]_profile" in buf.getvalue()


def test_db_table_shows_filenames_and_paths_with_brackets(monkeypatch):
    con, buf = _console()
    monkeypatch.setattr(db.console, "get_console", lambda: con)
    monkeypatch.setattr(db, "add_other_handler", lambda log: None)
    manager_ = db.DBManager("a creator", 1)
    manager_.media = [
        {"filename": "new set [ppv] clip.mp4", "directory": r"D:\media\[old]"}
    ]
    manager_.print_dictionary_table()
    out = buf.getvalue()
    assert "new set [ppv] clip.mp4" in out
    assert r"D:\media\[old]" in out


@pytest.mark.parametrize(
    "save,dirformat,filled",
    [
        (r"D:\media", "[{model_username}]", "[alice]"),
        (r"D:\media\[2024]", "{model_username}", "alice"),
        (r"D:\media", r"[Old] x\[{date}]", r"[Old] x\[{date}]"),
        ("/data/[archive]/OF", "{model_username}", "alice"),
        (r"D:\media", "{model_username}", "alice"),
    ],
)
def test_saving_files_to_line(monkeypatch, save, dirformat, filled):
    import ofscraper.commands.scraper.actions.download.download as download

    monkeypatch.setattr(download.common_paths, "get_save_location", lambda: save)
    monkeypatch.setattr(download.config_data, "get_dirformat", lambda: dirformat)
    monkeypatch.setattr(download.config_data, "get_fileformat", lambda: "{filename}.{ext}")
    con, buf = _console()
    con.print(download.save_path_str(username="alice", model_id=1))
    want = str(Path(save, filled, "{filename}.{ext}"))
    assert buf.getvalue().strip() == f"Saving files to {want}"

def test_auth_file_path_with_brackets(monkeypatch):
    con, buf = _console()
    monkeypatch.setattr(auth_warning, "console", con)
    auth_warning.authwarning("C:/cfg [/b]/auth.json")
    assert "C:/cfg [/b]/auth.json" in buf.getvalue()
