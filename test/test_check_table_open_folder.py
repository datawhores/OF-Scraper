"""Check table: open the download folder (#424).

`o` opens the highlighted row's folder (the file's folder, with the file
selected, when it's downloaded and still on disk; else the creator's folder).
The "Open Download Folder" button opens the creator's folder. Nothing here
starts a real file manager: the opener is stubbed, or its folder is missing.
"""

import asyncio
import os
import pathlib
import queue
import subprocess
import threading
from types import SimpleNamespace

import pytest

import ofscraper.classes.table.app as table_app
import ofscraper.classes.table.utils.open_folder as open_folder
from ofscraper.classes.table.utils.open_folder import OpenError, Target

DIR_FORMAT = "{model_username}/{responsetype}/{mediatype}/"


# ------------------------------------------------------------ picking the path


def _row(username="a_creator", downloaded=False, directory=None, filename=None):
    return {
        "username": username,
        "downloaded": downloaded,
        "directory": directory,
        "filename": filename,
    }


def _downloaded_file(tmp_path, username="a_creator"):
    folder = tmp_path / "save" / username / "Timeline" / "Videos"
    folder.mkdir(parents=True)
    file = folder / "clip.mp4"
    file.write_bytes(b"x")
    return file


def test_downloaded_row_with_its_file_selects_the_file(tmp_path):
    file = _downloaded_file(tmp_path)
    row = _row(downloaded=True, directory=str(file.parent), filename=file.name)

    target = open_folder.row_target(row, root=tmp_path / "save", dir_format=DIR_FORMAT)

    assert target == Target(file, select=True)
    assert target.folder == file.parent


def test_downloaded_row_whose_file_is_gone_opens_the_creator_folder(tmp_path):
    folder = tmp_path / "save" / "a_creator" / "Timeline" / "Videos"
    row = _row(downloaded=True, directory=str(folder), filename="gone.mp4")

    target = open_folder.row_target(row, root=tmp_path / "save", dir_format=DIR_FORMAT)

    assert target == Target(tmp_path / "save" / "a_creator")


def test_downloaded_row_with_no_recorded_file_opens_the_creator_folder(tmp_path):
    row = _row(downloaded=True)

    target = open_folder.row_target(row, root=tmp_path / "save", dir_format=DIR_FORMAT)

    assert target == Target(tmp_path / "save" / "a_creator")


def test_row_not_downloaded_opens_the_creator_folder(tmp_path):
    # even with a file on disk: the database doesn't say it's this media's
    file = _downloaded_file(tmp_path)
    row = _row(downloaded=False, directory=str(file.parent), filename=file.name)

    target = open_folder.row_target(row, root=tmp_path / "save", dir_format=DIR_FORMAT)

    assert target == Target(tmp_path / "save" / "a_creator")


def test_each_creator_gets_its_own_folder(tmp_path):
    root = tmp_path / "save"
    for name in ["a_creator", "b_creator"]:
        target = open_folder.row_target(_row(name), root=root, dir_format=DIR_FORMAT)
        assert target == Target(root / name)


@pytest.mark.parametrize(
    "dir_format, parts",
    [
        ("{model_username}", ["a_creator"]),
        ("{modelusername}/{date}", ["a_creator"]),
        ("{user_name}/{responsetype}", ["a_creator"]),
        # a fixed folder before the creator is part of the creator's folder
        ("OnlyFans/{model_username}/{mediatype}", ["OnlyFans", "a_creator"]),
        # the whole folder name that holds the username (#434 review)
        ("{model_username}_archive/{media_type}", ["a_creator_archive"]),
        ("x_{model_username}-y/{date}", ["x_a_creator-y"]),
        ("{model_username}_x", ["a_creator_x"]),
        (f"{{model_username}}_archive{os.sep}{{media_type}}", ["a_creator_archive"]),
        # escaped braces are part of the name, not fields (#434 re-review)
        ("{model_username}_{{archive}}/{media_type}", ["a_creator_{archive}"]),
        ("{{x}}/{model_username}}}{{/{date}", ["{x}", "a_creator}{"]),
    ],
)
def test_creator_folder_is_dir_format_up_to_the_username(tmp_path, dir_format, parts):
    target = open_folder.creator_target("a_creator", tmp_path, dir_format)
    assert target == Target(tmp_path.joinpath(*parts))


@pytest.mark.parametrize(
    "dir_format",
    [
        "{model_username}/{responsetype}/{mediatype}/",
        "{model_username}_archive/{media_type}",
        "OnlyFans/{model_username}-{model_username}/{date}/",
        "{user_name}",
        "{model_username}_{{archive}}/{media_type}",
    ],
)
def test_creator_folder_holds_what_the_downloader_writes(tmp_path, dir_format):
    # the media folder, built as Placeholders.getmediadir builds it
    variables = {
        "model_username": "a_creator", "modelusername": "a_creator",
        "user_name": "a_creator", "username": "a_creator",
        "responsetype": "Timeline", "mediatype": "Videos",
        "media_type": "Videos", "date": "2024-01-01",
    }
    media_dir = pathlib.Path(
        os.path.normpath(f"{tmp_path}/{pathlib.Path(dir_format.format(**variables))}")
    )

    target = open_folder.creator_target("a_creator", tmp_path, dir_format)

    assert target.note is None
    assert target.path == media_dir or target.path in media_dir.parents
    # the creator's own folder, not the save location
    assert target.path.parent == tmp_path or target.path.parent.parent == tmp_path


@pytest.mark.parametrize(
    "dir_format",
    [
        "{responsetype}/{model_username}/{mediatype}",
        "{first_letter}/{model_username}",
        # the username's folder name also depends on the post
        "{model_username}_{date}/{mediatype}",
        # an escaped brace doesn't hide a later post-dependent placeholder
        "{model_username}_{{x}}_{date}/{mediatype}",
        "{model_username}}}{{{date}/{mediatype}",
        "{mediatype}",
        "",
    ],
)
def test_dir_format_not_starting_with_the_username_uses_the_save_location(
    tmp_path, dir_format
):
    target = open_folder.creator_target("a_creator", tmp_path, dir_format)

    assert target.path == tmp_path
    assert not target.select
    assert "save location" in target.note


def test_no_creator_uses_the_save_location(tmp_path):
    target = open_folder.creator_target(None, tmp_path, DIR_FORMAT)
    assert target.path == tmp_path and target.note


def test_config_values_are_read_when_not_given(tmp_path, monkeypatch):
    monkeypatch.setattr(open_folder, "default_root", lambda: tmp_path / "save")
    monkeypatch.setattr(open_folder, "get_dir_format", lambda: DIR_FORMAT)

    assert open_folder.row_target(_row()) == Target(tmp_path / "save" / "a_creator")


def test_database_gives_each_downloaded_files_directory_and_name(tmp_path):
    import ofscraper.db.operations as operations
    from ofscraper.db.operations_.media import (
        get_media_post_files_downloaded,
        write_media_table_transition,
    )
    from ofscraper.db.operations_.profile import write_models_table, write_profile_table
    from ofscraper.db.transition import modify_tables

    def media(media_id, downloaded, directory=None, filename=None):
        return {
            "media_id": media_id, "post_id": 10, "link": None,
            "directory": directory, "filename": filename, "size": None,
            "api_type": "Posts", "media_type": "Videos", "preview": 0,
            "linked": None, "downloaded": downloaded,
            "created_at": "2024-01-03T03:04:05+00:00",
            "posted_at": "2024-01-03T03:04:06+00:00", "hash": None,
            "model_id": 1, "duration": None, "unlocked": 1,
        }

    db = tmp_path / "db" / "user_data.db"
    db.parent.mkdir()

    async def make():
        await operations.create_tables(db_path=db)
        await write_profile_table(model_id=1, username="a_creator", db_path=db)
        await write_models_table(model_id=1, db_path=db)
        await modify_tables(db_path=db)
        await write_media_table_transition(
            [media(1, 1, "/dl/a", "a.mp4"), media(2, 0), media(3, 1)], db_path=db
        )

    asyncio.run(make())

    assert get_media_post_files_downloaded(db_path=db) == {
        (1, 10): ("/dl/a", "a.mp4"),
        (3, 10): (None, None),
    }
    assert get_media_post_files_downloaded(db_path=db, media_id=1) == {
        (1, 10): ("/dl/a", "a.mp4")
    }


def test_a_download_in_the_table_records_its_file_on_the_row(monkeypatch):
    import ofscraper.commands.check as check

    seen = {}

    def files(**kwargs):
        seen.update(kwargs)
        # recorded on another post of the same media
        return {(7, 99): ("/dl/a", "a.mp4")}

    monkeypatch.setattr(check, "get_media_post_files_downloaded", files)
    row = _row()
    check._record_row_file(row, 1, "a_creator", SimpleNamespace(id=7, post_id=10))

    assert (row["directory"], row["filename"]) == ("/dl/a", "a.mp4")
    assert seen["media_id"] == 7 and seen["model_id"] == 1


def test_a_failed_file_lookup_leaves_the_row_alone(monkeypatch):
    import ofscraper.commands.check as check

    def fail(**kwargs):
        raise OSError("locked")

    monkeypatch.setattr(check, "get_media_post_files_downloaded", fail)
    row = _row()
    check._record_row_file(row, 1, "a_creator", SimpleNamespace(id=7, post_id=10))

    assert row == _row()


# ------------------------------------------------------------------ the opener


def test_open_commands_for_each_os(tmp_path):
    file = tmp_path / "a b" / "clip.mp4"
    folder = tmp_path / "a b"

    win = open_folder.open_command(Target(file, select=True), "Windows")
    assert win == f'explorer /select,"{file}"'
    assert open_folder.open_command(Target(folder), "Windows") == f'explorer "{folder}"'

    assert open_folder.open_command(Target(file, select=True), "Darwin") == [
        "open", "-R", str(file)
    ]
    assert open_folder.open_command(Target(folder), "Darwin") == ["open", str(folder)]

    # xdg-open can't select a file: its folder
    assert open_folder.open_command(Target(file, select=True), "Linux") == [
        "xdg-open", str(folder)
    ]


class _Popen:
    def __init__(self, fail=None):
        self.calls = []
        self.fail = fail
        self.waiting = threading.Event()
        self.release = threading.Event()

    def __call__(self, cmd, **kwargs):
        if self.fail:
            raise self.fail
        self.calls.append((cmd, kwargs))
        return self

    def wait(self):
        self.waiting.set()
        self.release.wait(5)


def test_opener_starts_the_file_manager_without_waiting(tmp_path):
    popen = _Popen()
    open_folder.open_target(Target(tmp_path), system="Darwin", popen=popen)

    # returned while the file manager is still "running"
    assert not popen.release.is_set()
    [(cmd, kwargs)] = popen.calls
    assert cmd == ["open", str(tmp_path)]
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    # and is reaped in the background
    assert popen.waiting.wait(5)
    popen.release.set()


def test_opener_refuses_a_folder_that_does_not_exist(tmp_path):
    popen = _Popen()
    with pytest.raises(OpenError, match="doesn't exist"):
        open_folder.open_target(Target(tmp_path / "missing"), "Windows", popen)
    assert popen.calls == []


def test_opener_without_xdg_open(tmp_path, monkeypatch):
    monkeypatch.setattr(open_folder.shutil, "which", lambda name: None)
    monkeypatch.setenv("DISPLAY", ":0")
    popen = _Popen()
    with pytest.raises(OpenError, match="xdg-open"):
        open_folder.open_target(Target(tmp_path), "Linux", popen)
    assert popen.calls == []


def test_opener_on_linux_without_a_desktop(tmp_path, monkeypatch):
    monkeypatch.setattr(open_folder.shutil, "which", lambda name: "/usr/bin/xdg-open")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    popen = _Popen()
    with pytest.raises(OpenError, match="desktop"):
        open_folder.open_target(Target(tmp_path), "Linux", popen)
    assert popen.calls == []


def test_opener_that_cannot_start(tmp_path):
    popen = _Popen(fail=FileNotFoundError("explorer"))
    with pytest.raises(OpenError, match="file manager"):
        open_folder.open_target(Target(tmp_path), "Windows", popen)


def test_explorer_command_for_a_path_with_spaces_and_a_comma():
    # Explorer reads /select, then the quoted path; the comma stays inside
    # the quotes. Built as a string, so nothing re-quotes it.
    file = pathlib.PureWindowsPath(r"C:\a b\c,d\e f.mp4")

    assert (
        open_folder.open_command(Target(file, select=True), "Windows")
        == r'explorer /select,"C:\a b\c,d\e f.mp4"'
    )
    assert (
        open_folder.open_command(Target(file.parent), "Windows")
        == r'explorer "C:\a b\c,d"'
    )


def test_explorer_gets_that_string_unchanged(tmp_path):
    file = tmp_path / "a b" / "c,d" / "e f.mp4"
    file.parent.mkdir(parents=True)
    file.write_bytes(b"x")
    popen = _Popen()

    open_folder.open_target(Target(file, select=True), "Windows", popen)

    [(cmd, kwargs)] = popen.calls
    assert cmd == f'explorer /select,"{file}"'
    assert "start_new_session" not in kwargs
    popen.release.set()


@pytest.mark.parametrize(
    "system, expected",
    [
        ("Linux", lambda folder: ["xdg-open", str(folder)]),
        ("Darwin", lambda folder: ["open", str(folder)]),
        ("Windows", lambda folder: f'explorer "{folder}"'),
    ],
)
def test_a_relative_save_location_reaches_the_opener_absolute(
    tmp_path, monkeypatch, system, expected
):
    # "-downloads/a_creator" would be read as an option (#434 review)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(open_folder.shutil, "which", lambda name: "/usr/bin/xdg-open")
    monkeypatch.setenv("DISPLAY", ":0")
    folder = tmp_path / "-downloads" / "a_creator"
    folder.mkdir(parents=True)
    popen = _Popen()

    open_folder.open_target(
        Target(pathlib.Path("-downloads", "a_creator")), system, popen
    )

    [(cmd, _kwargs)] = popen.calls
    assert cmd == expected(folder)
    popen.release.set()


def test_a_relative_save_location_gives_an_absolute_creator_folder(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    target = open_folder.creator_target("a_creator", "-downloads", DIR_FORMAT)
    assert target.path == tmp_path / "-downloads" / "a_creator"
    assert target.path.is_absolute()

    fallback = open_folder.creator_target("a_creator", "-downloads", "{date}")
    assert fallback.path == tmp_path / "-downloads"


# ------------------------------------------------------------------- the table


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _table_row(index, username, downloaded=False, directory=None, filename=None):
    return {
        "index": index,
        "number": index,
        "download_cart": "[downloaded]" if downloaded else "[]",
        "username": username,
        "downloaded": downloaded,
        "unlocked": True,
        "download_type": "normal",
        "other_posts_with_media": [],
        "post_media_count": 1,
        "mediatype": "Videos",
        "post_date": "2024-01-01",
        "media": 1,
        "length": "0:01:00",
        "responsetype": "Timeline",
        "price": "Free",
        "post_id": 100 + index,
        "media_id": 1000 + index,
        "text": "a post",
        "directory": directory,
        "filename": filename,
    }


@pytest.fixture
def opened(monkeypatch, tmp_path):
    """Stubbed settings and opener; the list of what would have been opened."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)
    monkeypatch.setattr(table_app, "row_queue", queue.Queue())
    monkeypatch.setattr(open_folder, "default_root", lambda: tmp_path / "save")
    monkeypatch.setattr(open_folder, "get_dir_format", lambda: DIR_FORMAT)

    calls = []
    monkeypatch.setattr(open_folder, "open_target", calls.append)
    return calls


def _drive(rows, steps):
    async def run():
        app = table_app.InputApp()
        app.table_data = rows
        app._sortkey = None
        app._reverse = False
        notes = []
        real_notify = app.notify

        def notify(message, **kwargs):
            notes.append((message, kwargs.get("severity", "information")))
            return real_notify(message, **kwargs)

        app.notify = notify
        async with app.run_test(size=(245, 60)) as pilot:
            await pilot.pause()
            await steps(app, pilot, notes)
            # still running after whatever happened
            assert app.is_running

    asyncio.run(run())


async def _settle(pilot):
    for _ in range(5):
        await pilot.pause(0.02)


def test_o_key_and_button(opened, tmp_path):
    file = _downloaded_file(tmp_path)
    rows = [
        _table_row(1, "a_creator", True, str(file.parent), file.name),
        _table_row(2, "a_creator"),
        _table_row(3, "b_creator", True, str(tmp_path / "nowhere"), "gone.mp4"),
    ]
    save = tmp_path / "save"

    async def steps(app, pilot, notes):
        assert "(o)" in str(app.query_one("#table_instructions").render())
        button = app.query_one("#open_download_folder")
        # beside the send button
        row = app.query_one("#main_action_row")
        assert button.parent is row
        ids = [child.id for child in row.children]
        assert ids.index("open_download_folder") == ids.index("send_downloads_main") + 1

        # downloaded, file on disk: the file, selected
        app.table.move_cursor(row=0)
        await pilot.press("o")
        await _settle(pilot)
        assert opened[-1] == Target(file, select=True)

        # not downloaded: the creator's folder
        app.table.move_cursor(row=1)
        await pilot.press("o")
        await _settle(pilot)
        assert opened[-1] == Target(save / "a_creator")

        # downloaded, file gone: the creator's folder
        app.table.move_cursor(row=2)
        await pilot.press("o")
        await _settle(pilot)
        assert opened[-1] == Target(save / "b_creator")

        # the button: the highlighted row's creator, even on a downloaded row
        await pilot.click("#open_download_folder")
        await _settle(pilot)
        assert opened[-1] == Target(save / "b_creator")

        app.table.move_cursor(row=0)
        await _settle(pilot)
        await pilot.click("#open_download_folder")
        await _settle(pilot)
        assert opened[-1] == Target(save / "a_creator")

        assert len(opened) == 5
        assert notes == []

    _drive(rows, steps)


def test_o_key_does_nothing_with_a_sidebar_open(opened):
    async def steps(app, pilot, notes):
        await pilot.press("ctrl+s")
        await _settle(pilot)
        await pilot.press("o")
        await _settle(pilot)
        assert opened == []

    _drive([_table_row(1, "a_creator")], steps)


def test_button_with_no_rows_uses_the_save_location(opened, tmp_path):
    async def steps(app, pilot, notes):
        await pilot.click("#open_download_folder")
        await _settle(pilot)
        assert [t.path for t in opened] == [tmp_path / "save"]
        # says why it isn't a creator's folder
        assert len(notes) == 1 and "save location" in notes[0][0]

    _drive([], steps)


def test_failing_opener_shows_a_notice_with_the_path(opened, monkeypatch, tmp_path):
    def fail(target):
        raise OpenError("No desktop to open it on")

    monkeypatch.setattr(open_folder, "open_target", fail)

    async def steps(app, pilot, notes):
        await pilot.press("o")
        await _settle(pilot)
        await pilot.click("#open_download_folder")
        await _settle(pilot)

        folder = str(tmp_path / "save" / "a_creator")
        assert notes == [
            (f"No desktop to open it on: {folder}", "warning"),
            (f"No desktop to open it on: {folder}", "warning"),
        ]
        # shown on screen
        assert [n.message for n in app._notifications] == [m for m, _ in notes]

    _drive([_table_row(1, "a_creator")], steps)


def test_any_opener_error_is_a_notice_not_a_crash(opened, monkeypatch):
    def boom(target):
        raise RuntimeError("something broke")

    monkeypatch.setattr(open_folder, "open_target", boom)

    async def steps(app, pilot, notes):
        await pilot.press("o")
        await _settle(pilot)
        assert len(notes) == 1
        assert notes[0][0].startswith("something broke: ")

    _drive([_table_row(1, "a_creator")], steps)


def test_missing_folder_is_a_notice_and_nothing_is_started(opened, monkeypatch, tmp_path):
    # the real opener: the creator's folder doesn't exist yet
    started = []
    monkeypatch.setattr(
        open_folder,
        "open_target",
        lambda target: _real_open_target(target, popen=lambda *a, **k: started.append(a)),
    )

    async def steps(app, pilot, notes):
        await pilot.press("o")
        await _settle(pilot)
        folder = tmp_path / "save" / "a_creator"
        assert notes == [(f"Folder doesn't exist yet: {folder}", "warning")]
        assert not folder.exists()
        assert started == []

    _drive([_table_row(1, "a_creator")], steps)


def test_config_error_is_a_notice(opened, monkeypatch):
    def broken():
        raise ValueError("bad config")

    monkeypatch.setattr(open_folder, "default_root", broken)

    async def steps(app, pilot, notes):
        await pilot.press("o")
        await _settle(pilot)
        assert notes == [("Couldn't work out the download folder: bad config", "warning")]

    _drive([_table_row(1, "a_creator")], steps)


_real_open_target = open_folder.open_target
