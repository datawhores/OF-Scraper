"""system_free_min measures free space on the disk that holds save_location
(#716), not on `/`. OFSC_DISK_SPACE_CHECK_PATH still wins when it's set."""

import json
import os
import pathlib
import shutil
from types import SimpleNamespace

import pytest

import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
import ofscraper.utils.system.free as free


@pytest.fixture
def measured(monkeypatch, tmp_path):
    """A fresh home with a config.json whose save_location is in tmp_path;
    returns the paths shutil.disk_usage was asked about."""
    home = tmp_path / "home"
    config = home / ".config" / "ofscraper" / "config.json"
    config.parent.mkdir(parents=True)
    # an OFSC_DISK_SPACE_CHECK_PATH in the environment running the tests
    # would be measured instead of save_location
    monkeypatch.delenv("DISK_SPACE_CHECK_PATH", raising=False)
    monkeypatch.delenv("OFSC_DISK_SPACE_CHECK_PATH", raising=False)
    monkeypatch.setitem(of_env.get_all_configs(), "DISK_SPACE_CHECK_PATH", "")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(
        settings, "get_settings", lambda: SimpleNamespace(system_free_min=1)
    )
    # paths are compared resolved: a temp folder can sit behind a link
    # (/var on macOS) or a short 8.3 name on Windows
    calls = []
    real = shutil.disk_usage

    def disk_usage(path):
        calls.append(pathlib.Path(path))
        return real(path)

    monkeypatch.setattr(free.shutil, "disk_usage", disk_usage)

    def write_config(save_location, mtime=None):
        config.write_text(
            json.dumps({"file_options": {"save_location": str(save_location)}}),
            encoding="utf-8",
        )
        if mtime is not None:
            os.utime(config, (mtime, mtime))

    return SimpleNamespace(calls=calls, write_config=write_config)


def test_free_space_is_measured_on_the_save_location(measured, tmp_path):
    save = tmp_path / "downloads"
    save.mkdir()
    measured.write_config(save)

    assert free.check_free_size()
    assert measured.calls == [save.resolve()]


def test_a_save_location_not_made_yet_is_measured_on_its_nearest_folder(
    measured, tmp_path
):
    # the first run creates the folder later; its disk is the parent's
    measured.write_config(tmp_path / "not" / "made" / "yet")

    assert free.check_free_size()
    assert measured.calls == [tmp_path.resolve()]


def test_the_env_path_still_wins(measured, tmp_path, monkeypatch):
    save = tmp_path / "downloads"
    save.mkdir()
    measured.write_config(save)
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setenv("DISK_SPACE_CHECK_PATH", str(other))

    assert free.check_free_size()
    assert measured.calls == [other]


def test_config_json_is_read_once_until_it_changes(measured, tmp_path, monkeypatch):
    import ofscraper.utils.config.file as config_file

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    measured.write_config(first, mtime=1_700_000_000)
    reads = []
    real = config_file.open_config
    monkeypatch.setattr(config_file, "open_config", lambda: reads.append(1) or real())

    for _ in range(3):
        assert free.check_free_size()
    assert len(reads) == 1 and measured.calls == [first.resolve()] * 3

    # an edited config.json is read again
    measured.write_config(second, mtime=1_700_000_100)
    assert free.check_free_size()
    assert len(reads) == 2 and measured.calls[-1] == second.resolve()


def test_a_save_location_linked_to_a_missing_folder_is_measured_on_the_target(
    measured, tmp_path
):
    # a symlink to a drive not mounted yet: its disk is the target's, not the
    # disk the link sits on
    target_disk = tmp_path / "mnt"
    target_disk.mkdir()
    link = tmp_path / "downloads"
    try:
        link.symlink_to(target_disk / "external" / "downloads", target_is_directory=True)
    except OSError:
        pytest.skip("this system can't create symlinks")
    measured.write_config(link)

    assert free.check_free_size()
    assert measured.calls == [target_disk.resolve()]


def test_a_lookup_that_another_thread_replaces_mid_call_still_answers(
    measured, tmp_path
):
    # another thread finds config.json edited and reads it again just before
    # this lookup returns: this one still answers with what it read
    import inspect
    import sys

    first, second = tmp_path / "first", tmp_path / "second"
    measured.write_config(first, mtime=1_700_000_000)
    assert free._get_save_location() == str(first)

    lines, start = inspect.getsourcelines(free._get_save_location)
    returns = {
        start + i
        for i, line in enumerate(lines)
        if line.strip().startswith("return")
    }
    switched = []

    def other_thread(frame, event, arg):
        if frame.f_code is not free._get_save_location.__code__:
            return None
        if event == "line" and frame.f_lineno in returns and not switched:
            switched.append(1)
            measured.write_config(second, mtime=1_700_000_100)
            assert free._get_save_location() == str(second)
        return other_thread

    measured.write_config(first, mtime=1_700_000_050)
    previous = sys.gettrace()
    sys.settrace(other_thread)
    try:
        got = free._get_save_location()
    finally:
        sys.settrace(previous)
    assert switched and got == str(first)


def _write_overrides(tmp_path, save, live, videos):
    config = tmp_path / "home" / ".config" / "ofscraper" / "config.json"
    config.write_text(json.dumps({
        "file_options": {"save_location": str(save)},
        "live_options": {"save_location": str(live)},
        "type_options": {"videos": {"save_location": str(videos)}},
    }), encoding="utf-8")


def _media(mediatype):
    return SimpleNamespace(responsetype="Timeline", modified_responsetype="Posts", mediatype=mediatype)


def test_a_file_is_measured_on_the_disk_it_is_saved_on(measured, tmp_path):
    """A type_options save_location on another disk is checked for its own
    files only: a full disk there (or a livestream disk) doesn't stop the
    rest of the scrape"""
    from ofscraper.commands.scraper.actions.download.managers.downloadmanager import DownloadManager

    save, live, videos = (tmp_path / name for name in ("downloads", "live", "videos"))
    for folder in (save, live, videos):
        folder.mkdir()
    _write_overrides(tmp_path, save, live, videos)

    # the scrape-level check: save_location only, as before type_options
    assert free.check_free_size()
    assert measured.calls == [save.resolve()]
    measured.calls.clear()
    DownloadManager._downloadspace(None, _media("Videos"))
    DownloadManager._downloadspace(None, _media("Images"))
    assert measured.calls == [videos.resolve(), save.resolve()]


def test_a_full_override_disk_stops_only_its_files(measured, tmp_path, monkeypatch):
    from ofscraper.commands.scraper.actions.download.managers.downloadmanager import DownloadManager

    save, live, videos = (tmp_path / name for name in ("downloads", "live", "videos"))
    for folder in (save, live, videos):
        folder.mkdir()
    _write_overrides(tmp_path, save, live, videos)
    monkeypatch.setattr(free.shutil, "disk_usage", lambda path: SimpleNamespace(
        free=0 if pathlib.Path(path) == videos.resolve() else 10**12))
    monkeypatch.setattr(free, "alert_full", lambda *a: None)

    assert free.check_free_size()
    DownloadManager._downloadspace(None, _media("Images"))
    with pytest.raises(Exception):
        DownloadManager._downloadspace(None, _media("Videos"))


def test_the_folder_a_download_goes_to_is_worked_out_once(measured, tmp_path, monkeypatch):
    """the check runs before every download; config.json was read again
    each time, even with no limit"""
    import ofscraper.classes.placeholder as placeholder
    from ofscraper.commands.scraper.actions.download.managers.downloadmanager import DownloadManager

    save, live, videos = (tmp_path / name for name in ("downloads", "live", "videos"))
    for folder in (save, live, videos):
        folder.mkdir()
    _write_overrides(tmp_path, save, live, videos)
    calls = []
    real = placeholder.media_templates
    monkeypatch.setattr(placeholder, "media_templates", lambda *a, **k: calls.append(a) or real(*a, **k))
    for _ in range(3):
        DownloadManager._downloadspace(None, _media("Videos"))
    assert len(calls) == 1
    monkeypatch.setattr(settings, "get_settings", lambda: SimpleNamespace(system_free_min=0))
    measured.calls.clear()
    DownloadManager._downloadspace(None, _media("Images"))
    assert len(calls) == 1 and measured.calls == []
