"""The PostgreSQL engine against a real server (#608).

Skipped unless OFSC_TEST_POSTGRES_URL names a server the tests may use, e.g.
postgresql://postgres:password@localhost:5432/ofscraper_test. CI sets it for
a PostgreSQL container. Each test works in a schema of its own and drops it.
"""

import asyncio
import contextlib
import logging
import os
import sqlite3
import urllib.parse
import uuid
from types import SimpleNamespace

import arrow
import pytest
import tenacity

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.db.operations_.others as others
import ofscraper.db.operations_.posts as posts
import ofscraper.db.operations_.profile as profile
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.postgres as postgres
import ofscraper.filters.media.filters as filters
import ofscraper.utils.settings as settings
import ofscraper.sites as sites
from ofscraper.db.difference import ALL_FLAGS
from test.db_scenario import (
    ONE,
    TWO,
    NAMES,
    Clock,
    after_start,
    check,
    name_before_the_dates,
    post,
    record_names,
    scenario,
    table_rows,
)
from test.test_db_postgres import sqlite_columns

URL = os.environ.get("OFSC_TEST_POSTGRES_URL", "")
if not URL:
    pytest.skip(
        "needs a PostgreSQL server: set OFSC_TEST_POSTGRES_URL", allow_module_level=True
    )

# with a server named, a missing driver is a failure, not a skip
import psycopg  # noqa: E402

CREATOR = dict(model_id=ONE, username=NAMES[ONE])


def changed_url(**parts):
    """The test URL with a part swapped: password=, port=, path=."""
    url = urllib.parse.urlsplit(URL)
    password = parts.get("password", url.password)
    port = parts.get("port", url.port or 5432)
    login = f"{url.username}:{urllib.parse.quote(password, safe='')}"
    return urllib.parse.urlunsplit(
        (url.scheme, f"{login}@{url.hostname}:{port}", parts.get("path", url.path), "", "")
    )


def new_schema():
    return f"t_{uuid.uuid4().hex[:16]}"


def drop(*schemas):
    postgres.POSTGRES.shutdown()
    with psycopg.connect(URL, autocommit=True) as conn:
        for schema in schemas:
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


@pytest.fixture
def pg(monkeypatch):
    """PostgreSQL is configured, and the current site is a schema of this
    test's own."""
    schema = new_schema()
    monkeypatch.setenv(postgres.URL_KEY, URL)
    monkeypatch.setattr(sites, "current_site", lambda: schema)
    yield schema
    drop(schema)


@pytest.fixture
def no_wait(monkeypatch):
    monkeypatch.setattr(tenacity.nap.time, "sleep", lambda seconds: None)


@wrapper.operation_wrapper
def run_sql(sql, params=(), conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall() if cur.description else None
        conn.commit()
        return rows


def start(**creator):
    async def go():
        await operations.table_init_create(**(creator or CREATOR))

    asyncio.run(go())


# --- the same results as SQLite ---


def test_every_operation_gives_what_sqlite_gives(tmp_path, monkeypatch):
    with monkeypatch.context() as patch:
        path = tmp_path / "user_data.db"
        patch.delenv(postgres.URL_KEY, raising=False)
        patch.setattr(
            placeholder.databasePlaceholder,
            "databasePathHelper",
            lambda self, model_id, model_username: path,
        )
        on_sqlite = asyncio.run(scenario())

    schema = new_schema()
    try:
        with monkeypatch.context() as patch:
            patch.setenv(postgres.URL_KEY, URL)
            patch.setattr(sites, "current_site", lambda: schema)
            on_postgres = asyncio.run(scenario())
    finally:
        drop(schema)

    check(on_sqlite)
    check(on_postgres)
    assert list(on_postgres) == list(on_sqlite)
    different = {
        name: (on_sqlite[name], on_postgres[name])
        for name in on_sqlite
        if on_sqlite[name] != on_postgres[name]
    }
    assert different == {}


def test_values_keep_their_types(pg):
    start()
    rows = run_sql(
        "SELECT 712345678901234567 AS big, TRUE AS yes, NULL AS nothing,"
        " CAST('4.50' AS NUMERIC) AS price,"
        " CAST('2024-03-05T08:30:00+02:00' AS TIMESTAMPTZ) AS moment,"
        " ? AS text",
        ["it's 100% ?"],
        read_only=True,
    )
    row = rows[0]
    assert dict(row) == {
        "big": 712345678901234567,
        "yes": 1,
        "nothing": None,
        "price": 4.5,
        "moment": "2024-03-05T06:30:00+00:00",
        "text": "it's 100% ?",
    }
    assert row[0] == row["big"] == row["BIG"]
    assert type(row["yes"]) is int


# --- the tables ---


def test_the_tables_and_columns_are_sqlites(pg, tmp_path):
    start()
    expected = sqlite_columns(tmp_path)
    found = run_sql(
        "SELECT table_name, column_name FROM information_schema.columns"
        " WHERE table_schema = ?",
        [pg],
        read_only=True,
    )
    columns = {}
    for table, column in found:
        columns.setdefault(table, set()).add(column)
    assert columns == {table: set(names) for table, names in expected.items()}
    # and what the engine says without asking matches the server
    assert {t: set(c) for t, c in postgres.TABLE_COLUMNS.items()} == columns


def test_a_new_database_has_had_every_upgrade_step(pg):
    start()
    assert set(others.get_schema_changes(**CREATOR)) == set(ALL_FLAGS)


def test_starting_again_adds_nothing_and_marks_no_step_done(pg):
    start()
    run_sql("DELETE FROM schema_flags WHERE flag_name = 'media_hash'")
    # a new run: the tables are there, so no upgrade step is marked as done
    postgres.POSTGRES.shutdown()
    start()
    start(model_id=5, username="another")

    flags = set(others.get_schema_changes(**CREATOR))
    assert flags == set(ALL_FLAGS) - {"media_hash"}
    assert sorted(row["model_id"] for row in table_rows("models", **CREATOR)) == [5, ONE]
    assert len(table_rows("profiles", **CREATOR)) == 2


# --- tables made before the dates of a creator's names were kept (#643) ---


def before_the_dates():
    """Leave the tables as the version before made them, and start anew."""
    run_sql("ALTER TABLE profiles DROP COLUMN first_seen_at")
    run_sql("ALTER TABLE profiles DROP COLUMN last_seen_at")
    run_sql("DELETE FROM schema_flags WHERE flag_name = 'profiles_seen_at'")
    # a new run: nothing is remembered about the tables
    postgres.POSTGRES.shutdown()


def profile_columns(schema):
    with psycopg.connect(URL) as conn:
        return [
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = %s AND table_name = 'profiles'"
                " ORDER BY ordinal_position",
                [schema],
            )
        ]


def profile_rows(schema):
    with psycopg.connect(URL) as conn:
        return conn.execute(f"SELECT * FROM {schema}.profiles ORDER BY id").fetchall()


def name_of_a_deleted_account():
    async def go():
        return await profile.get_profile_info(**CREATOR)

    return asyncio.run(go())


def test_tables_made_before_the_dates_get_the_columns_and_keep_their_rows(
    pg, monkeypatch
):
    clock = Clock()
    monkeypatch.setattr(profile, "_now", clock)
    start()
    record_names(["zeta_name", "alpha_name"], **CREATOR)
    before_the_dates()
    assert profile_columns(pg) == ["id", "user_id", "username"]
    before = profile_rows(pg)
    assert [row[1:] for row in before] == [
        (ONE, NAMES[ONE]),
        (ONE, "zeta_name"),
        (ONE, "alpha_name"),
    ]
    # read as they are, before anything is changed: the name is the one the
    # version before gave
    assert name_of_a_deleted_account() == name_before_the_dates(**CREATOR)
    assert profile_columns(pg) == ["id", "user_id", "username"]

    clock.later(days=1)
    start(model_id=ONE, username="zeta_name")

    assert profile_columns(pg) == [
        "id",
        "user_id",
        "username",
        "first_seen_at",
        "last_seen_at",
    ]
    assert set(others.get_schema_changes(**CREATOR)) == set(ALL_FLAGS)
    # each row with the id it had; the only date is of the name this run
    # is under
    rows = profile_rows(pg)
    assert [row[:3] for row in rows] == before
    assert [row[3] for row in rows] == [None, None, None]
    assert [row[4] and arrow.get(row[4]).to("UTC").isoformat() for row in rows] == [
        None,
        after_start(days=1),
        None,
    ]
    assert name_of_a_deleted_account() == "zeta_name"


def test_tables_brought_up_to_date_are_left_alone_at_the_next_start(pg, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(profile, "_now", clock)
    start()
    before_the_dates()
    start()
    rows = profile_rows(pg)
    flags = sorted(others.get_schema_changes(**CREATOR))
    # the step is not marked again once it is done
    run_sql("DELETE FROM schema_flags WHERE flag_name = 'profiles_seen_at'")

    postgres.POSTGRES.shutdown()
    clock.later(minutes=5)
    start()

    assert profile_rows(pg) == rows
    assert len(profile_columns(pg)) == 5
    assert sorted(others.get_schema_changes(**CREATOR)) == [
        flag for flag in flags if flag != "profiles_seen_at"
    ]


def test_tables_with_one_of_the_columns_get_the_other(pg):
    # the change is one transaction, so a table isn't left like this: it is
    # put right all the same
    start()
    run_sql("ALTER TABLE profiles DROP COLUMN last_seen_at")
    run_sql("DELETE FROM schema_flags WHERE flag_name = 'profiles_seen_at'")
    postgres.POSTGRES.shutdown()

    start()

    assert sorted(profile_columns(pg)) == sorted(postgres.TABLE_COLUMNS["profiles"])
    assert set(others.get_schema_changes(**CREATOR)) == set(ALL_FLAGS)


def test_two_programs_bringing_the_tables_up_to_date_at_once_both_succeed(pg, no_wait):
    import concurrent.futures

    start()
    before_the_dates()

    def make():
        engine = postgres.PostgresBackend()
        try:
            engine.create_tables(ALL_FLAGS)
        finally:
            engine.shutdown()

    with concurrent.futures.ThreadPoolExecutor(4) as workers:
        for done in [workers.submit(make) for _ in range(4)]:
            done.result()

    assert len(profile_columns(pg)) == 5
    assert set(others.get_schema_changes(**CREATOR)) == set(ALL_FLAGS)
    assert len(profile_rows(pg)) == 1


def test_names_without_dates_go_by_the_databases_own_order(pg):
    # the order of names is the database's, as it was before the dates:
    # whatever it is here, the name is the first in it
    start()
    run_sql("DELETE FROM profiles")
    record_names(["moe", "Zed", "abe", "Abe", "_abe"], **CREATOR)
    first = run_sql(
        "SELECT username FROM profiles WHERE user_id = ? ORDER BY username LIMIT 1",
        [ONE],
        read_only=True,
    )[0][0]

    assert name_of_a_deleted_account() == first == name_before_the_dates(**CREATOR)
    # and the same after the tables are read as they were before the dates
    before_the_dates()
    assert name_of_a_deleted_account() == first


def last_seen(schema):
    """{name: when it was last seen, in UTC}."""
    return {
        row[2]: row[4] and arrow.get(row[4]).to("UTC").isoformat()
        for row in profile_rows(schema)
    }


def test_a_date_another_program_moved_meanwhile_is_not_moved_back(pg, monkeypatch):
    # two programs start the same creator: each reads the name's date and
    # then writes its own time, and nothing keeps the other out between
    clock = Clock()
    monkeypatch.setattr(profile, "_now", clock)
    start()
    clock.later(days=1)
    decide = profile._seen_again
    others_time = after_start(days=1, seconds=5)

    def meanwhile(seen, username, now):
        # the other program's clock is seconds ahead of this one's
        with psycopg.connect(URL, autocommit=True) as conn:
            conn.execute(f"UPDATE {pg}.profiles SET last_seen_at = %s", [others_time])
        return decide(seen, username, now)

    monkeypatch.setattr(profile, "_seen_again", meanwhile)

    start()

    assert last_seen(pg) == {NAMES[ONE]: others_time}


def test_the_statement_that_moves_a_date_only_moves_it_forward(pg):
    start()
    run_sql("DELETE FROM profiles")
    dates = {
        "older": after_start(seconds=-1),
        "same": after_start(),
        "newer": after_start(seconds=1),
        "undated": None,
    }
    for name, date in dates.items():
        run_sql(
            "INSERT INTO profiles (user_id, username, last_seen_at) VALUES (?, ?, ?)",
            [ONE, name, date],
        )

    for name in dates:
        run_sql(profile.profileSeenAgain, [after_start(), ONE, name, after_start(), None])

    assert last_seen(pg) == {
        "older": after_start(),
        "same": after_start(),
        "newer": after_start(seconds=1),
        "undated": after_start(),
    }


def test_each_site_has_its_own_tables(monkeypatch):
    first, second = new_schema(), new_schema()
    monkeypatch.setenv(postgres.URL_KEY, URL)
    try:
        async def save_and_read():
            await operations.table_init_create(**CREATOR)
            await posts.make_post_table_changes([post(10)], **CREATOR)
            return await posts.get_all_post_ids(**CREATOR)

        monkeypatch.setattr(sites, "current_site", lambda: first)
        assert asyncio.run(save_and_read()) == [10]

        async def read():
            await operations.table_init_create(**CREATOR)
            return await posts.get_all_post_ids(**CREATOR)

        monkeypatch.setattr(sites, "current_site", lambda: second)
        assert asyncio.run(read()) == []
    finally:
        drop(first, second)


def test_a_read_before_the_tables_exist_finds_no_database(pg):
    # as a read-only read of a creator with no SQLite file does
    with pytest.raises(wrapper.DatabaseMissing):
        table_rows("medias", read_only=True, **CREATOR)


# --- transactions and errors ---


def test_a_read_only_operation_cannot_write(pg, no_wait):
    start()
    tries = []

    @wrapper.operation_wrapper
    def write(conn=None, **kwargs):
        tries.append(1)
        conn.execute("INSERT INTO models (model_id) VALUES (?)", [77])
        conn.commit()

    with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
        write(read_only=True)
    assert len(tries) == 1
    assert [row["model_id"] for row in table_rows("models", **CREATOR)] == [ONE]


def test_a_write_after_a_read_only_operation_still_writes(pg, no_wait):
    # connections go back to the pool and come out again: "read only" must
    # not stay on one. More rounds than the pool has connections
    start()

    @wrapper.operation_wrapper
    def write(number, conn=None, **kwargs):
        conn.execute("INSERT INTO models (model_id) VALUES (?)", [number])
        conn.commit()

    for number in range(1000, 1000 + postgres.POOL_SIZE * 2):
        table_rows("models", read_only=True, **CREATOR)
        write(number)

    assert len(table_rows("models", **CREATOR)) == 1 + postgres.POOL_SIZE * 2


def test_two_programs_making_the_tables_at_once_both_succeed(pg, no_wait):
    # each new program checks and makes the tables under one lock
    import concurrent.futures

    def make():
        engine = postgres.PostgresBackend()
        try:
            engine.create_tables(ALL_FLAGS)
        finally:
            engine.shutdown()

    with concurrent.futures.ThreadPoolExecutor(4) as workers:
        for done in [workers.submit(make) for _ in range(4)]:
            done.result()

    assert len(others.get_schema_changes(**CREATOR)) == len(ALL_FLAGS)


def test_dates_are_read_the_same_whatever_the_servers_date_style(pg, no_wait):
    start()
    with psycopg.connect(URL, autocommit=True) as conn:
        database = conn.execute("SELECT current_database()").fetchone()[0]
        conn.execute(f'ALTER DATABASE "{database}" SET DateStyle TO \'German, DMY\'')
    try:
        postgres.POSTGRES.shutdown()
        start()

        async def go():
            await posts.write_post_table([post(10)], **CREATOR)
            return await posts.get_all_posts_transition(**CREATOR)

        saved = asyncio.run(go())
    finally:
        with psycopg.connect(URL, autocommit=True) as conn:
            conn.execute(f'ALTER DATABASE "{database}" RESET DateStyle')
    assert saved[0]["created_at"] == "2024-01-03T03:04:05+00:00"


def test_media_another_creator_downloaded_is_not_left_out(pg, no_wait, monkeypatch):
    # by default a run leaves out what the database says is downloaded. One
    # database holds every creator here, and only the creator's own count
    stub = SimpleNamespace(
        force_all=False,
        force_model_unique=False,
        allow_dupe_downloads=False,
        retry_permanent_skips=False,
    )
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    other = dict(model_id=TWO, username=NAMES[TWO])
    start()
    start(**other)
    run_sql(
        "INSERT INTO medias (media_id, post_id, model_id, downloaded)"
        " VALUES (?, ?, ?, ?)",
        [77, 1, ONE, True],
        **CREATOR,
    )

    assert filters.downloaded_media_ids(**CREATOR) == {77}
    assert filters.downloaded_media_ids(**other) == set()

    stub.allow_dupe_downloads = True
    assert filters.downloaded_media_ids(**CREATOR) == {(77, 1)}
    assert filters.downloaded_media_ids(**other) == set()


def test_what_is_not_committed_is_rolled_back(pg, no_wait):
    start()

    @wrapper.operation_wrapper
    def write_then_fail(conn=None, **kwargs):
        conn.execute("INSERT INTO models (model_id) VALUES (?)", [77])
        raise ValueError("no")

    with pytest.raises(ValueError):
        write_then_fail()
    assert [row["model_id"] for row in table_rows("models", **CREATOR)] == [ONE]


def test_a_failed_statement_does_not_spoil_the_next_operation(pg, no_wait):
    start()
    # more failures than the pool has connections: each one is given back
    for _ in range(postgres.POOL_SIZE + 2):
        with pytest.raises(psycopg.errors.UniqueViolation) as raised:
            run_sql("INSERT INTO models (model_id) VALUES (?)", [ONE])
        assert "PostgreSQL" in raised.value.database_path
    assert run_sql("SELECT model_id FROM models", read_only=True) == [(ONE,)]


def test_a_lost_connection_is_retried_on_a_new_one(pg, no_wait):
    start()
    tries = []

    @wrapper.operation_wrapper
    def work(conn=None, **kwargs):
        tries.append(1)
        if len(tries) == 1:
            conn.execute("SELECT pg_terminate_backend(pg_backend_pid())")
        return conn.execute("SELECT model_id FROM models").fetchone()[0]

    assert work() == ONE
    assert len(tries) == 2


def test_a_mistake_in_the_sql_is_not_retried(pg, no_wait):
    start()
    tries = []

    @wrapper.operation_wrapper
    def work(conn=None, **kwargs):
        tries.append(1)
        conn.execute("SELECT nothing FROM models")

    with pytest.raises(psycopg.errors.UndefinedColumn):
        work()
    assert len(tries) == 1


# --- the startup check ---


def test_the_startup_check_names_the_server_version(pg):
    version = postgres.POSTGRES.check()
    with psycopg.connect(URL) as conn:
        number = int(conn.execute("SHOW server_version_num").fetchone()[0])
    assert version == f"{number // 10000}.{number % 10000}"
    assert number // 10000 >= postgres.MIN_SERVER


@pytest.mark.parametrize(
    "change, sentence",
    [
        (dict(password="not-the-password"), "the user name or password was refused"),
        (dict(port=1), "the server can't be reached"),
        (dict(path="/no_such_database_here"), "there is no database with that name"),
    ],
    ids=["wrong password", "no server", "no such database"],
)
def test_a_server_that_cannot_be_used_stops_with_one_sentence(
    monkeypatch, caplog, change, sentence
):
    url = changed_url(**change)
    monkeypatch.setenv(postgres.URL_KEY, url)
    monkeypatch.setattr(sites, "current_site", new_schema)
    monkeypatch.setattr(postgres, "CONNECT_TIMEOUT", 5)
    try:
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(postgres.PostgresUnavailable) as raised:
                postgres.POSTGRES.check()
    finally:
        postgres.POSTGRES.shutdown()

    message = str(raised.value)
    assert sentence in message
    assert "\n" not in message
    password = urllib.parse.urlsplit(url).password
    assert password not in message
    assert password not in caplog.text
    # and it isn't tried again and again
    assert wrapper._retryable(raised.value) is False


def test_sqlite_files_are_untouched_by_a_database_url(pg, tmp_path):
    # merge, and the upgrade of one file, name their file
    path = tmp_path / "user_data.db"

    async def make():
        await operations.create_tables(db_path=path)

    asyncio.run(make())

    with contextlib.closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM medias").fetchone() == (0,)
    with pytest.raises(wrapper.DatabaseMissing):
        table_rows("medias", read_only=True, **CREATOR)
