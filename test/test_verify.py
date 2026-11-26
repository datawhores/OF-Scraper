"""ofscraper verify: the library checked against the database, offline."""

import json
import ntpath
import os
import sqlite3
from contextlib import closing
from pathlib import PureWindowsPath
from types import SimpleNamespace

import pytest

import ofscraper.commands.verify as verify
from ofscraper.db.operations_.media import mediaCreate
from ofscraper.db.operations_.posts import postCreate


def snapshot(root):
    return {
        str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def make_library(tmp_path, rows, posts=()):
    """A creator's database at tmp_path/.data/5/user_data.db, its files under
    tmp_path/lib. rows: (media_id, post_id, filename, recorded size, bytes on
    disk or None for no file, api_type, extra columns)."""
    db = tmp_path / ".data" / "5" / "user_data.db"
    db.parent.mkdir(parents=True)
    lib = tmp_path / "lib"
    lib.mkdir()
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute(mediaCreate)
        conn.execute(postCreate)
        for post_id, deleted in posts:
            conn.execute("INSERT INTO posts (post_id, text, model_id, is_deleted) VALUES (?, '', 5, ?)", (post_id, deleted))
        for media_id, post_id, name, size, content, api_type, extra in rows:
            if content is not None and name:
                (lib / name).write_bytes(content)
            conn.execute(
                "INSERT INTO medias (media_id, post_id, directory, filename, size, api_type, media_type,"
                " downloaded, model_id, unlocked, skip_permanent) VALUES (?,?,?,?,?,?,'Images',?,5,?,?)",
                (media_id, post_id, str(lib) if name else None, name, size, api_type,
                 extra.get("downloaded", 1), extra.get("unlocked", 1), extra.get("skip_permanent", 0)),
            )
    return db, lib


@pytest.fixture
def library(tmp_path):
    return make_library(tmp_path, [
        (1, 100, "ok.jpg", 3, b"abc", "Timeline", {}),
        (2, 101, "gone.jpg", 3, None, "Timeline", {}),
        (3, 102, "empty.jpg", 3, b"", "Messages", {}),
        (4, 103, "edited.jpg", 3, b"abcdef", "Timeline", {}),
        (5, 104, None, None, None, "Timeline", {"skip_permanent": 1}),
        (6, 105, "story.jpg", 3, None, "Stories", {}),
        (7, 106, "notyet.jpg", 3, None, "Timeline", {"downloaded": 0}),
        # one media in two posts: one row's file is fine, so the media is
        (8, 107, "shared.jpg", 3, b"abc", "Timeline", {}),
        (8, 108, "shared.jpg", 3, None, "Archived", {}),
        (9, 109, "deletedpost.jpg", 3, None, "Timeline", {}),
    ], posts=[(109, 1)])


def test_findings(library):
    db, lib = library
    report = verify.verify([db])
    (creator,) = report["creators"]
    assert {k: creator[k] for k in ("missing", "empty", "size_differs", "no_file_recorded", "ok")} == {
        "missing": 3, "empty": 1, "size_differs": 1, "no_file_recorded": 1, "ok": 2,
    }
    assert creator["skip_permanent"] == 1
    assert creator["media_checked"] == 8  # media 7 isn't marked downloaded
    by_media = {f["media_id"]: f for f in creator["findings"]}
    assert set(by_media) == {"2", "3", "4", "6", "9"}
    assert by_media["2"]["finding"] == "missing" and by_media["2"]["path"] == str(lib / "gone.jpg")
    assert by_media["4"] == {
        "finding": "size_differs", "media_id": "4", "post_id": "103", "area": "Timeline",
        "path": str(lib / "edited.jpg"), "recorded_size": 3, "size": 6,
    }
    # a reset can't bring these back
    assert by_media["6"]["not_recoverable"] == "stories expire"
    assert by_media["9"]["not_recoverable"] == "the post was deleted"
    assert "not_recoverable" not in by_media["2"]
    assert creator["not_recoverable"] == 2
    assert report["totals"]["missing"] == 3 and report["applied"] is False


def test_the_preview_changes_nothing(library, tmp_path):
    before = snapshot(tmp_path)
    verify.verify([tmp_path / ".data"])
    assert snapshot(tmp_path) == before


def test_path_map_reads_paths_recorded_elsewhere(tmp_path):
    db, lib = make_library(tmp_path, [(1, 100, "ok.jpg", 3, b"abc", "Timeline", {})])
    # a full path on this system, recorded on another machine
    recorded = r"Z:\data\lib" if os.name == "nt" else "/data/lib"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE medias SET directory = ?", (recorded,))
    assert verify.verify([db])["totals"]["missing"] == 1
    report = verify.verify([db], mappings=[(recorded, str(lib))])
    assert report["totals"] == {**report["totals"], "ok": 1, "missing": 0}


def test_relative_paths_need_path_root(tmp_path):
    db, lib = make_library(tmp_path, [(1, 100, "ok.jpg", 3, b"abc", "Timeline", {})])
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE medias SET directory = 'lib'")
    with pytest.raises(ValueError, match="--path-root"):
        verify.verify([db])
    assert verify.verify([db], path_root=tmp_path)["totals"]["ok"] == 1


def test_sample_limits_the_list_not_the_counts(tmp_path):
    db, _ = make_library(tmp_path, [(i, 100 + i, f"{i}.jpg", 3, None, "Timeline", {}) for i in range(1, 6)])
    (creator,) = verify.verify([db], sample=2)["creators"]
    assert creator["missing"] == 5 and len(creator["findings"]) == 2


def test_missing_creator_folder_is_listed(tmp_path):
    db, lib = make_library(tmp_path, [(1, 100, "gone.jpg", 3, None, "Timeline", {})])
    lib.rmdir()
    (creator,) = verify.verify([db])["creators"]
    assert creator["folders_missing"] == [str(lib)]


def test_command_line(library, capsys, tmp_path):
    db, _ = library
    assert verify.main([str(tmp_path / ".data")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["totals"]["missing"] == 3
    with pytest.raises(SystemExit) as e:
        verify.main([])
    assert e.value.code == 2
    with pytest.raises(SystemExit) as e:
        verify.main([str(tmp_path / "nothing-here")])
    assert e.value.code == 1


def test_routed_as_ofscraper_verify(library, capsys, tmp_path):
    import ofscraper.__main__ as entrypoint

    assert entrypoint.main(["verify", str(tmp_path / ".data")]) == 0
    assert json.loads(capsys.readouterr().out)["totals"]["empty"] == 1


def test_postgres_needs_creator(monkeypatch):
    monkeypatch.setenv("OFSC_DATABASE_URL", "postgresql://localhost/x")
    with pytest.raises(SystemExit) as e:
        verify.main(["--postgres"])
    assert e.value.code == 2
    monkeypatch.delenv("OFSC_DATABASE_URL")
    with pytest.raises(SystemExit) as e:
        verify.main(["--postgres", "--creator", "a creator"])
    assert e.value.code == 2


# --- --apply ---

def downloaded(db):
    with closing(sqlite3.connect(db)) as conn:
        return dict(conn.execute("SELECT id, downloaded FROM medias ORDER BY id"))


def by_media_id(db):
    with closing(sqlite3.connect(db)) as conn:
        return {m: d for m, d in conn.execute("SELECT media_id, MIN(downloaded) FROM medias GROUP BY media_id")}


def test_apply_resets_missing_and_empty_and_moves_empty_aside(library):
    db, lib = library
    report = verify.verify([db], apply=True)
    (creator,) = report["creators"]
    # 2 missing and 3 empty; 6 (a story) and 9 (deleted post) can't come back
    assert creator["media_reset"] == 2 and creator["files_moved_aside"] == 1
    state = by_media_id(db)
    assert state[2] == 0 and state[3] == 0
    assert state[1] == 1 and state[4] == 1 and state[6] == 1 and state[9] == 1
    # no_file_recorded and skip_permanent rows are never changed
    assert state[5] == 1
    assert not (lib / "empty.jpg").exists() and (lib / "empty.jpg.bad").exists()
    assert (lib / "edited.jpg").exists()
    assert os.path.exists(creator["undo_file"])


def test_reset_size_differs_moves_the_file_aside(library):
    db, lib = library
    verify.verify([db], apply=True, reset_size_differs=True)
    assert by_media_id(db)[4] == 0
    assert (lib / "edited.jpg.bad").read_bytes() == b"abcdef"


def test_a_bad_name_that_is_taken_gets_a_number(library):
    db, lib = library
    (lib / "empty.jpg.bad").write_bytes(b"older")
    verify.verify([db], apply=True)
    assert (lib / "empty.jpg.bad").read_bytes() == b"older"
    assert (lib / "empty.jpg.2.bad").exists()


def test_a_media_in_several_posts_has_every_row_reset_and_restored(tmp_path):
    db, lib = make_library(tmp_path, [
        (1, 100, "gone.jpg", 3, None, "Timeline", {}),
        (1, 101, "gone.jpg", 3, None, "Archived", {}),
        (1, 102, "gone.jpg", 3, None, "Messages", {}),
        (2, 103, "ok.jpg", 3, b"abc", "Timeline", {}),
    ])
    before = downloaded(db)
    report = verify.verify([db], apply=True)
    assert set(downloaded(db).values()) == {0, 1}
    assert [d for d in downloaded(db).values()].count(0) == 3
    undo_file = report["creators"][0]["undo_file"]
    assert verify.undo(undo_file)["rows_to_restore"] == 3
    assert downloaded(db) != before  # the preview changed nothing
    assert verify.undo(undo_file, apply=True)["rows_to_restore"] == 3
    assert downloaded(db) == before


def one_empty_file_for_two_media(tmp_path):
    return make_library(tmp_path, [
        (1, 100, "shared.jpg", 3, b"", "Timeline", {}),
        (2, 101, "shared.jpg", 3, b"", "Timeline", {}),
        (3, 102, "ok.jpg", 3, b"abc", "Timeline", {}),
    ])


def test_two_media_with_one_empty_file_move_it_aside_once(tmp_path):
    db, lib = one_empty_file_for_two_media(tmp_path)
    before = downloaded(db)
    (creator,) = verify.verify([db], apply=True)["creators"]
    assert creator["media_reset"] == 2 and creator["files_moved_aside"] == 1
    assert by_media_id(db) == {1: 0, 2: 0, 3: 1}
    assert sorted(p.name for p in lib.iterdir()) == ["ok.jpg", "shared.jpg.bad"]
    undo_file = creator["undo_file"]
    with open(undo_file, encoding="utf-8") as undo:
        assert json.load(undo)["renames"] == [[str(lib / "shared.jpg"), str(lib / "shared.jpg.bad")]]

    done = verify.undo(undo_file, apply=True)
    assert (done["rows_to_restore"], done["files_to_rename_back"]) == (2, 1)
    assert downloaded(db) == before
    assert sorted(p.name for p in lib.iterdir()) == ["ok.jpg", "shared.jpg"]


def test_an_undo_file_naming_one_rename_twice_puts_the_file_back_once(tmp_path):
    db, lib = one_empty_file_for_two_media(tmp_path)
    before = downloaded(db)
    undo_file = verify.verify([db], apply=True)["creators"][0]["undo_file"]
    with open(undo_file, encoding="utf-8") as undo:
        record = json.load(undo)
    record["renames"] *= 2
    with open(undo_file, "w", encoding="utf-8") as undo:
        json.dump(record, undo)

    assert verify.undo(undo_file, apply=True)["files_to_rename_back"] == 1
    assert downloaded(db) == before
    assert sorted(p.name for p in lib.iterdir()) == ["ok.jpg", "shared.jpg"]


def test_undo_puts_files_back(library):
    db, lib = library
    before = downloaded(db)
    report = verify.verify([db], apply=True, reset_size_differs=True)
    result = verify.undo(report["creators"][0]["undo_file"], apply=True)
    assert result["files_to_rename_back"] == 2
    assert (lib / "empty.jpg").exists() and (lib / "edited.jpg").read_bytes() == b"abcdef"
    assert not list(lib.glob("*.bad"))
    assert downloaded(db) == before


def test_an_interrupted_apply_changes_nothing(library, tmp_path, monkeypatch):
    db, lib = library
    before = snapshot(tmp_path)
    real = sqlite3.Connection.execute

    class Stopping(sqlite3.Connection):
        def execute(self, sql, *args):
            if sql.startswith("UPDATE medias"):
                raise KeyboardInterrupt
            return real(self, sql, *args)

    real_connect = sqlite3.connect
    monkeypatch.setattr(verify.sqlite3, "connect", lambda *a, **k: real_connect(*a, factory=Stopping, **k))
    with pytest.raises(KeyboardInterrupt):
        verify.verify([db], apply=True)
    monkeypatch.undo()
    assert snapshot(tmp_path) == before


def test_an_undo_file_left_by_a_stopped_apply_restores_the_start(library, tmp_path):
    """Stopped after the renames and the row changes were sent, before the
    commit was known: what the undo file names is put back."""
    db, lib = library
    before = downloaded(db)
    report = verify.verify([db], apply=True)
    undo_file = report["creators"][0]["undo_file"]
    # as if the commit had arrived but this run never heard: undo puts it back
    verify.undo(undo_file, apply=True)
    assert downloaded(db) == before and (lib / "empty.jpg").exists()
    # and running it again finds nothing more to do
    assert verify.undo(undo_file) == {"applied": False, "rows_to_restore": 0, "files_to_rename_back": 0}


def test_the_guard_leaves_a_creator_with_a_missing_folder_alone(tmp_path):
    db, lib = make_library(tmp_path, [(i, 100 + i, f"{i}.jpg", 3, b"abc", "Timeline", {}) for i in range(1, 4)])
    before = downloaded(db)
    for f in lib.iterdir():
        f.unlink()
    lib.rmdir()
    (creator,) = verify.verify([db], apply=True)["creators"]
    assert "isn't there" in creator["left_alone"] and creator["media_reset"] == 0
    assert downloaded(db) == before and creator["undo_file"] is None
    (creator,) = verify.verify([db], apply=True, allow_missing=True)["creators"]
    assert creator["media_reset"] == 3


def test_the_guard_leaves_a_creator_with_most_files_missing_alone(tmp_path):
    rows = [(i, 100 + i, f"{i}.jpg", 3, None if i <= 6 else b"abc", "Timeline", {}) for i in range(1, 11)]
    db, lib = make_library(tmp_path, rows)
    report = verify.verify([db], apply=True)
    (creator,) = report["creators"]
    assert "6 of 10 files are missing" in creator["left_alone"]
    assert report["totals"]["creators_left_alone"] == 1
    assert set(by_media_id(db).values()) == {1}
    assert verify.verify([db], apply=True, allow_missing=True)["totals"]["media_reset"] == 6


def test_the_preview_says_what_apply_would_do(library, tmp_path):
    db, _ = library
    before = snapshot(tmp_path)
    (creator,) = verify.verify([db])["creators"]
    assert creator["media_to_reset"] == 2 and creator["files_to_move_aside"] == 1
    assert snapshot(tmp_path) == before


def test_command_line_apply_and_undo(library, capsys, tmp_path):
    db, lib = library
    before = downloaded(db)
    assert verify.main([str(db), "--apply"]) == 0
    undo_file = json.loads(capsys.readouterr().out)["creators"][0]["undo_file"]
    assert verify.main(["--undo", undo_file, "--apply"]) == 0
    assert json.loads(capsys.readouterr().out)["rows_to_restore"] == 2
    assert downloaded(db) == before
    for wrong in (["--undo", undo_file, str(db)], ["--undo", undo_file, "--reset-size-differs"]):
        with pytest.raises(SystemExit) as e:
            verify.main(wrong)
        assert e.value.code == 2


# --- --untracked ---

def test_untracked_lists_files_no_row_points_to(library, tmp_path):
    db, lib = library
    (lib / "stray.jpg").write_bytes(b"x")
    (lib / "notyet.jpg").write_bytes(b"abc")  # a row names it, not downloaded yet
    for name in ("post.txt", "a.mp4.part", "b.jpg.duplicate", "c.jpg.bad", "show_live.mp4",
                 "show_live_part2.mp4", "show_chat.jsonl", "user_data.db.verify-undo-1.json", "Thumbs.db"):
        (lib / name).write_bytes(b"x")
    (lib / "sub").mkdir()
    before = snapshot(tmp_path)
    (creator,) = verify.verify([db], untracked=True)["creators"]
    assert creator["untracked_files"] == [str(lib / "stray.jpg")]
    assert creator["untracked"] == 1 and creator["not_in_database"] == 9
    assert snapshot(tmp_path) == before
    assert "untracked" not in verify.verify([db])["creators"][0]


# --- --hash ---

def set_hash(db, media_id, value):
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("UPDATE medias SET hash = ? WHERE media_id = ?", (value, media_id))


def test_hash_finds_a_changed_file_of_the_right_size(tmp_path):
    db, lib = make_library(tmp_path, [
        (1, 100, "same.jpg", 3, b"abc", "Timeline", {}),
        (2, 101, "changed.jpg", 3, b"xyz", "Timeline", {}),
        (3, 102, "nohash.jpg", 3, b"abc", "Timeline", {}),
    ])
    set_hash(db, 1, verify.file_hash(lib / "same.jpg"))
    set_hash(db, 2, verify.file_hash(lib / "same.jpg"))
    # off by default: the files are the recorded size
    assert verify.verify([db])["totals"]["ok"] == 3
    (creator,) = verify.verify([db], hash=True)["creators"]
    assert creator["hash_differs"] == 1 and creator["ok"] == 2
    assert creator["hash_not_recorded"] == 1
    assert creator["findings"][0]["path"] == str(lib / "changed.jpg")
    # not reset unless asked
    (creator,) = verify.verify([db], apply=True, hash=True)["creators"]
    assert creator["media_reset"] == 0
    (creator,) = verify.verify([db], apply=True, reset_hash_differs=True)["creators"]
    assert creator["media_reset"] == 1 and (lib / "changed.jpg.bad").exists()


def test_the_hash_is_the_one_the_scraper_records(tmp_path):
    import xxhash

    path = tmp_path / "f"
    path.write_bytes(b"some bytes" * 100000)
    assert verify.file_hash(path) == xxhash.xxh128(path.read_bytes()).hexdigest()


# --- review follow-up ---

def two_creators(tmp_path):
    """Two creators' databases, each with one missing file to reset."""
    made = []
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
        made.append(make_library(tmp_path / name, [
            (1, 100, "gone.jpg", 3, None, "Timeline", {}),
            (2, 101, "ok1.jpg", 3, b"abc", "Timeline", {}),
            (3, 102, "ok2.jpg", 3, b"abc", "Timeline", {}),
        ]))
    return made


@pytest.mark.parametrize("stop, code", [(KeyboardInterrupt, 130), (OSError("disk gone"), 1)])
def test_a_multi_creator_apply_stopped_partway_names_what_it_changed(tmp_path, capsys, monkeypatch, stop, code):
    (db_a, _), (db_b, _) = two_creators(tmp_path)
    real = verify._apply_file

    def second_stops(path, options):
        if path == db_b:
            raise stop
        return real(path, options)

    monkeypatch.setattr(verify, "_apply_file", second_stops)
    with pytest.raises(SystemExit) as e:
        verify.main([str(db_a), str(db_b), "--apply"])
    assert e.value.code == code
    out = capsys.readouterr()
    (undo_file,) = tmp_path.glob("a/.data/5/user_data.db.verify-undo-*.json")
    assert "Nothing was changed" not in out.err
    assert str(undo_file) in out.err
    # the report of what was done is printed as well
    report = json.loads(out.out)
    assert [c["undo_file"] for c in report["creators"]] == [str(undo_file)]
    assert by_media_id(db_a)[1] == 0 and by_media_id(db_b)[1] == 1


def test_a_multi_creator_apply_stopped_before_any_change_says_nothing_changed(tmp_path, capsys, monkeypatch):
    (db_a, _), (db_b, _) = two_creators(tmp_path)
    monkeypatch.setattr(verify, "_apply_file", lambda *a: (_ for _ in ()).throw(KeyboardInterrupt))
    with pytest.raises(SystemExit) as e:
        verify.main([str(db_a), str(db_b), "--apply"])
    assert e.value.code == 130
    assert "Nothing was changed" in capsys.readouterr().err


def test_an_undo_that_fails_partway_puts_the_renames_back(library, monkeypatch):
    db, lib = library
    report = verify.verify([db], apply=True, reset_size_differs=True)
    after_apply = downloaded(db)
    undo_file = report["creators"][0]["undo_file"]
    real = os.rename
    calls = []

    def second_fails(src, dst):
        calls.append(src)
        if len(calls) == 2:
            raise OSError("in use")
        return real(src, dst)

    monkeypatch.setattr(verify.os, "rename", second_fails)
    with pytest.raises(OSError, match="in use"):
        verify.undo(undo_file, apply=True)
    monkeypatch.undo()
    # the database rolled back, so the files keep their .bad names too
    assert downloaded(db) == after_apply
    assert sorted(p.name for p in lib.glob("*.bad")) == ["edited.jpg.bad", "empty.jpg.bad"]
    # and the undo can still be run in full
    assert verify.undo(undo_file, apply=True)["files_to_rename_back"] == 2


def test_files_warns_when_postgresql_is_on(library, capsys, monkeypatch):
    db, _ = library
    monkeypatch.setenv("OFSC_DATABASE_URL", "postgresql://localhost/x")
    assert verify.main([str(db)]) == 0
    assert "OFSC_DATABASE_URL is set" in capsys.readouterr().err


def test_a_media_in_a_deleted_post_and_a_live_one_can_be_reset(tmp_path):
    db, _ = make_library(tmp_path, [
        (1, 100, "gone.jpg", 3, None, "Timeline", {}),
        (1, 101, "gone.jpg", 3, None, "Timeline", {}),
        (2, 102, "ok.jpg", 3, b"abc", "Timeline", {}),
        (3, 103, "ok3.jpg", 3, b"abc", "Timeline", {}),
    ], posts=[(100, 1), (101, 0)])
    (creator,) = verify.verify([db])["creators"]
    assert creator["not_recoverable"] == 0 and creator["media_to_reset"] == 1


def test_a_broken_link_or_a_folder_is_not_reset(tmp_path):
    db, lib = make_library(tmp_path, [
        (1, 100, "link.jpg", 3, None, "Timeline", {}),
        (2, 101, "folder.jpg", 3, None, "Timeline", {}),
        (3, 102, "ok.jpg", 3, b"abc", "Timeline", {}),
        (4, 103, "ok4.jpg", 3, b"abc", "Timeline", {}),
        (5, 104, "ok5.jpg", 3, b"abc", "Timeline", {}),
    ])
    try:
        (lib / "link.jpg").symlink_to(tmp_path / "unplugged" / "link.jpg")
    except OSError as error:
        # Windows needs a privilege or Developer Mode to make one
        pytest.skip(f"can't make a symlink here: {error}")
    (lib / "folder.jpg").mkdir()
    (creator,) = verify.verify([db], hash=True)["creators"]
    reasons = {f["media_id"]: f.get("not_recoverable") for f in creator["findings"]}
    assert "link" in reasons["1"] and "folder" in reasons["2"]
    (creator,) = verify.verify([db], apply=True)["creators"]
    assert creator["media_reset"] == 0 and creator["undo_file"] is None
    assert (lib / "folder.jpg").is_dir() and (lib / "link.jpg").is_symlink()


def test_a_windows_path_read_on_linux_needs_a_path_map(tmp_path):
    if os.name == "nt":
        pytest.skip("the other system's paths here are POSIX ones")
    db, lib = make_library(tmp_path, [(1, 100, "ok.jpg", 3, b"abc", "Timeline", {})])
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute(r"UPDATE medias SET directory = 'D:\lib'")
    for path_root in (None, tmp_path):
        with pytest.raises(ValueError, match="--path-map"):
            verify.verify([db], path_root=path_root)


def _windows_312_isabs(path):
    """ntpath.isabs before Python 3.13: a path rooted at / counts as full."""
    path = ntpath.splitdrive(os.fspath(path))[1]
    return len(path) > 0 and path[0] in "\\/"


def test_a_posix_path_read_on_windows_needs_a_path_map(monkeypatch):
    # Windows Python 3.11 and 3.12, simulated: ntpath, and its isabs that took
    # /mnt/lib for a full path although it names no drive.
    import ofscraper.commands.recover_collisions as recover_collisions

    windows_path = SimpleNamespace(**{**vars(ntpath), "isabs": _windows_312_isabs})
    monkeypatch.setattr(verify, "os", SimpleNamespace(path=windows_path, name="nt"))
    monkeypatch.setattr(verify, "Path", PureWindowsPath)
    monkeypatch.setattr(recover_collisions, "os", SimpleNamespace(name="nt"))
    for path_root in (None, r"C:\run"):
        with pytest.raises(ValueError, match="--path-map"):
            verify._full_path("/mnt/lib", "ok.jpg", path_root, None)
    assert verify._full_path(r"D:\lib", "ok.jpg", None, None) == r"D:\lib\ok.jpg"


def test_left_alone_resets_nothing_in_the_totals(tmp_path):
    rows = [(i, 100 + i, f"{i}.jpg", 3, None if i <= 6 else b"abc", "Timeline", {}) for i in range(1, 11)]
    db, _ = make_library(tmp_path, rows)
    for apply in (False, True):
        report = verify.verify([db], apply=apply)
        assert report["creators"][0]["left_alone"]
        assert report["totals"]["media_to_reset"] == 0
        assert report["creators"][0]["files_to_move_aside"] == 0


def per_post_library(tmp_path, folders):
    """Creator 5's database; each file in its own post folder under
    tmp_path/save/creator/Posts. folders: {post_id: [file names]}, all on
    disk at first."""
    db = tmp_path / ".data" / "5" / "user_data.db"
    db.parent.mkdir(parents=True)
    posts = tmp_path / "save" / "creator" / "Posts"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute(mediaCreate)
        media_id = 0
        for post_id, names in folders.items():
            (posts / str(post_id)).mkdir(parents=True)
            for name in names:
                media_id += 1
                (posts / str(post_id) / name).write_bytes(b"abc")
                conn.execute(
                    "INSERT INTO medias (media_id, post_id, directory, filename, size, api_type, media_type,"
                    " downloaded, model_id, unlocked) VALUES (?, ?, ?, ?, 3, 'Timeline', 'Images', 1, 5, 1)",
                    (media_id, post_id, str(posts / str(post_id)), name),
                )
    return db, posts


def test_a_deleted_post_folder_is_reset(tmp_path):
    # with a folder for each post, a missing file usually means a missing
    # folder: the creator's folder is there, so the file is really gone
    import shutil

    db, posts = per_post_library(tmp_path, {post: [f"{post}.jpg"] for post in range(101, 106)})
    shutil.rmtree(posts / "103")

    (creator,) = verify.verify([db], apply=True)["creators"]

    assert "left_alone" not in creator and creator["media_reset"] == 1
    assert by_media_id(db)[3] == 0


@pytest.mark.parametrize("gone", ["creator", "save"])
def test_a_missing_creator_or_save_folder_leaves_the_creator_alone(tmp_path, gone):
    import shutil

    db, posts = per_post_library(tmp_path, {post: [f"{post}.jpg"] for post in range(101, 106)})
    folder = posts.parent if gone == "creator" else posts.parent.parent
    shutil.rmtree(folder)
    before = downloaded(db)

    (creator,) = verify.verify([db], apply=True)["creators"]

    assert f"the creator's folder {posts} isn't there" in creator["left_alone"]
    assert creator["media_reset"] == 0 and downloaded(db) == before
    (creator,) = verify.verify([db], apply=True, allow_missing=True)["creators"]
    assert creator["media_reset"] == 5


def test_a_missing_file_whose_folder_is_gone_leaves_the_creator_alone(tmp_path, monkeypatch):
    # most files are there, but two are recorded on a second drive that isn't
    # mounted: the percentage alone wouldn't stop it
    rows = [(i, 100 + i, f"{i}.jpg", 3, b"abc", "Timeline", {}) for i in range(1, 11)]
    rows += [(11, 111, "gone.jpg", 3, None, "Timeline", {})]
    db, lib = make_library(tmp_path, rows)
    # lib stands in for a drive mounted in tmp_path; other-drive isn't mounted
    monkeypatch.setattr(verify, "MOUNT_PARENTS", (str(tmp_path),))
    unplugged = tmp_path / "other-drive" / "Videos"
    with closing(sqlite3.connect(db)) as conn, conn:
        for media_id in (12, 13):
            conn.execute(
                "INSERT INTO medias (media_id, post_id, directory, filename, size, api_type, media_type,"
                " downloaded, model_id, unlocked) VALUES (?, ?, ?, ?, 3, 'Timeline', 'Videos', 1, 5, 1)",
                (media_id, 100 + media_id, str(unplugged), f"{media_id}.mp4"),
            )
    before = downloaded(db)

    (creator,) = verify.verify([db], apply=True)["creators"]

    assert str(unplugged) in creator["left_alone"] and creator["media_reset"] == 0
    assert downloaded(db) == before and creator["undo_file"] is None
    (creator,) = verify.verify([db], apply=True, allow_missing=True)["creators"]
    assert creator["media_reset"] == 3


def two_drive_library(tmp_path):
    """Creator 5's files on two drives mounted under tmp_path/mnt: eight
    posts on disk1, two on disk2. Each post has its own folder."""
    db = tmp_path / ".data" / "5" / "user_data.db"
    db.parent.mkdir(parents=True)
    mnt = tmp_path / "mnt"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute(mediaCreate)
        for media_id in range(1, 11):
            disk = "disk1" if media_id <= 8 else "disk2"
            folder = mnt / disk / "creator" / "Posts" / str(100 + media_id)
            folder.mkdir(parents=True)
            (folder / f"{media_id}.jpg").write_bytes(b"abc")
            conn.execute(
                "INSERT INTO medias (media_id, post_id, directory, filename, size, api_type, media_type,"
                " downloaded, model_id, unlocked) VALUES (?, ?, ?, ?, 3, 'Timeline', 'Images', 1, 5, 1)",
                (media_id, 100 + media_id, str(folder), f"{media_id}.jpg"),
            )
    return db, mnt


def test_an_unplugged_drive_that_leaves_its_empty_mount_folder_leaves_the_creator_alone(tmp_path, monkeypatch):
    # on Linux an unmounted drive usually leaves its empty mount folder
    # (fstab, Docker bind mounts): disk2 is there but empty, and only two of
    # ten files are on it, so the percentage alone wouldn't stop it
    import shutil

    monkeypatch.setattr(verify, "MOUNT_PARENTS", (str(tmp_path),))
    db, mnt = two_drive_library(tmp_path)
    shutil.rmtree(mnt / "disk2")
    (mnt / "disk2").mkdir()
    before = downloaded(db)

    (creator,) = verify.verify([db], apply=True)["creators"]

    assert str(mnt / "disk2") in creator["left_alone"] and creator["media_reset"] == 0
    assert downloaded(db) == before
    (creator,) = verify.verify([db], apply=True, allow_missing=True)["creators"]
    assert creator["media_reset"] == 2


def test_a_deleted_post_folder_on_one_of_two_drives_is_reset(tmp_path, monkeypatch):
    import shutil

    monkeypatch.setattr(verify, "MOUNT_PARENTS", (str(tmp_path),))
    db, mnt = two_drive_library(tmp_path)
    shutil.rmtree(mnt / "disk2" / "creator" / "Posts" / "110")

    (creator,) = verify.verify([db], apply=True)["creators"]

    assert "left_alone" not in creator and creator["media_reset"] == 1
    assert by_media_id(db)[10] == 0


def test_creators_sharing_one_database_are_guarded_and_reset_each_on_their_own(tmp_path):
    # creator 5: one file of four missing, in a folder that is there
    rows = [(i, 100 + i, f"{i}.jpg", 3, b"abc", "Timeline", {}) for i in range(1, 4)]
    rows += [(4, 104, "gone.jpg", 3, None, "Timeline", {})]
    db, lib = make_library(tmp_path, rows)
    # creator 6, in the same database: every file missing
    with closing(sqlite3.connect(db)) as conn, conn:
        for media_id in range(20, 26):
            conn.execute(
                "INSERT INTO medias (media_id, post_id, directory, filename, size, api_type, media_type,"
                " downloaded, model_id, unlocked) VALUES (?, ?, ?, ?, 3, 'Timeline', 'Images', 1, 6, 1)",
                (media_id, 100 + media_id, str(lib), f"{media_id}.jpg"),
            )

    report = verify.verify([db], apply=True)

    (creator,) = report["creators"]
    assert "creator 6" in creator["left_alone"] and "creator 5" not in creator["left_alone"]
    assert creator["media_reset"] == 1 and report["totals"]["creators_left_alone"] == 1
    state = by_media_id(db)
    assert state[4] == 0
    assert all(state[m] == 1 for m in range(20, 26))


def folds_case(folder):
    return os.path.exists(str(folder).swapcase()) and os.path.samefile(folder, str(folder).swapcase())


def test_a_file_spelt_in_another_unicode_form_or_case_is_found(tmp_path):
    import unicodedata

    nfc = unicodedata.normalize("NFC", "café.jpg")
    nfd = unicodedata.normalize("NFD", "café.jpg")
    upper_nfc = unicodedata.normalize("NFC", "CAFÉ2.jpg")
    lower_nfd = unicodedata.normalize("NFD", "café2.jpg")
    empty_nfd = unicodedata.normalize("NFD", "vidé.jpg")
    db, lib = make_library(tmp_path, [
        (1, 100, nfc, 3, None, "Timeline", {}),
        (2, 101, upper_nfc, 3, None, "Timeline", {}),
        (3, 102, unicodedata.normalize("NFC", "vidé.jpg"), 3, None, "Timeline", {}),
        (4, 103, "ok.jpg", 3, b"abc", "Timeline", {}),
    ])
    # the files as a Mac writes them: decomposed
    (lib / nfd).write_bytes(b"abc")
    (lib / lower_nfd).write_bytes(b"abc")
    (lib / empty_nfd).write_bytes(b"")
    if nfc in os.listdir(lib):
        pytest.skip("this disk stores names in one Unicode form")
    case_found = folds_case(lib)

    (creator,) = verify.verify([db], untracked=True)["creators"]

    assert creator["ok"] == (3 if case_found else 2)
    assert creator["missing"] == (0 if case_found else 1) and creator["empty"] == 1
    assert creator["untracked_files"] == ([] if case_found else [str(lib / lower_nfd)])
    # the empty file is moved aside under the name it has on disk
    verify.verify([db], apply=True)
    assert (lib / f"{empty_nfd}.bad").exists() and not (lib / empty_nfd).exists()


def test_expired_stories_do_not_count_toward_the_guard(tmp_path):
    rows = [(i, 100 + i, f"s{i}.jpg", 3, None, "Stories", {}) for i in range(1, 7)]
    rows += [(i, 100 + i, f"{i}.jpg", 3, b"abc", "Timeline", {}) for i in range(7, 11)]
    rows += [(11, 111, "gone.jpg", 3, None, "Timeline", {})]
    db, _ = make_library(tmp_path, rows)
    (creator,) = verify.verify([db], apply=True)["creators"]
    assert "left_alone" not in creator and creator["media_reset"] == 1
