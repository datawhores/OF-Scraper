"""recover_collisions working on a real PostgreSQL server (#631).

Skipped unless OFSC_TEST_POSTGRES_URL names a server the tests may use (see
test_db_postgres_live.py). Each test gives the sites schemas of its own and
drops them. The `check_...` functions are the ones
test_collision_recovery_postgres.py runs against its stand-in; here the rows
are in a server, brought in by the real import. The other tests are what only
a server can answer: what its transaction does when another program changes
a row meanwhile, and what its column types take.
"""

import json
import os
import urllib.parse
import uuid

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.db.creator_rows as creator_rows
import ofscraper.db.postgres as postgres
from ofscraper.commands import recover_collisions
from ofscraper.commands.recover_collisions import on_postgres, recover
from ofscraper.db.difference import ALL_FLAGS

URL = os.environ.get("OFSC_TEST_POSTGRES_URL", "")
if not URL:
    pytest.skip(
        "needs a PostgreSQL server: set OFSC_TEST_POSTGRES_URL", allow_module_level=True
    )

# with a server named, a missing driver is a failure, not a skip
import psycopg  # noqa: E402

from test.test_collision_recovery_postgres import (  # noqa: E402,F401  (the fixtures)
    CREATOR,
    MARKED,
    NAME,
    NAMESAKE,
    OTHER,
    OTHER_NAME,
    TO_MARK,
    WHO,
    check_one_creator_or_none,
    check_only_that_creator,
    check_same_recovery,
    one_creator,
    postgres_rows,
    three_creators,
    undo_files,
)
from test.test_db_postgres_live import changed_url  # noqa: E402
from test.test_stash_sync_postgres_live import (  # noqa: E402,F401  (the fixtures)
    bring_in,
    everything_held,
    no_url,
    pg,
    server,
)


def command(capsys, *args):
    """The command, as it is run: (exit code, stdout, stderr)."""
    capsys.readouterr()
    try:
        code = recover_collisions.main([str(arg) for arg in args]) or 0
    except SystemExit as stopped:
        code = stopped.code
    said = capsys.readouterr()
    return code, said.out, said.err


def meanwhile(monkeypatch, statement):
    """Another program changes a row and keeps the change after the command
    has read the rows, before its first change."""
    real = creator_rows.PostgresRows.change
    done = []

    def change(self, *args):
        if not done:
            done.append(server(statement))
        return real(self, *args)

    monkeypatch.setattr(creator_rows.PostgresRows, "change", change)
    return done


# --- the same rows, the same recovery ---


def test_the_same_rows_give_the_same_recovery_from_either(one_creator, pg, tmp_path):
    bring_in(tmp_path / ".data")

    check_same_recovery(URL, one_creator, tmp_path / "undo")


def test_only_that_creators_rows_of_that_site_are_touched(three_creators, pg, tmp_path):
    bring_in(tmp_path / ".data")

    check_only_that_creator(URL, lambda: everything_held(pg), pg["onlyfans"], tmp_path / "undo")


# --- the command ---


def test_cli_works_on_the_database_its_environment_names(one_creator, pg, tmp_path, monkeypatch, capsys):
    bring_in(tmp_path / ".data")
    monkeypatch.chdir(tmp_path)
    before = everything_held(pg)
    from_file = recover(one_creator)

    code, out, err = command(capsys, "--postgres", "--creator", NAME, "--undo-dir", "undo")

    assert (code, err) == (0, "")
    # what the file gives, and who the name turned out to be
    assert json.loads(out) == {**from_file, "creator": WHO}
    assert from_file["media_to_mark"] == TO_MARK
    # a preview changes nothing, and leaves nothing in the undo folder
    assert everything_held(pg) == before
    assert list((tmp_path / "undo").iterdir()) == []

    # without a folder for the undo file nothing is applied
    code, out, err = command(capsys, "--postgres", "--creator", CREATOR, "--site", "onlyfans", "--apply")

    assert (code, out) == (2, "")
    assert "--postgres --apply needs --undo-dir" in err
    assert everything_held(pg) == before

    code, out, err = command(
        capsys, "--postgres", "--creator", CREATOR, "--site", "onlyfans", "--apply", "--undo-dir", "undo"
    )

    assert (code, err) == (0, "")
    applied = json.loads(out)
    assert (applied["applied"], applied["rows_marked"], applied["creator"]) == (True, MARKED, WHO)
    (saved,) = undo_files(tmp_path / "undo")
    assert applied["undo_file"] == str(saved) and saved.is_absolute()
    # the undo file says where it was made, without the login
    record = json.loads(saved.read_text(encoding="utf-8"))
    assert record["database"] == postgres.describe(URL)
    assert list(record) == ["version", "source", "site", "model_id", "database", "rows"]
    marked = everything_held(pg)
    assert marked != before

    code, out, err = command(capsys, "--postgres", "--creator", NAME, "--undo", saved)

    assert (code, err) == (0, "")
    assert json.loads(out) == {"applied": False, "rows_to_restore": MARKED, "creator": WHO}
    assert everything_held(pg) == marked

    code, out, err = command(capsys, "--postgres", "--creator", NAME, "--undo", saved, "--apply")

    assert (code, err) == (0, "")
    assert json.loads(out) == {"applied": True, "rows_to_restore": MARKED, "creator": WHO}
    assert everything_held(pg) == before


def test_stopped_while_the_changes_are_saved_the_undo_file_is_the_way_back(
    one_creator, pg, tmp_path, monkeypatch, capsys
):
    """Ctrl-C lands after the server kept the changes and before the command
    knows it."""
    bring_in(tmp_path / ".data")
    before = everything_held(pg)
    real = psycopg.Connection.commit
    changing = []

    def change(self, *args, was=creator_rows.PostgresRows.change):
        changing.append(args)
        return was(self, *args)

    def commit(self):
        real(self)
        # not the commit that sets the connection up
        if changing:
            raise KeyboardInterrupt

    monkeypatch.setattr(creator_rows.PostgresRows, "change", change)
    monkeypatch.setattr(psycopg.Connection, "commit", commit)

    code, out, err = command(capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo")

    monkeypatch.setattr(psycopg.Connection, "commit", real)
    (saved,) = undo_files(tmp_path / "undo")
    assert (code, out) == (130, "")
    assert err.startswith("Recovery failed: This was stopped while the changes were being saved to the PostgreSQL")
    assert f"The undo file is kept: {saved}." in err and err.count("\n") == 1
    assert len(changing) == MARKED
    assert everything_held(pg) != before

    code, out, err = command(capsys, "--postgres", "--creator", NAME, "--undo", saved)
    assert (code, err) == (0, "")
    assert json.loads(out)["rows_to_restore"] == MARKED
    code, out, err = command(capsys, "--postgres", "--creator", NAME, "--undo", saved, "--apply")
    assert (code, err) == (0, "")
    assert everything_held(pg) == before


def test_a_database_without_the_scrapers_tables_has_no_creator(pg, tmp_path, capsys):
    code, out, err = command(capsys, "--postgres", "--creator", "Nobody", "--apply", "--undo-dir", tmp_path)

    assert (code, out) == (1, "")
    assert err == "Recovery failed: PostgreSQL has no creator named Nobody (looked in: onlyfans, fansly)\n"


def test_a_refused_login_is_one_sentence_without_the_password(pg, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(postgres.URL_KEY, changed_url(password="not-the-password"))

    code, out, err = command(capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path)

    assert (code, out) == (1, "")
    assert err.startswith("Recovery failed: Can't use the PostgreSQL database at ")
    assert "the user name or password was refused" in err
    assert "not-the-password" not in err and err.count("\n") == 1


def test_a_login_that_may_only_read_previews_and_changes_nothing(one_creator, pg, tmp_path, monkeypatch, capsys):
    bring_in(tmp_path / ".data")
    login = f"t_{uuid.uuid4().hex[:12]}_reads"
    try:
        server(f"CREATE ROLE {login} LOGIN PASSWORD 'only-reads'")
    except psycopg.errors.InsufficientPrivilege:
        pytest.skip("the tests' login may not make another login")
    try:
        for (schema,) in server("SELECT nspname FROM pg_namespace WHERE nspname = ANY(%s)", [list(pg.values())]):
            server(f"GRANT USAGE ON SCHEMA {schema} TO {login}")
            server(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {login}")
        url = urllib.parse.urlsplit(URL)
        monkeypatch.setenv(
            postgres.URL_KEY,
            url._replace(netloc=f"{login}:only-reads@{url.hostname}:{url.port or 5432}").geturl(),
        )
        before = everything_held(pg)

        code, out, err = command(capsys, "--postgres", "--creator", NAME, "--undo-dir", tmp_path / "undo")

        assert (code, err) == (0, "")
        assert json.loads(out)["media_to_mark"] == TO_MARK

        code, out, err = command(capsys, "--postgres", "--creator", NAME, "--undo-dir", tmp_path / "undo", "--apply")

        assert (code, out) == (1, "")
        assert err.startswith("Recovery failed: Can't change the PostgreSQL database at ")
        assert "Nothing was changed. (" in err and "permission denied" in err
        assert "only-reads" not in err and err.count("\n") == 1
        assert everything_held(pg) == before
        assert not undo_files(tmp_path / "undo")
    finally:
        server(f"DROP OWNED BY {login}")
        server(f"DROP ROLE {login}")


def test_a_name_more_than_one_creator_goes_by_is_refused_and_each_can_still_be_named(three_creators, pg, tmp_path):
    bring_in(tmp_path / ".data")

    def add(table, columns, rows):
        for row in rows:
            server(
                f"INSERT INTO {pg['onlyfans']}.{table} ({', '.join(columns)})"
                f" VALUES ({', '.join(['%s'] * len(columns))})",
                row,
            )

    check_one_creator_or_none(URL, add, tmp_path / "undo")


# --- the scraper, still running ---


def test_a_row_the_scraper_changed_meanwhile_stops_the_run_with_nothing_changed(
    one_creator, pg, tmp_path, monkeypatch, capsys
):
    bring_in(tmp_path / ".data")
    before = postgres_rows(URL)
    # a download is saved: one of the rows the command is about to mark
    done = meanwhile(
        monkeypatch,
        f"UPDATE {pg['onlyfans']}.medias SET filename = 'missing_5.jpg', size = 501 WHERE post_id = '106'",
    )

    code, out, err = command(
        capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert done
    assert (code, out) == (1, "")
    # the server refuses the change: the row isn't the one that was read
    assert err.startswith(
        "Recovery failed: Another program changed or is using the same rows of the PostgreSQL database at "
    )
    assert "(is the scraper running?). Nothing was changed. (" in err
    assert "could not serialize access due to concurrent update" in err
    assert err.count("\n") == 1
    after = postgres_rows(URL)
    # the scraper's row is as the scraper left it; the rows changed before it are back
    assert after[5] == (5, 106, str(tmp_path / "media"), "missing_5.jpg", 1, 501, "hash-5", CREATOR)
    assert after[:5] + after[6:] == before[:5] + before[6:]
    assert not undo_files(tmp_path / "undo")


def test_a_row_the_scraper_holds_stops_the_run_with_nothing_changed(one_creator, pg, tmp_path, monkeypatch, capsys):
    bring_in(tmp_path / ".data")
    before = everything_held(pg)
    # how long a connection of the command's waits for a held row, in seconds
    monkeypatch.setattr(postgres, "CHECKOUT_TIMEOUT", 1)
    # a write of the scraper's that isn't finished
    scraper = psycopg.connect(URL)
    try:
        scraper.execute(f"UPDATE {pg['onlyfans']}.medias SET size = 501 WHERE post_id = '106'")

        code, out, err = command(
            capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
        )
    finally:
        scraper.rollback()
        scraper.close()

    assert (code, out) == (1, "")
    assert err.startswith(
        "Recovery failed: Another program changed or is using the same rows of the PostgreSQL database at "
    )
    assert "lock timeout" in err and err.count("\n") == 1
    assert everything_held(pg) == before
    assert not undo_files(tmp_path / "undo")


def test_what_the_scraper_changes_in_other_rows_doesnt_stop_the_run(three_creators, pg, tmp_path, monkeypatch, capsys):
    bring_in(tmp_path / ".data")
    before = postgres_rows(URL)
    # rows the command doesn't mark: this creator's unshared file, and
    # everything of the other creator's
    done = meanwhile(
        monkeypatch,
        f"UPDATE {pg['onlyfans']}.medias SET size = 9 WHERE post_id = '104' OR model_id = {OTHER}",
    )

    code, out, err = command(
        capsys, "--postgres", "--creator", NAME, "--apply", "--undo-dir", tmp_path / "undo"
    )

    assert done
    assert (code, err) == (0, "")
    assert json.loads(out)["rows_marked"] == MARKED
    after = postgres_rows(URL)
    assert [row[4] for row in after] == [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0, None]
    # the scraper's change is kept beside the command's
    assert after[3] == before[3][:5] + (9,) + before[3][6:]
    assert {row[5] for row in postgres_rows(URL, OTHER)} == {9}


def test_undo_restores_nothing_if_the_scraper_changes_a_row_while_it_runs(
    one_creator, pg, tmp_path, monkeypatch, capsys
):
    bring_in(tmp_path / ".data")
    saved = on_postgres(URL, NAME, apply=True, undo_dir=tmp_path / "undo")["undo_file"]
    marked = postgres_rows(URL)
    done = meanwhile(
        monkeypatch,
        f"UPDATE {pg['onlyfans']}.medias SET downloaded = TRUE, filename = 'avatar_2.jpg' WHERE post_id = '109'",
    )

    code, out, err = command(capsys, "--postgres", "--creator", NAME, "--undo", saved, "--apply")

    assert done
    assert (code, out) == (1, "")
    assert "could not serialize access due to concurrent update" in err
    after = postgres_rows(URL)
    assert after[9][3:5] == ("avatar_2.jpg", 1)
    assert after[:9] + after[10:] == marked[:9] + marked[10:]


# --- undo ---


def test_undo_is_refused_for_what_it_doesnt_fit(three_creators, pg, tmp_path):
    bring_in(tmp_path / ".data")
    saved = on_postgres(URL, NAME, apply=True, undo_dir=tmp_path / "undo")["undo_file"]
    file_undo = recover(three_creators, apply=True)["undo_file"]
    marked = everything_held(pg)
    medias = f"{pg['onlyfans']}.medias"

    for apply in (False, True):
        # the other creator and the other site hold rows it would fit
        with pytest.raises(ValueError, match="Undo file is for onlyfans creator 10, not onlyfans creator 20"):
            on_postgres(URL, OTHER_NAME, undo_file=saved, apply=apply)
        with pytest.raises(ValueError, match="Undo file is for onlyfans creator 10, not fansly creator 10"):
            on_postgres(URL, NAMESAKE, undo_file=saved, apply=apply)
        with pytest.raises(ValueError, match="Undo file was written for a user_data.db, not PostgreSQL"):
            on_postgres(URL, NAME, undo_file=file_undo, apply=apply)
        assert everything_held(pg) == marked

    # downloaded again since, under a name of its own
    server(f"UPDATE {medias} SET downloaded = TRUE, filename = 'missing_5.jpg' WHERE model_id = {CREATOR} AND post_id = '106'")
    changed = everything_held(pg)
    for apply in (False, True):
        with pytest.raises(ValueError, match="1 of the undo file's 7 rows are no longer as the recovery left them"):
            on_postgres(URL, NAME, undo_file=saved, apply=apply)
        assert everything_held(pg) == changed

    # downloaded again with the file it had: nothing to restore in that row
    server(f"UPDATE {medias} SET filename = 'missing.jpg' WHERE model_id = {CREATOR} AND post_id = '106'")
    assert on_postgres(URL, NAME, undo_file=saved, apply=True) == {
        "applied": True, "rows_to_restore": MARKED - 1, "creator": WHO,
    }
    assert on_postgres(URL, NAME, undo_file=saved, apply=True) == {
        "applied": True, "rows_to_restore": 0, "creator": WHO,
    }


# --- one creator's rows, changed (creator_rows) ---


def test_a_row_is_changed_only_while_it_holds_what_was_read(three_creators, pg, tmp_path):
    bring_in(tmp_path / ".data")
    before = everything_held(pg)
    medias = f"{pg['onlyfans']}.medias"
    ((others_row,),) = server(f"SELECT id FROM {medias} WHERE model_id = {OTHER} AND post_id = '101'")
    was = {
        "downloaded": 1, "directory": str(tmp_path / "media"), "filename": "shared.jpg", "size": 100,
        "hash": "hash-1",
    }

    with creator_rows.in_postgres(URL, ["onlyfans"], [NAME], write=True) as (rows,):
        ids = {post_id: row_id for row_id, post_id in rows.select("medias", ["id", "post_id"])}
        assert rows.change("medias", ids[101], {**was, "size": 101}, {"downloaded": 0}) is False
        assert rows.change("medias", ids[101], {**was, "hash": None}, {"downloaded": 0}) is False
        assert rows.change("medias", ids[101], {**was, "directory": None}, {"downloaded": 0}) is False
        assert rows.change("medias", ids[101], {**was, "downloaded": 0}, {"downloaded": 0}) is False
        # another creator's row, which holds the same
        assert rows.change("medias", others_row, was, {"downloaded": 0}) is False
        assert rows.change("medias", 0, was, {"downloaded": 0}) is False
        # every type the command compares and sets: yes/no, text, number, empty
        assert rows.change("medias", ids[101], was, {"downloaded": 0, "size": 5}) is True
        nothing = {"directory": None, "filename": None, "size": None, "hash": None}
        assert rows.change("medias", ids[111], {"downloaded": 1, **nothing}, {"filename": "found.jpg"}) is True
        # an empty text is not an empty value
        assert rows.change("medias", ids[109], {"hash": None}, {"hash": "x"}) is False
        assert rows.change("medias", ids[109], {"hash": ""}, {"hash": None}) is True
        assert rows.change("medias", ids[112], {"downloaded": None}, {"downloaded": 1}) is True
        # not kept yet: another connection sees none of it
        assert everything_held(pg) == before
        rows.commit()

    after = everything_held(pg)
    changed = {
        key: [(was, now) for was, now in zip(rows, after[key]) if was != now]
        for key, rows in before.items()
        if rows != after[key]
    }
    assert list(changed) == [(pg["onlyfans"], "medias")]
    columns = postgres.TABLE_COLUMNS["medias"]
    differences = [
        {column: (old, new) for column, old, new in zip(columns, was, now) if old != new}
        for was, now in changed[pg["onlyfans"], "medias"]
    ]
    assert differences == [
        {"downloaded": (True, False), "size": (100, 5)},
        {"hash": ("", None)},
        {"filename": (None, "found.jpg")},
        {"downloaded": (None, True)},
    ]


def test_changes_are_gone_without_a_commit(one_creator, pg, tmp_path):
    bring_in(tmp_path / ".data")
    before = everything_held(pg)

    with creator_rows.in_postgres(URL, ["onlyfans"], [NAME], write=True) as (rows,):
        ids = {post_id: row_id for row_id, post_id in rows.select("medias", ["id", "post_id"])}
        assert rows.change("medias", ids[104], {"downloaded": 1}, {"downloaded": 0}) is True
        # the command's own reads see its change
        assert [tuple(row) for row in rows.select("medias", ["downloaded"], "post_id = '104'")] == [(0,)]

    assert everything_held(pg) == before


# --- the connection ---


def test_the_connection_changes_rows_in_one_transaction_that_sees_one_moment(pg):
    postgres.POSTGRES.create_tables(ALL_FLAGS, schema=pg["onlyfans"])
    models = f"{pg['onlyfans']}.models"
    server(f"INSERT INTO {models} (model_id) VALUES (1)")
    writer = postgres.Writer(URL)
    try:
        assert tuple(writer.rows("SHOW transaction_read_only")[0]) == ("off",)
        assert tuple(writer.rows("SHOW transaction_isolation")[0]) == ("repeatable read",)
        # the Reader's timeouts, which it is opened with
        assert tuple(writer.rows("SHOW lock_timeout")[0]) == ("30s",)
        assert tuple(writer.rows("SHOW statement_timeout")[0]) == ("5min",)
        assert tuple(writer.rows("SHOW TimeZone")[0]) == ("UTC",)
        # the first read of a table is the moment every later one sees
        assert [tuple(row) for row in writer.rows(f"SELECT model_id FROM {models}")] == [(1,)]
        # the scraper saves more while the tool works: not seen
        server(f"INSERT INTO {models} (model_id) VALUES (2)")
        assert [tuple(row) for row in writer.rows(f"SELECT model_id FROM {models}")] == [(1,)]
        assert writer.change(f"UPDATE {models} SET model_id = ? WHERE model_id = ?", [3, 1]) == 1
        assert writer.change(f"UPDATE {models} SET model_id = ? WHERE model_id = ?", [4, 99]) == 0
        # nothing is kept until it is told to
        assert server(f"SELECT model_id FROM {models} ORDER BY 1") == [(1,), (2,)]
    finally:
        writer.close()
    assert server(f"SELECT model_id FROM {models} ORDER BY 1") == [(1,), (2,)]

    writer = postgres.Writer(URL)
    try:
        assert writer.change(f"UPDATE {models} SET model_id = ? WHERE model_id = ?", [3, 1]) == 1
        writer.commit()
    finally:
        writer.close()
    assert server(f"SELECT model_id FROM {models} ORDER BY 1") == [(2,), (3,)]


def test_a_change_the_server_refuses_is_one_sentence_and_nothing_is_kept(pg):
    postgres.POSTGRES.create_tables(ALL_FLAGS, schema=pg["onlyfans"])
    models = f"{pg['onlyfans']}.models"
    server(f"INSERT INTO {models} (model_id) VALUES (1), (2)")
    writer = postgres.Writer(URL)
    try:
        assert writer.change(f"UPDATE {models} SET model_id = ? WHERE model_id = ?", [5, 1]) == 1
        # two creators can't have one id
        with pytest.raises(postgres.PostgresUnavailable) as raised:
            writer.change(f"UPDATE {models} SET model_id = ? WHERE model_id = ?", [2, 5])
    finally:
        writer.close()

    said = str(raised.value)
    assert said.startswith("Can't change the PostgreSQL database at ")
    assert "Nothing was changed. (" in said and "\n" not in said
    assert not isinstance(raised.value, postgres.ChangedMeanwhile)
    assert server(f"SELECT model_id FROM {models} ORDER BY 1") == [(1,), (2,)]
