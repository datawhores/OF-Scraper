"""ofscraper verify on PostgreSQL: the same findings as from the file.

The server is a stand-in (postgres_stand_in.py); test_verify_postgres_live.py
runs check_same_findings against a real server in CI. The files are real
ones, under pytest's tmp_path.
"""

from pathlib import Path

import pytest

import ofscraper.commands.verify as verify
import ofscraper.db.postgres as postgres
from test.test_verify import library  # noqa: F401  (the fixture)

URL = "postgresql://scraper:s3cret-word@db.example:5433/library"


@pytest.fixture(autouse=True)
def no_url(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)


@pytest.fixture
def server(monkeypatch):
    pytest.importorskip("psycopg")
    from test.postgres_stand_in import Server

    server = Server()
    monkeypatch.setattr(postgres, "Reader", server.reader)
    monkeypatch.setattr(postgres, "Writer", server.writer)
    yield server
    server.close()


def without_names(report):
    for creator in report["creators"]:
        creator.pop("database")
        creator.pop("creator", None)
    return report


def check_same_findings(database_url, db):
    from_file = without_names(verify.verify([db]))
    from_postgres = without_names(verify.verify_postgres(database_url, "5", site="onlyfans"))
    assert from_postgres == from_file
    assert from_file["totals"]["missing"] == 3


def test_the_same_rows_give_the_same_findings_from_either(library, server, tmp_path):  # noqa: F811
    db, _ = library
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    check_same_findings(URL, db)


def test_unknown_creator(library, server, tmp_path):  # noqa: F811
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    with pytest.raises(Exception, match="no creator named nobody"):
        verify.verify_postgres(URL, "nobody")


def medias(database_url):
    import ofscraper.db.creator_rows as creator_rows

    with creator_rows.in_postgres(database_url, ["onlyfans"], ["5"]) as (rows,):
        return sorted(tuple(r) for r in rows.select("medias", ["media_id", "post_id", "downloaded"]))


def check_apply_and_undo(database_url, library, tmp_path):
    db, lib = library
    before = medias(database_url)
    with pytest.raises(ValueError, match="undo file"):
        verify.verify_postgres(database_url, "5", apply=True)
    undo_dir = tmp_path / "undo"
    undo_dir.mkdir()
    report = verify.verify_postgres(database_url, "5", apply=True, undo_dir=undo_dir)
    (creator,) = report["creators"]
    assert creator["media_reset"] == 2 and creator["files_moved_aside"] == 1
    reset = {m for m, _, d in medias(database_url) if d == 0} - {m for m, _, d in before if d == 0}
    assert reset == {2, 3}
    assert (lib / "empty.jpg.bad").exists()
    undo_file = creator["undo_file"]
    assert verify.undo_postgres(database_url, "5", undo_file)["rows_to_restore"] == 2
    assert verify.undo_postgres(database_url, "5", undo_file, apply=True)["files_to_rename_back"] == 1
    assert medias(database_url) == before
    assert (lib / "empty.jpg").exists() and not (lib / "empty.jpg.bad").exists()


def test_apply_and_undo(library, server, tmp_path):  # noqa: F811
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    check_apply_and_undo(URL, library, tmp_path)


def test_a_row_changed_meanwhile_changes_nothing(library, server, tmp_path, monkeypatch):  # noqa: F811
    import ofscraper.db.creator_rows as creator_rows

    db, lib = library
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    before = medias(URL)
    real = creator_rows.PostgresRows.change
    monkeypatch.setattr(creator_rows.PostgresRows, "change", lambda *a: False)
    with pytest.raises(postgres.ChangedMeanwhile):
        verify.verify_postgres(URL, "5", apply=True, undo_dir=tmp_path)
    monkeypatch.setattr(creator_rows.PostgresRows, "change", real)
    assert medias(URL) == before
    assert (lib / "empty.jpg").exists() and not list(tmp_path.glob("*.verify-undo-*"))


def apply_for_undo(tmp_path, **choices):
    undo_dir = tmp_path / "undo"
    undo_dir.mkdir()
    report = verify.verify_postgres(URL, "5", apply=True, undo_dir=undo_dir, **choices)
    return report["creators"][0]["undo_file"]


def test_an_undo_file_from_another_database_restores_nothing(library, server, tmp_path):  # noqa: F811
    import json

    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    _, lib = library
    undo_file = apply_for_undo(tmp_path)
    after_apply = medias(URL)
    record = json.loads(Path(undo_file).read_text(encoding="utf-8"))
    assert record["database"] == "db.example:5433/library"
    # as an undo file made on another database would be: its rows aren't these
    record["database"] = "other.example:5432/library"
    record["rows"][0]["filename"] = "another.jpg"
    with open(undo_file, "w", encoding="utf-8") as output:
        json.dump(record, output)
    with pytest.raises(ValueError, match="made on other.example:5432/library") as error:
        verify.undo_postgres(URL, "5", undo_file, apply=True)
    assert "Nothing was restored" in str(error.value)
    assert medias(URL) == after_apply
    assert (lib / "empty.jpg.bad").exists() and not (lib / "empty.jpg").exists()


def test_an_undo_that_fails_partway_puts_the_renames_back(library, server, tmp_path, monkeypatch):  # noqa: F811
    import os

    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    _, lib = library
    undo_file = apply_for_undo(tmp_path, reset_size_differs=True)
    after_apply = medias(URL)
    real = os.rename
    calls = []

    def second_fails(src, dst):
        calls.append(src)
        if len(calls) == 2:
            raise OSError("in use")
        return real(src, dst)

    # a context of its own, so that leaving it doesn't also undo the server
    # fixture's stand-ins for postgres.Reader and Writer
    with monkeypatch.context() as patch:
        patch.setattr(verify.os, "rename", second_fails)
        with pytest.raises(OSError, match="in use"):
            verify.undo_postgres(URL, "5", undo_file, apply=True)
    assert medias(URL) == after_apply
    assert sorted(p.name for p in lib.glob("*.bad")) == ["edited.jpg.bad", "empty.jpg.bad"]
    assert verify.undo_postgres(URL, "5", undo_file, apply=True)["files_to_rename_back"] == 2


def test_two_media_with_one_empty_file_move_it_aside_once(server, tmp_path):
    from test.test_verify import one_empty_file_for_two_media

    _, lib = one_empty_file_for_two_media(tmp_path)
    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    before = medias(URL)
    undo_dir = tmp_path / "undo"
    undo_dir.mkdir()
    (creator,) = verify.verify_postgres(URL, "5", apply=True, undo_dir=undo_dir)["creators"]
    assert creator["media_reset"] == 2 and creator["files_moved_aside"] == 1
    assert sorted(p.name for p in lib.iterdir()) == ["ok.jpg", "shared.jpg.bad"]
    done = verify.undo_postgres(URL, "5", creator["undo_file"], apply=True)
    assert (done["rows_to_restore"], done["files_to_rename_back"]) == (2, 1)
    assert medias(URL) == before
    assert sorted(p.name for p in lib.iterdir()) == ["ok.jpg", "shared.jpg"]


def test_apply_skips_a_creator_without_a_medias_table(library, server, tmp_path, monkeypatch):  # noqa: F811
    import ofscraper.db.creator_rows as creator_rows

    server.bring_in(tmp_path / ".data", tmp_path / "staging")
    monkeypatch.setattr(creator_rows.PostgresRows, "tables", lambda self: {"posts"})
    report = verify.verify_postgres(URL, "5", apply=True, undo_dir=tmp_path)
    assert report["creators"][0]["skipped"] == "no medias table"
    assert not list(tmp_path.glob("*.verify-undo-*"))
