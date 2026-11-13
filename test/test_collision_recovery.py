import json
import sqlite3
from contextlib import closing
import subprocess
import sys
from pathlib import Path

import pytest

from ofscraper.commands.recover_collisions import recover, undo
from ofscraper.db.operations_.media import mediaCreate


@pytest.fixture(params=["DELETE", "WAL"])
def database(tmp_path, request):
    db = tmp_path / "user_data.db"
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute(f"PRAGMA journal_mode={request.param}")
        conn.execute(mediaCreate)
    return db


def add(db, media, path, post=None, downloaded=1):
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute(
            "INSERT INTO medias (media_id,model_id,post_id,directory,filename,downloaded,size,hash) "
            "VALUES (?,10,?,?,?,?,100,'old-hash')",
            (media, post or media, str(path.parent), path.name, downloaded),
        )


def rows(db):
    with closing(sqlite3.connect(db)) as conn, conn:
        return conn.execute("SELECT * FROM medias ORDER BY id").fetchall()


def flags(db):
    with closing(sqlite3.connect(db)) as conn, conn:
        return conn.execute("SELECT media_id,downloaded FROM medias ORDER BY id").fetchall()


def test_preview_and_apply_only_reset_ambiguous_media(database, tmp_path):
    shared = tmp_path / "shared.jpg"
    shared.write_bytes(b"surviving content")
    add(database, 1, shared)
    add(database, 2, shared)
    add(database, 2, tmp_path / "other-post.jpg", post=20)
    add(database, 3, tmp_path / "unshared-missing.jpg")
    original = rows(database)
    assert recover(database)["media_to_mark"] == 2
    assert rows(database) == original
    assert not list(tmp_path.glob("*.collision-undo-*"))
    result = recover(database, apply=True)
    assert result["rows_marked"] == 3
    record = json.loads(Path(result["undo_file"]).read_text())
    assert len(record["rows"]) == 3
    assert all(len(row) == 5 and row[-1] == 1 for row in record["rows"])
    assert not list(tmp_path.glob("*.sqlite"))
    assert flags(database) == [(1, 0), (2, 0), (2, 0), (3, 1)]
    with closing(sqlite3.connect(database)) as conn, conn:
        columns = [r[1] for r in conn.execute("PRAGMA table_info(medias)")]
    index = columns.index("downloaded")
    for old, new in zip(original, rows(database)):
        assert old[:index] + old[index + 1:] == new[:index] + new[index + 1:]
    assert shared.read_bytes() == b"surviving content"
    again = recover(database, apply=True)
    assert again["rows_marked"] == 0 and again["undo_file"] is None


def test_same_media_in_two_posts_is_not_a_collision(database, tmp_path):
    add(database, 1, tmp_path / "same.jpg", post=1)
    add(database, 1, tmp_path / "same.jpg", post=2)
    assert recover(database, apply=True)["groups"] == []
    assert flags(database) == [(1, 1), (1, 1)]


def test_missing_shared_path_and_pending_owner(database, tmp_path):
    add(database, 1, tmp_path / "missing.jpg", downloaded=0)
    add(database, 2, tmp_path / "missing.jpg")
    assert recover(database, apply=True)["media_to_mark"] == 1
    assert flags(database) == [(1, 0), (2, 0)]


def test_case_aliases_follow_real_filesystem(database, tmp_path):
    upper, lower = tmp_path / "File.JPG", tmp_path / "file.jpg"
    upper.write_bytes(b"one")
    aliases = lower.exists()
    if not aliases:
        lower.write_bytes(b"two")
    add(database, 1, upper)
    add(database, 2, lower)
    assert recover(database)["media_to_mark"] == (2 if aliases else 0)


def test_windows_sensitive_directory_keeps_distinct_files(database, tmp_path):
    if sys.platform != "win32":
        pytest.skip("Windows per-directory case sensitivity")
    folder = tmp_path / "cs"
    folder.mkdir()
    command = subprocess.run(
        ["fsutil", "file", "setCaseSensitiveInfo", str(folder), "enable"],
        capture_output=True,
    )
    if command.returncode:
        pytest.skip("Case-sensitive directories unavailable")
    for media, name in [(1, "A.jpg"), (2, "a.jpg")]:
        path = folder / name
        path.write_bytes(str(media).encode())
        add(database, media, path)
    assert recover(database)["groups"] == []


def test_relative_paths_require_explicit_root(database, tmp_path):
    add(database, 1, Path("relative.jpg"))
    add(database, 2, Path("relative.jpg"))
    with pytest.raises(ValueError, match="path-root"):
        recover(database, apply=True)
    assert flags(database) == [(1, 1), (2, 1)]
    assert recover(database, path_root=tmp_path)["media_to_mark"] == 2


def test_apply_rolls_back_all_flags_when_update_fails(database, tmp_path):
    add(database, 1, tmp_path / "same.jpg")
    add(database, 2, tmp_path / "same.jpg")
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.execute("CREATE TRIGGER fail_update BEFORE UPDATE ON medias "
                     "WHEN NEW.media_id=2 BEGIN SELECT RAISE(ABORT,'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        recover(database, apply=True)
    assert flags(database) == [(1, 1), (2, 1)]
    assert not list(tmp_path.glob("*.collision-undo-*"))


def test_cli_defaults_to_preview_and_never_creates_missing_db(database, tmp_path):
    add(database, 1, tmp_path / "same.jpg")
    add(database, 2, tmp_path / "same.jpg")
    command = [sys.executable, "-m", "ofscraper.commands.recover_collisions"]
    result = subprocess.run(command + [str(database)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["applied"] is False
    assert flags(database) == [(1, 1), (2, 1)]
    applied = subprocess.run(command + [str(database), "--apply"], capture_output=True, text=True)
    assert applied.returncode == 0, applied.stderr
    undo_path = json.loads(applied.stdout)["undo_file"]
    restored = subprocess.run(
        command + [str(database), "--undo", undo_path, "--apply"],
        capture_output=True, text=True,
    )
    assert restored.returncode == 0, restored.stderr
    assert flags(database) == [(1, 1), (2, 1)]
    missing = tmp_path / "absent.db"
    result = subprocess.run(command + [str(missing), "--apply"], capture_output=True)
    assert result.returncode != 0 and not missing.exists()


def test_undo_file_failure_does_not_change_flags(database, tmp_path, monkeypatch):
    add(database, 1, tmp_path / "same.jpg")
    add(database, 2, tmp_path / "same.jpg")
    original = Path.open

    def deny_undo(path, *args, **kwargs):
        if ".collision-undo-" in path.name:
            raise PermissionError("undo file denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_undo)
    with pytest.raises(PermissionError, match="undo file denied"):
        recover(database, apply=True)
    assert flags(database) == [(1, 1), (2, 1)]


def test_undo_restores_only_changed_rows_and_is_repeatable(database, tmp_path):
    add(database, 1, tmp_path / "same.jpg")
    add(database, 2, tmp_path / "same.jpg")
    add(database, 3, tmp_path / "other.jpg", downloaded=0)
    original = rows(database)
    result = recover(database, apply=True)
    assert undo(database, result["undo_file"])["rows_to_restore"] == 2
    assert flags(database) == [(1, 0), (2, 0), (3, 0)]
    assert undo(database, result["undo_file"], apply=True)["rows_to_restore"] == 2
    assert rows(database) == original
    assert undo(database, result["undo_file"], apply=True)["rows_to_restore"] == 0


def test_undo_checks_database_and_row_identity(database, tmp_path):
    add(database, 1, tmp_path / "same.jpg")
    add(database, 2, tmp_path / "same.jpg")
    result = recover(database, apply=True)
    other = tmp_path / "other.db"
    other.touch()
    with pytest.raises(ValueError, match="does not belong"):
        undo(other, result["undo_file"], apply=True)
    with closing(sqlite3.connect(database)) as conn, conn:
        conn.execute("UPDATE medias SET media_id=99 WHERE media_id=1")
    assert undo(database, result["undo_file"], apply=True)["rows_to_restore"] == 1
    assert flags(database) == [(99, 0), (2, 1)]
