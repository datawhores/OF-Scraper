"""stash_sync reading a real PostgreSQL server (#631).

Skipped unless OFSC_TEST_POSTGRES_URL names a server the tests may use (see
test_db_postgres_live.py). Each test gives the sites schemas of its own and
drops them. The checks are the ones test_stash_sync_postgres.py runs against
its stand-in; here the rows are in a server, brought in by the real import
or saved by the scraper.
"""

import json
import os
import threading
import time
import urllib.parse
import uuid

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.postgres_import as importer
import ofscraper.db.creator_rows as creator_rows
import ofscraper.db.postgres as postgres
import ofscraper.sites as sites
from ofscraper.commands import stash_sync
from ofscraper.commands.stash_sync import sync
from ofscraper.db.difference import ALL_FLAGS

URL = os.environ.get("OFSC_TEST_POSTGRES_URL", "")
if not URL:
    pytest.skip(
        "needs a PostgreSQL server: set OFSC_TEST_POSTGRES_URL", allow_module_level=True
    )

# with a server named, a missing driver is a failure, not a skip
import psycopg  # noqa: E402

from test.test_db_postgres_live import changed_url  # noqa: E402
from test.test_stash_sync_postgres import (  # noqa: E402,F401  (the fixtures)
    BOTH,
    DATES,
    OF_ID,
    OF_USER,
    PERFORMERS,
    SAME_ID_NAME,
    SECOND,
    SECOND_NAME,
    Recording,
    check_date,
    check_oldest_first,
    check_own_rows,
    check_same_sync,
    check_seven_creators,
    check_username,
    check_values,
    dated_file,
    everything,
    fansly,
    fansly_library,
    from_postgres,
    library,
    more_creators,
    renamed_file,
    save_onlyfans,
    seven_creators,
    stash_server,
    state,
    without_sources,
)


@pytest.fixture(autouse=True)
def no_url(monkeypatch):
    """The files are written first, with PostgreSQL off."""
    monkeypatch.delenv(postgres.URL_KEY, raising=False)


@pytest.fixture
def pg(monkeypatch):
    """PostgreSQL is on, and each site's schema is this test's own:
    {site: schema}. Ask for it after the fixtures that write files."""
    tag = uuid.uuid4().hex[:12]
    schemas = {site: f"t_{tag}_{site}" for site in sites.SITES}
    real = postgres.schema_name
    # the settings are read once, before the address is in the environment:
    # read then, they would keep it for every later test
    postgres.url()
    monkeypatch.setenv(postgres.URL_KEY, URL)
    monkeypatch.setattr(
        postgres, "schema_name", lambda site: schemas.get(site) or real(site)
    )
    yield schemas
    postgres.POSTGRES.shutdown()
    with psycopg.connect(URL, autocommit=True) as conn:
        for schema in schemas.values():
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


def bring_in(folder):
    """The real import of every user_data.db under `folder`."""
    lines = []
    code = importer.run(folder, apply=True, out=lines.append)
    assert code == 0, "\n".join(lines)


def server(statement, params=()):
    with psycopg.connect(URL, autocommit=True) as conn:
        cursor = conn.execute(statement, params)
        return cursor.fetchall() if cursor.description else None


def everything_held(schemas):
    """Every row of the tests' schemas, to see that nothing changed."""
    held = {}
    for schema in schemas.values():
        tables = server(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s"
            " ORDER BY table_name",
            [schema],
        )
        for (table,) in tables:
            held[schema, table] = server(f"SELECT * FROM {schema}.{table} ORDER BY 1")
    return held


# --- the same rows, the same sync ---


@pytest.mark.parametrize("apply", [False, True])
def test_the_same_rows_give_the_same_sync_from_either(everything, pg, apply):
    data, in_stash = everything
    bring_in(data)
    before = everything_held(pg)

    check_same_sync(URL, data, in_stash, apply)

    # the database was only read
    assert everything_held(pg) == before
    assert len(before[pg["onlyfans"], "medias"]) > 10


def test_each_creator_gets_only_their_own_rows(everything, pg):
    data, _ = everything
    bring_in(data)

    check_own_rows(URL, data)


def test_the_values_are_the_ones_a_file_gives(more_creators, pg, tmp_path):
    bring_in(tmp_path / ".data")

    check_values(URL, str(tmp_path / "second"))


def test_rows_come_oldest_first(more_creators, pg, tmp_path):
    bring_in(tmp_path / ".data")

    check_oldest_first(URL)


@pytest.mark.parametrize("posted, made, from_a_file, from_postgresql", DATES)
def test_the_two_dates_postgresql_gives_differently(tmp_path, pg, posted, made, from_a_file, from_postgresql):
    db = dated_file(tmp_path, posted, made)
    bring_in(tmp_path / ".data")

    check_date(URL, db, from_a_file, from_postgresql)


def test_the_username_saved_last_is_the_creators(tmp_path, pg):
    db = renamed_file(tmp_path)
    bring_in(tmp_path / ".data")

    check_username(URL, db)


def test_seven_creators_of_one_site_leave_no_statement_on_the_server(tmp_path, pg):
    """The driver keeps a statement on the server once it has run five
    times, unless told not to. A pooler that gives each transaction to
    another connection can't have that."""
    data, in_stash = seven_creators(tmp_path)
    bring_in(data)

    kept = check_seven_creators(
        URL, data, in_stash,
        lambda creators: creators[0]._reader.rows("SELECT name FROM pg_prepared_statements"),
    )

    assert kept == []


def test_rows_the_scraper_saved_in_postgresql_sync_as_the_ones_it_saved_in_a_file(tmp_path, pg, monkeypatch):
    media_dir = tmp_path / "of"
    data = tmp_path / ".data"
    with monkeypatch.context() as patch:
        patch.delenv(postgres.URL_KEY)
        in_stash = save_onlyfans(patch, media_dir, data / str(OF_ID) / "user_data.db")
    # the same, saved by the same code, with PostgreSQL on
    save_onlyfans(monkeypatch, media_dir)
    assert len(server(f"SELECT 1 FROM {pg['onlyfans']}.medias WHERE model_id = %s", [OF_ID])) == 3
    files, database = Recording(in_stash), Recording(in_stash)

    from_files = sync([data], files, apply=True)
    from_database = from_postgres(URL, database, apply=True)

    assert without_sources(from_database) == without_sources(from_files)
    assert from_files["totals"] == {"files": 3, "updated": 2, "not_in_stash": 1}
    assert [m["performer"] for m in from_database["models"]] == [OF_USER]
    assert database.calls == files.calls
    assert state(database) == state(files)


# --- the command ---


def test_cli_reads_the_database_its_environment_names(everything, pg, stash_server, capsys):
    data, in_stash = everything
    bring_in(data)
    stash, url = stash_server
    for kind, path in in_stash:
        stash.add(kind, path)
    assert stash_sync.main([str(data), "--url", url]) == 0
    from_files = capsys.readouterr()
    assert from_files.err.startswith("warning: PostgreSQL is on")
    before = everything_held(pg)

    def run(*args):
        code = stash_sync.main(["--postgres", "--url", url, *args])
        said = capsys.readouterr()
        assert (code, said.err) == (0, "")
        return json.loads(said.out)

    assert without_sources(run()) == without_sources(json.loads(from_files.out))
    assert [m["performer"] for m in run("--site", "fansly")["models"]] == ["samplecreator2", SAME_ID_NAME]
    assert [m["performer"] for m in run("--creator", "OFCREATOR", "--creator", str(SECOND))["models"]] == [
        OF_USER, SECOND_NAME,
    ]
    assert [m["performer"] for m in run("--site", "onlyfans", "--creator", "123")["models"]] == ["creator"]
    applied = run("--apply")
    assert applied["totals"]["updated"] >= 12
    assert [m["performer"] for m in applied["models"]] == PERFORMERS
    assert everything_held(pg) == before


def test_a_database_without_the_scrapers_tables_has_no_creators(pg, stash_server, capsys):
    _, url = stash_server

    assert stash_sync.main(["--postgres", "--url", url]) == 0

    said = capsys.readouterr()
    assert said.err == ""
    assert json.loads(said.out) == {"apply": False, "models": [], "totals": {}}


def test_a_creator_nobody_has_is_said(more_creators, pg, tmp_path, capsys):
    bring_in(tmp_path / ".data")

    assert stash_sync.main(["--postgres", "--creator", "nobody", "--url", "http://127.0.0.1:9/graphql"]) == 1

    said = capsys.readouterr()
    assert said.out == ""
    assert said.err == "error: PostgreSQL has no creator named nobody (looked in: onlyfans, fansly)\n"


# --- the connection ---


def test_nothing_can_be_written_through_the_connection(pg):
    postgres.POSTGRES.create_tables(ALL_FLAGS, schema=pg["onlyfans"])
    reader = postgres.Reader(URL)
    try:
        assert tuple(reader.rows("SHOW transaction_read_only")[0]) == ("on",)
        assert tuple(reader.rows("SHOW transaction_isolation")[0]) == ("repeatable read",)
        assert tuple(reader.rows("SHOW TimeZone")[0]) == ("UTC",)
        # in milliseconds: how long a read may wait for a lock, and take
        limits = reader.rows(
            "SELECT name, setting FROM pg_settings"
            " WHERE name IN ('lock_timeout', 'statement_timeout') ORDER BY name"
        )
        assert [tuple(row) for row in limits] == [
            ("lock_timeout", "30000"), ("statement_timeout", "300000"),
        ]
        with pytest.raises(postgres.PostgresUnavailable) as raised:
            reader.rows(f"INSERT INTO {pg['onlyfans']}.models (model_id) VALUES (?)", [1])
    finally:
        reader.close()

    assert "read-only transaction" in str(raised.value)
    assert server(f"SELECT COUNT(*) FROM {pg['onlyfans']}.models") == [(0,)]


def test_every_read_sees_the_database_as_it_was_at_the_first(pg):
    postgres.POSTGRES.create_tables(ALL_FLAGS, schema=pg["onlyfans"])
    models = f"{pg['onlyfans']}.models"
    medias = f"{pg['onlyfans']}.medias"
    server(f"INSERT INTO {models} (model_id) VALUES (1)")
    server(f"INSERT INTO {medias} (media_id, post_id, model_id) VALUES ('10', '20', 1)")

    with creator_rows.in_postgres(URL, BOTH) as creators:
        assert [rows.model_id for rows in creators] == [1]
        # the scraper saves more while the tool is still reading
        server(f"INSERT INTO {models} (model_id) VALUES (2)")
        server(f"INSERT INTO {medias} (media_id, post_id, model_id) VALUES ('11', '21', 1)")
        seen = creators[0].select("medias", ["media_id"])

    assert [tuple(row) for row in seen] == [(10,)]
    # the next run sees it
    with creator_rows.in_postgres(URL, BOTH) as creators:
        assert [rows.model_id for rows in creators] == [1, 2]
        assert [tuple(row) for row in creators[0].select("medias", ["media_id"])] == [(10,), (11,)]


# --- what goes wrong ---


def test_a_refused_login_is_one_sentence_without_the_password(pg, monkeypatch, capsys):
    monkeypatch.setenv(postgres.URL_KEY, changed_url(password="not-the-password"))
    monkeypatch.setattr(stash_sync.StashClient, "call", lambda *a, **k: pytest.fail("Stash was asked"))

    assert stash_sync.main(["--postgres", "--apply"]) == 1

    said = capsys.readouterr()
    assert said.out == ""
    assert said.err.startswith("error: Can't use the PostgreSQL database at ")
    assert "the user name or password was refused" in said.err
    assert "not-the-password" not in said.err and said.err.count("\n") == 1


def test_a_read_that_waits_on_another_programs_lock_gives_up(more_creators, pg, tmp_path, monkeypatch, capsys):
    bring_in(tmp_path / ".data")
    monkeypatch.setattr(postgres, "CHECKOUT_TIMEOUT", 1)
    monkeypatch.setattr(stash_sync.StashClient, "call", lambda *a, **k: pytest.fail("Stash was asked"))
    locked, done = threading.Event(), threading.Event()

    def hold():
        # as a program that is rebuilding the table would; let go in the
        # end, so that a read without a limit fails here and doesn't hang
        with psycopg.connect(URL) as other:
            other.execute(f"LOCK TABLE {pg['onlyfans']}.medias IN ACCESS EXCLUSIVE MODE")
            locked.set()
            done.wait(20)
            other.rollback()

    holder = threading.Thread(target=hold)
    holder.start()
    try:
        assert locked.wait(20)
        started = time.monotonic()
        code = stash_sync.main(["--postgres", "--apply"])
        waited = time.monotonic() - started
    finally:
        done.set()
        holder.join()

    said = capsys.readouterr()
    assert (code, said.out) == (1, "")
    assert said.err.startswith("error: Can't read the PostgreSQL database at ")
    assert "lock timeout" in said.err and said.err.count("\n") == 1
    assert waited < 15


def test_a_read_that_takes_too_long_is_ended_by_the_server(monkeypatch):
    monkeypatch.setattr(postgres, "READ_TIMEOUT", 1)
    reader = postgres.Reader(URL)
    started = time.monotonic()
    try:
        with pytest.raises(postgres.PostgresUnavailable) as raised:
            reader.rows("SELECT pg_sleep(20)")
    finally:
        reader.close()

    assert "statement timeout" in str(raised.value)
    assert time.monotonic() - started < 15


def as_login(user, password):
    """The test URL with another login."""
    url = urllib.parse.urlsplit(URL)
    return urllib.parse.urlunsplit(
        (url.scheme, f"{user}:{password}@{url.hostname}:{url.port or 5432}", url.path, "", "")
    )


def test_a_login_that_may_not_read_is_told_so_and_one_that_may_reads(
    more_creators, pg, stash_server, tmp_path, monkeypatch, capsys
):
    """A login that was never granted anything sees no tables at all: that
    isn't a database with nothing in it."""
    if not server("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user")[0][0]:
        pytest.skip("the test login may not make another login")
    bring_in(tmp_path / ".data")
    _, url = stash_server
    role, password = f"t_{uuid.uuid4().hex[:12]}_reader", "only-for-this-test"
    server(f"CREATE ROLE {role} LOGIN PASSWORD '{password}'")

    def run(*args):
        code = stash_sync.main(["--postgres", "--url", url, *args])
        said = capsys.readouterr()
        return code, said.out, said.err

    try:
        monkeypatch.setenv(postgres.URL_KEY, as_login(role, password))

        code, out, err = run()
        assert (code, out) == (1, "")
        assert err.startswith("error: Can't read the PostgreSQL database at ")
        assert "the user isn't allowed to read the onlyfans tables (" in err and ", medias, " in err
        assert err.count("\n") == 1 and password not in err

        # the right to read one site: that site is read, the other is said
        server(f"GRANT USAGE ON SCHEMA {pg['onlyfans']} TO {role}")
        server(f"GRANT SELECT ON ALL TABLES IN SCHEMA {pg['onlyfans']} TO {role}")
        code, out, err = run()
        assert (code, out) == (1, "")
        assert "the user isn't allowed to read the fansly tables (" in err
        code, out, err = run("--site", "onlyfans")
        assert (code, err) == (0, "")
        assert [m["performer"] for m in json.loads(out)["models"]] == [SECOND_NAME]

        # the right to read both is all the command needs
        server(f"GRANT USAGE ON SCHEMA {pg['fansly']} TO {role}")
        server(f"GRANT SELECT ON ALL TABLES IN SCHEMA {pg['fansly']} TO {role}")
        code, out, err = run()
        assert (code, err) == (0, "")
        assert [m["performer"] for m in json.loads(out)["models"]] == [SECOND_NAME, SAME_ID_NAME]
    finally:
        server(f"DROP OWNED BY {role}")
        server(f"DROP ROLE {role}")


def test_a_database_that_isnt_there_is_one_sentence(pg, monkeypatch, capsys):
    monkeypatch.setenv(postgres.URL_KEY, changed_url(path="/no_such_database"))

    assert stash_sync.main(["--postgres"]) == 1

    said = capsys.readouterr()
    assert said.out == ""
    assert "there is no database with that name on the server" in said.err
    assert said.err.count("\n") == 1
