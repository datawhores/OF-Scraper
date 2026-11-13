import logging
import pathlib

import pytest

import ofscraper.commands.scraper.actions.utils.globals as common_globals
from ofscraper.commands.scraper.actions.utils import paths


@pytest.fixture(autouse=True)
def empty_dirset(monkeypatch):
    monkeypatch.setattr(common_globals, "dirSet", set(), raising=False)


def test_file_path_records_parent(tmp_path):
    f = tmp_path / "a.jpg"
    f.write_bytes(b"x")
    paths.addGlobalDir(f)
    assert common_globals.dirSet == {tmp_path.resolve()}


def test_dir_path_records_itself(tmp_path):
    paths.addGlobalDir(tmp_path)
    assert common_globals.dirSet == {tmp_path.resolve()}


def test_str_path_is_one_path(tmp_path):
    paths.addGlobalDir(str(tmp_path))
    assert common_globals.dirSet == {tmp_path.resolve()}


def test_unresolvable_path_does_not_raise(tmp_path, monkeypatch):
    # WinError 1005 from Path.resolve on some mapped/virtual drives (#39)
    def boom(self, *a, **k):
        raise OSError(1005, "The volume does not contain a recognized file system")

    monkeypatch.setattr(pathlib.Path, "resolve", boom)
    paths.addGlobalDir(tmp_path)
    paths.addLocalDir(tmp_path / "missing.jpg")
    assert common_globals.dirSet == {tmp_path.absolute()}


@pytest.fixture
def save_root(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "model" / "Posts").mkdir(parents=True)
    monkeypatch.setattr(paths.common_paths, "get_save_location", lambda: str(root))
    dated = []
    monkeypatch.setattr(paths, "set_time", lambda p, t: dated.append(pathlib.Path(p)))
    monkeypatch.setattr(common_globals, "log", logging.getLogger("test"), raising=False)
    return root, dated


def test_dates_folders_up_to_save_root(save_root):
    root, dated = save_root
    paths.addGlobalDir(root / "model" / "Posts")
    paths.setDirectoriesDate()
    assert set(dated) == {(root / "model" / "Posts").resolve(), (root / "model").resolve()}


def test_unnormalized_save_root_still_walks_up(save_root, monkeypatch):
    # dirSet holds resolved paths; an unresolved rootDir made is_relative_to
    # fail and stopped the walk early
    root, dated = save_root
    monkeypatch.setattr(
        paths.common_paths, "get_save_location", lambda: str(root / "model" / "..")
    )
    paths.addGlobalDir(root / "model" / "Posts")
    paths.setDirectoriesDate()
    assert (root / "model").resolve() in dated


def test_samefile_error_does_not_raise(save_root, monkeypatch):
    root, dated = save_root

    def boom(*a):
        raise OSError(1005, "The volume does not contain a recognized file system")

    monkeypatch.setattr(paths.os.path, "samefile", boom)
    paths.addGlobalDir(root / "model" / "Posts")
    paths.setDirectoriesDate()
    assert dated == [(root / "model" / "Posts").resolve()]
