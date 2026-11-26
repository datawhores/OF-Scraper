"""The optional PostgreSQL engine (#608): everything that needs no server.

The engine itself is run against a real server in test_db_postgres_live,
which CI runs with a PostgreSQL container.
"""

import asyncio
import builtins
import contextlib
import importlib.util
import logging
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.postgres as postgres
import ofscraper.filters.media.filters as filters
import ofscraper.utils.config.data as config_data
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.schema as config_schema
import ofscraper.utils.settings as settings
import ofscraper.main.open.run as run
import ofscraper.utils.logs.classes.classes as log_classes
from ofscraper.db.difference import ALL_FLAGS
from ofscraper.db.transition import modify_tables
from test.db_scenario import check, scenario

URL = "postgresql://scraper:s3cr%40t-word@db.example:5433/library"


@pytest.fixture
def sqlite_file(tmp_path, monkeypatch):
    """Every creator's database is one SQLite file, as with a `metadata`
    folder that doesn't name the creator."""
    path = tmp_path / "user_data.db"
    monkeypatch.delenv(postgres.URL_KEY, raising=False)
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: path,
    )
    return path


def test_the_scenario_on_sqlite(sqlite_file):
    check(asyncio.run(scenario()))


# --- which engine ---


def test_sqlite_is_used_without_a_url(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)
    assert postgres.url() == ""
    assert wrapper.backend_for({}) is wrapper.SQLITE


def test_a_url_selects_postgresql_but_a_named_file_is_still_sqlite(monkeypatch):
    pytest.importorskip("psycopg")
    monkeypatch.setenv(postgres.URL_KEY, f"  {URL}  ")
    assert postgres.url() == URL
    assert wrapper.backend_for({}) is postgres.POSTGRES
    assert wrapper.backend_for({"model_id": 5}) is postgres.POSTGRES
    # merge, the upgrade of one file and the tests name their file
    assert wrapper.backend_for({"db_path": "some.db"}) is wrapper.SQLITE
    psycopg = pytest.importorskip("psycopg")
    assert psycopg.Error in wrapper.DB_ERRORS
    assert sqlite3.Error in wrapper.DB_ERRORS


def test_a_missing_driver_is_one_sentence(monkeypatch):
    real_import = builtins.__import__

    def no_driver(name, *args, **kwargs):
        if name.split(".")[0] in ("psycopg", "psycopg_pool"):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_driver)

    with pytest.raises(postgres.PostgresUnavailable) as raised:
        postgres._driver()
    message = str(raised.value)
    assert postgres.URL_KEY in message
    assert "[postgres]" in message
    assert "\n" not in message
    # not an error a retry can fix
    assert wrapper._retryable(raised.value) is False


def test_the_startup_check_does_nothing_for_sqlite(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)
    monkeypatch.setattr(
        postgres.POSTGRES, "check", lambda: pytest.fail("no server to check")
    )
    run.check_database()


def test_the_startup_check_asks_the_server_when_a_url_is_set(monkeypatch, caplog):
    # the server is named as the driver reads the address
    pytest.importorskip("psycopg")
    monkeypatch.setenv(postgres.URL_KEY, URL)
    monkeypatch.setattr(postgres.POSTGRES, "check", lambda: "16.4")

    with caplog.at_level(logging.INFO, logger="shared"):
        run.check_database()

    assert "db.example:5433/library" in caplog.text
    assert "16.4" in caplog.text
    assert "s3cr" not in caplog.text
    assert "scraper" not in caplog.text


# --- where people look for the setting ---


def test_config_json_says_where_the_database_setting_is():
    # the file can't hold a comment: a key of its own holds the note
    written = config_schema.get_current_config_schema(config=False)
    note = written["advanced_options"]["database_url"]
    assert postgres.URL_KEY in note
    assert "POSTGRESQL.md" in note
    assert "env_files" in note


@pytest.mark.parametrize(
    "written",
    [
        URL,
        "",
        None,
        {"url": URL},
    ],
)
def test_an_address_written_in_config_json_is_not_used_or_kept(monkeypatch, written):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)
    config = {"advanced_options": {"database_url": written}, "database_url": written}

    rebuilt = config_schema.get_current_config_schema(config=config)

    # the file is rewritten from this: the password doesn't stay in it
    assert rebuilt["advanced_options"]["database_url"] == config_data.DATABASE_URL_NOTE
    assert "s3cr" not in str(rebuilt)
    assert postgres.enabled() is False


@pytest.mark.parametrize(
    "config, said",
    [
        ({"advanced_options": {"database_url": URL}}, True),
        ({"database_url": URL}, True),
        ({"config": {"advanced_options": {"database_url": URL}}}, True),
        ({"advanced_options": {"database_url": config_data.DATABASE_URL_NOTE}}, False),
        ({"advanced_options": {"database_url": ""}}, False),
        ({"advanced_options": {}}, False),
        ({"advanced_options": None}, False),
    ],
)
def test_an_address_written_in_config_json_is_said_to_be_unused(
    monkeypatch, caplog, config, said
):
    monkeypatch.setattr(config_file, "write_config", lambda config: None)
    monkeypatch.setattr(config_file, "_notes", [])

    with caplog.at_level(logging.WARNING, logger="shared"):
        config_file.auto_update_config(config)
        # kept until the log is set up, then written
        config_file.log_notes()

    assert ("database_url in config.json is not read" in caplog.text) is said
    assert "OFSC_DATABASE_URL" in caplog.text or not said
    # the address isn't repeated: it holds a password
    assert "s3cr" not in caplog.text


# --- what counts as already downloaded ---


@pytest.fixture
def asked(monkeypatch):
    """Which list of downloaded media a run asks the database for."""
    stub = SimpleNamespace(
        force_all=False,
        force_model_unique=False,
        allow_dupe_downloads=False,
        retry_permanent_skips=False,
    )
    calls = Calls()
    calls.stub = stub
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    monkeypatch.setattr(
        filters,
        "get_media_ids_downloaded",
        lambda **kwargs: calls.append("the database's") or {1, 2},
    )
    monkeypatch.setattr(
        filters,
        "get_media_ids_downloaded_model_sync",
        lambda **kwargs: calls.append("the creator's") or {1},
    )
    monkeypatch.setattr(
        filters,
        "get_media_post_ids_downloaded",
        lambda **kwargs: calls.append(("pairs", kwargs["model_only"])) or [],
    )
    return calls


class Calls(list):
    """A list that also carries the settings the test may change."""

    stub = None


def test_a_sqlite_file_is_asked_for_everything_it_holds(monkeypatch, asked):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)

    assert filters.downloaded_media_ids(username="a_creator", model_id=5) == {1, 2}
    asked.stub.allow_dupe_downloads = True
    filters.downloaded_media_ids(username="a_creator", model_id=5)

    assert asked == ["the database's", ("pairs", False)]


def test_postgresql_is_asked_for_the_creators_own_media(monkeypatch, asked):
    # it holds every creator: media another creator downloaded isn't left out,
    # as it never was with a file per creator
    pytest.importorskip("psycopg")
    monkeypatch.setenv(postgres.URL_KEY, URL)

    assert filters.downloaded_media_ids(username="a_creator", model_id=5) == {1}
    asked.stub.allow_dupe_downloads = True
    filters.downloaded_media_ids(username="a_creator", model_id=5)

    assert asked == ["the creator's", ("pairs", True)]


def test_force_model_unique_asks_for_the_creators_own_media_on_either(monkeypatch, asked):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)
    asked.stub.force_model_unique = True

    assert filters.downloaded_media_ids(username="a_creator", model_id=5) == {1}
    assert asked == ["the creator's"]


# --- the password ---


@pytest.mark.parametrize(
    "url, password",
    [
        (URL, "s3cr@t-word"),
        ("host=db.example dbname=library user=scraper password=s3cr@t-word", "s3cr@t-word"),
        ("host=db.example password='two words'", "two words"),
        ("postgresql://db.example/library", None),
        ("", None),
    ],
)
def test_the_password_is_found_in_either_spelling(url, password):
    # as the driver reads the address
    pytest.importorskip("psycopg")
    secrets = postgres._secrets(url)
    if password is None:
        assert secrets == []
    else:
        assert password in secrets
        # and the URL itself, longest first
        assert secrets[0] == url


@pytest.mark.parametrize(
    "url",
    [
        # a mistyped scheme, or none: the driver quotes the whole URL back
        "postgresql:/scraper:SECRETpw@db.example/library",
        "postgres//scraper:SECRETpw@db.example/library",
        "scraper:SECRETpw@db.example/library",
        # an @ in the password that wasn't written as %40: the driver takes
        # what follows it for the server's name
        "postgresql://scraper:xx@SECRETpw@db.example/library",
        "postgresql://scraper:SECRETpw@more@db.example/library",
    ],
)
def test_a_url_that_isnt_read_as_meant_is_one_sentence_without_it(url):
    # what the driver says of it quotes the address: it isn't shown at all
    psycopg = pytest.importorskip("psycopg")
    said = [
        psycopg.ProgrammingError(f'missing "=" after "{url}" in connection info string'),
        psycopg.OperationalError("failed to resolve host 'SECRETpw@db.example': Name or service not known"),
    ]
    for error in said:
        message = str(postgres.POSTGRES._unavailable(error, url))
        assert "SECRETpw" not in message
        assert postgres.URL_KEY in message
    assert postgres.describe(url) == "the configured database"


def test_only_the_variable_with_the_scrapers_name_turns_postgresql_on(monkeypatch):
    # DATABASE_URL is set for other software on many machines
    monkeypatch.delenv(postgres.URL_KEY, raising=False)
    for name in ("DATABASE_URL", "POSTGRES_URL", "PGHOST", "PGDATABASE"):
        monkeypatch.setenv(name, URL)
    assert postgres.enabled() is False
    assert wrapper.backend_for({}) is wrapper.SQLITE
    monkeypatch.setenv("OFSC_DATABASE_URL", URL)
    assert postgres.enabled() is True


def test_messages_name_the_server_and_never_the_login():
    pytest.importorskip("psycopg")
    assert postgres.describe(URL) == "db.example:5433/library"
    assert postgres.describe("host=db.example password=x") == "the configured database"
    masked = postgres.masked(f"could not connect to {URL}: s3cr@t-word", URL)
    assert "s3cr" not in masked
    assert "{hidden}" in masked


def test_the_password_is_hidden_from_every_log_line(monkeypatch):
    import ofscraper.utils.logs.utils.sensitive as sensitive

    # the password is found as the driver reads the address
    pytest.importorskip("psycopg")
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    postgres.POSTGRES._hide_password(URL)

    record = logging.LogRecord(
        "shared", logging.ERROR, __file__, 1,
        f"connection to db.example failed (password s3cr@t-word, from {URL})",
        None, None,
    )
    line = log_classes.SensitiveFormatter("%(message)s").format(record)

    assert "s3cr" not in line
    assert "db.example failed" in line


def test_opening_the_pool_hides_the_password_first(monkeypatch):
    psycopg = pytest.importorskip("psycopg")
    import ofscraper.utils.logs.utils.sensitive as sensitive

    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    monkeypatch.setenv(postgres.URL_KEY, URL)

    def refused(*args, **kwargs):
        raise psycopg.OperationalError(
            'connection failed: FATAL: password authentication failed for user'
            ' "scraper" (s3cr@t-word)'
        )

    monkeypatch.setattr(psycopg, "connect", refused)

    with pytest.raises(postgres.PostgresUnavailable) as raised:
        postgres.POSTGRES._open_pool("onlyfans", 30)

    message = str(raised.value)
    assert "the user name or password was refused" in message
    assert "db.example:5433/library" in message
    assert "s3cr" not in message
    # and from then on, out of every log line
    record = logging.LogRecord(
        "shared", logging.ERROR, __file__, 1, "tried s3cr@t-word", None, None
    )
    assert "s3cr" not in log_classes.SensitiveFormatter("%(message)s").format(record)


def unavailable(error, url=URL):
    return str(postgres.POSTGRES._unavailable(error, url))


def test_a_connection_that_cant_be_made_gets_its_own_sentence():
    psycopg = pytest.importorskip("psycopg")
    psycopg_pool = pytest.importorskip("psycopg_pool")
    error = psycopg.OperationalError

    assert "user name or password was refused" in unavailable(
        error('FATAL: role "nobody" does not exist')
    )
    assert "no database with that name" in unavailable(
        error('FATAL: database "library" does not exist')
    )
    # a server whose name has "database" in it is not a missing database
    assert "the server can't be reached" in unavailable(
        error("failed to resolve host 'database.example': name does not exist")
    )
    assert "isn't allowed" in unavailable(psycopg.errors.InsufficientPrivilege("no"))
    assert "another program is setting up" in unavailable(
        psycopg.errors.LockNotAvailable("lock timeout")
    )
    assert "down or busy" in unavailable(psycopg_pool.PoolTimeout("30 sec"))


def test_an_address_the_driver_cant_read_is_said_without_quoting_it():
    psycopg = pytest.importorskip("psycopg")
    url = "postgresql:/scraper:SECRETpw@db.example/library"

    message = unavailable(
        psycopg.ProgrammingError(f'missing "=" after "{url}" in connection info'), url
    )

    assert f"{postgres.URL_KEY} isn't an address PostgreSQL can read" in message
    assert "SECRETpw" not in message and "scraper" not in message


def state(name):
    psycopg = pytest.importorskip("psycopg")
    return getattr(psycopg.errors, name)("it happened")


@pytest.mark.parametrize(
    "name, again",
    [
        ("SerializationFailure", True),
        ("DeadlockDetected", True),
        ("LockNotAvailable", True),
        ("AdminShutdown", True),
        ("ConnectionFailure", True),
        ("QueryCanceled", False),
        ("DiskFull", False),
        ("OutOfMemory", False),
        ("TooManyConnections", False),
        ("InvalidPassword", False),
        ("UndefinedTable", False),
        ("UniqueViolation", False),
    ],
)
def test_only_an_error_a_retry_can_fix_is_retried(name, again, monkeypatch):
    # With the driver installed, the wrapper knows PostgreSQL's errors once a
    # run picks PostgreSQL. Pick it here as a run does, so this test doesn't
    # rely on an earlier one having done it, and put the wrapper's engine list
    # back afterwards. Without the driver there is nothing to pick.
    if importlib.util.find_spec("psycopg"):
        monkeypatch.setattr(wrapper, "_BACKENDS", list(wrapper._BACKENDS))
        monkeypatch.setattr(wrapper, "DB_ERRORS", wrapper.DB_ERRORS)
        monkeypatch.setattr(wrapper, "OPERATIONAL_ERRORS", wrapper.OPERATIONAL_ERRORS)
        monkeypatch.setenv(postgres.URL_KEY, URL)
        assert wrapper.backend_for({}) is postgres.POSTGRES

    assert postgres.POSTGRES.retryable(state(name)) is again
    assert wrapper._retryable(state(name)) is again


def test_a_connection_lost_without_a_word_from_the_server_is_retried():
    psycopg = pytest.importorskip("psycopg")
    assert postgres.POSTGRES.retryable(psycopg.OperationalError("closed")) is True
    assert postgres.POSTGRES.retryable(psycopg.InterfaceError("closed")) is False
    assert postgres.POSTGRES.retryable(ValueError("no")) is False


def test_waiting_for_another_writer_is_busy_and_nothing_else_is():
    assert postgres.POSTGRES.busy(state("LockNotAvailable")) is True
    assert postgres.POSTGRES.busy(state("DeadlockDetected")) is True
    assert postgres.POSTGRES.busy(state("SerializationFailure")) is False
    assert postgres.POSTGRES.busy(state("DiskFull")) is False


def test_a_server_that_has_gone_is_not_waited_on_for_minutes(monkeypatch):
    pytest.importorskip("psycopg")
    waits = []

    class Pool:
        def getconn(self, timeout):
            waits.append(timeout)
            return SimpleNamespace()

    monkeypatch.setattr(postgres.POSTGRES, "_pool", lambda where, timeout: Pool())

    # DATABASE_TIMEOUT is 300 seconds by default
    postgres.POSTGRES.connect("onlyfans", True, timeout=300)
    postgres.POSTGRES.connect("onlyfans", False, timeout=5)

    assert waits == [postgres.CHECKOUT_TIMEOUT, 5]


def test_a_server_too_old_is_refused_at_startup(monkeypatch):
    def connect(version):
        return lambda *args, **kwargs: SimpleNamespace(
            info=SimpleNamespace(server_version=version)
        )

    monkeypatch.setattr(postgres.POSTGRES, "where", lambda kwargs, read_only: "onlyfans")
    monkeypatch.setattr(postgres.POSTGRES, "close", lambda conn: None)
    monkeypatch.setenv(postgres.URL_KEY, URL)

    monkeypatch.setattr(postgres.POSTGRES, "connect", connect(140011))
    with pytest.raises(postgres.PostgresUnavailable, match="is version 14; 15 or newer"):
        postgres.POSTGRES.check()

    monkeypatch.setattr(postgres.POSTGRES, "connect", connect(150004))
    assert postgres.POSTGRES.check() == "15.4"


def test_each_engine_saves_a_date_its_own_way():
    # SQLite keeps what it's given; PostgreSQL gets a date it can read
    assert wrapper.SQLITE.date_value(1709285400) == 1709285400
    assert postgres.POSTGRES.date_value(1709285400) == "2024-03-01T09:30:00+00:00"
    assert postgres.POSTGRES.date_value("") is None


# --- the SQL and the values ---


def test_placeholders_are_translated_outside_quotes():
    assert (
        postgres.translate("SELECT a FROM t WHERE b=(?) AND c = ? AND d LIKE '100%?'")
        == "SELECT a FROM t WHERE b=(%s) AND c = %s AND d LIKE '100%%?'"
    )


def test_a_row_reads_like_an_sqlite_row():
    row = postgres._row_class(("media_id", "Post_ID"))((1, 2))
    assert row[0] == 1
    assert row["post_id"] == 2 and row["POST_ID"] == 2
    assert dict(row) == {"media_id": 1, "Post_ID": 2}
    assert row.keys() == ["media_id", "Post_ID"]
    media_id, post_id = row
    assert (media_id, post_id) == (1, 2)
    assert row == (1, 2)
    with pytest.raises(IndexError):
        row["nothing"]


def test_an_id_kept_as_text_is_read_as_sqlite_gives_it():
    # medias.media_id and post_id, and labels.label_id, are TEXT: a profile
    # picture's ids are hashes. A whole number in one is read as a number
    def column(name, type_code):
        return SimpleNamespace(name=name, type_code=type_code)

    text, bigint = 25, 20
    cursor = SimpleNamespace(
        description=[
            column("media_id", text),
            column("POST_ID", text),
            column("label_id", text),
            column("filename", text),
            column("model_id", bigint),
        ]
    )
    make = postgres.row_factory(cursor)

    row = make(["12", "0123456789abcdef0123456789abcdef", None, "34", 5])
    assert tuple(row) == (12, "0123456789abcdef0123456789abcdef", None, "34", 5)
    assert row["post_id"] == "0123456789abcdef0123456789abcdef"
    assert dict(row)["media_id"] == 12
    # only what str() writes for a number: anything else is the text saved
    assert tuple(make(["007", "+5", "-3", " 4", 5])) == ("007", "+5", -3, " 4", 5)
    assert tuple(make([str(2**70), "0", "1.0", "", 5]))[:3] == (2**70, 0, "1.0")
    # a query without such a column gets the plain row class
    plain = postgres.row_factory(
        SimpleNamespace(description=[column("post_id", bigint), column("text", text)])
    )
    assert issubclass(plain, postgres.Row)


def test_the_ids_that_are_not_always_numbers_are_text():
    kinds = {
        (table, line.split()[0]): line.split()[1].rstrip(",")
        for table, create in postgres.TABLES.items()
        for line in create.splitlines()
        if line.startswith("    ") and line.split()[0] in postgres.LOOSE_IDS
    }
    assert {key for key, kind in kinds.items() if kind == "TEXT"} == {
        ("medias", "media_id"),
        ("medias", "post_id"),
        ("labels", "label_id"),
    }
    assert {kind for key, kind in kinds.items()} == {"TEXT", "BIGINT"}


@pytest.mark.parametrize(
    "text, iso",
    [
        ("2024-01-02 03:04:05+00", "2024-01-02T03:04:05+00:00"),
        ("2024-01-02 03:04:05.25+00", "2024-01-02T03:04:05.25+00:00"),
        ("2024-01-02 03:04:05+05:30", "2024-01-02T03:04:05+05:30"),
    ],
)
def test_a_timestamp_comes_back_as_iso_text(text, iso):
    assert postgres.iso(text) == iso


@pytest.mark.parametrize("text, value", [("5", 5), ("5.00", 5), ("4.99", 4.99), ("-2", -2)])
def test_a_numeric_comes_back_as_sqlite_gave_it(text, value):
    result = postgres.number(text)
    assert result == value and type(result) is type(value)


@pytest.mark.parametrize(
    "value, saved",
    [
        ("2023-01-01T12:00:00+00:00", "2023-01-01T12:00:00+00:00"),
        ("2023-06-01T10:00:00+02:00", "2023-06-01T10:00:00+02:00"),
        # no offset is UTC, as the app reads it back
        ("2023-01-01T12:00:00", "2023-01-01T12:00:00+00:00"),
        ("2023-01-01 12:00:00", "2023-01-01T12:00:00+00:00"),
        # seconds since 1970, as a number or as text
        (1700000000, "2023-11-14T22:13:20+00:00"),
        ("1700000000", "2023-11-14T22:13:20+00:00"),
        ("", None),
        (None, None),
    ],
)
def test_a_date_is_saved_as_one_format(value, saved):
    assert postgres.date_value(value) == saved


def test_sqlite_saves_a_date_as_it_came(tmp_path):
    with contextlib.closing(sqlite3.connect(tmp_path / "a.db")) as conn:
        assert wrapper.date_value(conn, "2023-01-01 12:00:00") == "2023-01-01 12:00:00"
        assert wrapper.date_value(conn, 1700000000) == 1700000000
        assert wrapper.date_value(conn, None) is None


def test_values_go_in_as_untyped_text_and_come_out_as_sqlite_gave_them():
    psycopg = pytest.importorskip("psycopg")
    from psycopg.adapt import PyFormat, Transformer

    adapters = postgres._adapters()
    transformer = Transformer(adapters)

    def sent(value):
        dumper = transformer.get_dumper(value, PyFormat.AUTO)
        return dumper.oid, bytes(dumper.dump(value))

    # oid 0: the server reads the text as its column's type
    assert sent(1) == (0, b"1")
    assert sent(True) == (0, b"1")
    assert sent(False) == (0, b"0")
    assert sent(4.99) == (0, b"4.99")
    assert sent(712345678901234567) == (0, b"712345678901234567")
    assert sent("text") == (0, b"text")

    def read(type_name, data):
        loader = transformer.get_loader(adapters.types[type_name].oid, psycopg.pq.Format.TEXT)
        return loader.load(data)

    assert read("bool", b"t") == 1 and type(read("bool", b"t")) is int
    assert read("bool", b"f") == 0
    assert read("timestamptz", b"2024-01-02 03:04:05+00") == "2024-01-02T03:04:05+00:00"
    assert read("numeric", b"4.99") == 4.99
    assert read("int8", b"712345678901234567") == 712345678901234567


@pytest.mark.parametrize("site", ["onlyfans", "fansly", "a_site2"])
def test_a_site_names_its_schema(site):
    assert postgres.schema_name(site) == site


@pytest.mark.parametrize("site", ["", None, "two words", "x;drop", '"quoted"', "1site"])
def test_a_schema_name_is_never_built_from_odd_text(site):
    with pytest.raises(postgres.PostgresUnavailable):
        postgres.schema_name(site)


# --- the tables ---


def sqlite_columns(tmp_path):
    path = tmp_path / "current.db"

    async def make():
        await operations.create_tables(db_path=path)
        await modify_tables(db_path=path, new_db=True)

    asyncio.run(make())
    with contextlib.closing(sqlite3.connect(path)) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {
            table: [row[1] for row in conn.execute(f"PRAGMA table_info('{table}')")]
            for table in tables
        }


def test_postgresql_has_the_tables_and_columns_sqlite_has(tmp_path):
    # a column added to SQLite needs adding to postgres.TABLES too, with the
    # step that adds it to a PostgreSQL database made before
    expected = sqlite_columns(tmp_path)
    assert set(postgres.TABLES) == set(expected)
    for table, columns in expected.items():
        assert set(postgres.TABLE_COLUMNS[table]) == set(columns), table


def test_postgresql_has_the_unique_keys_sqlite_has(tmp_path):
    # the keys are what stop a row being saved twice
    path = tmp_path / "current.db"

    async def make():
        await operations.create_tables(db_path=path)
        await modify_tables(db_path=path, new_db=True)

    asyncio.run(make())
    expected = {}
    with contextlib.closing(sqlite3.connect(path)) as conn:
        for table in postgres.TABLES:
            keys = set()
            for _, name, unique, origin, _ in conn.execute(
                f"PRAGMA index_list({table})"
            ):
                # u: a UNIQUE in the table's definition (pk is the row's id)
                if unique and origin == "u":
                    keys.add(
                        frozenset(
                            row[2] for row in conn.execute(f"PRAGMA index_info({name})")
                        )
                    )
            expected[table] = keys

    found = {
        table: {
            frozenset(part.strip() for part in line.split("(")[1].rstrip("),").split(","))
            for line in create.splitlines()
            if line.strip().startswith("UNIQUE")
        }
        for table, create in postgres.TABLES.items()
    }
    assert found == expected
    assert found["medias"] == {frozenset({"media_id", "model_id", "post_id"})}


def test_a_new_postgresql_database_has_had_every_upgrade_step(tmp_path):
    # the flags a current SQLite file has are the ones PostgreSQL starts with
    path = tmp_path / "current.db"

    async def make():
        await operations.create_tables(db_path=path)
        await modify_tables(db_path=path, new_db=True)

    asyncio.run(make())
    with contextlib.closing(sqlite3.connect(path)) as conn:
        done = {row[0] for row in conn.execute("SELECT flag_name FROM schema_flags")}
    assert done == set(ALL_FLAGS)


# the upgrade steps there were when PostgreSQL could first be used: every
# database it made has had them. A step added since belongs in
# postgres.ADDED_COLUMNS when it adds columns, so that a database made
# before gets them (a step of another kind needs its own way in, and its
# name here)
STEPS_AT_FIRST = {
    "media_hash",
    "media_model_id",
    "posts_model_id",
    "posts_pinned",
    "products_model_id",
    "other_model_id",
    "stories_model_id",
    "messages_model_id",
    "labels_model_id",
    "media_posted_at",
    "media_unlocked",
    "media_duration",
    "posts_stream",
    "posts_opened",
    "posts_is_deleted",
    "messages_is_deleted",
    "posts_purchase_type",
    "posts_mentions",
    "messages_group_id",
    "media_skip_permanent",
    "profile_username_constraint_modified",
    "stories_model_id_constraint_added",
    "labels_model_id_constraint_added",
    "posts_model_id_constraint_added",
    "others_model_id_constraint_added",
    "products_model_id_constraint_added",
    "messages_model_id_constraint_added",
    "media_post_id_constraint_added",
    "media_bool_changes",
    "media_size_skip_repaired",
}


def test_every_step_added_since_reaches_a_database_made_before():
    added = [flag for flag, _table, _columns in postgres.ADDED_COLUMNS]

    assert len(added) == len(set(added))
    assert set(added) == set(ALL_FLAGS) - STEPS_AT_FIRST
    assert STEPS_AT_FIRST <= set(ALL_FLAGS)
    for _flag, table, columns in postgres.ADDED_COLUMNS:
        for column in columns:
            assert column in postgres.TABLE_COLUMNS[table]
            # no default and no NOT NULL: adding it rewrites no row, and
            # the rows already there are simply without a value
            assert postgres.COLUMN_TYPES[table][column] in (
                "TIMESTAMPTZ",
                "TEXT",
                "BIGINT",
                "BOOLEAN",
                "NUMERIC",
            )
    assert postgres.ADDED_COLUMNS == (
        ("profiles_seen_at", "profiles", ("first_seen_at", "last_seen_at")),
        ("stories_highlight_id", "stories", ("highlight_id",)),
    )


class ColumnsCursor:
    """A cursor of a server whose tables have the columns it is told."""

    def __init__(self, columns):
        self.columns = columns
        self.asked = []
        self.found = []

    def execute(self, query, params=None):
        self.asked.append((" ".join(query.split()), params))
        self.found = []
        if "information_schema.columns" in query:
            self.found = [(column,) for column in self.columns[params[0]]]
        return self

    def fetchall(self):
        return self.found


ASK_FOR_COLUMNS = (
    "SELECT column_name FROM information_schema.columns"
    " WHERE table_schema = current_schema() AND table_name = ?",
    ["profiles"],
)
STEP_DONE = (
    "INSERT INTO schema_flags (flag_name, flag_value) VALUES (?, '1')"
    " ON CONFLICT (flag_name) DO NOTHING",
    ["profiles_seen_at"],
)
ASK_FOR_STORY_COLUMNS = (ASK_FOR_COLUMNS[0], ["stories"])
# a stories table that already has the column the stories step adds (#728)
STORIES_NOW = {"stories": postgres.TABLE_COLUMNS["stories"]}


def test_tables_made_before_get_the_columns_added_since():
    cur = ColumnsCursor({"profiles": ["id", "user_id", "username"], **STORIES_NOW})

    postgres.POSTGRES._add_columns(cur)

    assert cur.asked == [
        ASK_FOR_COLUMNS,
        ("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ", None),
        ("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ", None),
        STEP_DONE,
        ASK_FOR_STORY_COLUMNS,
    ]


def test_a_stories_table_made_before_gets_the_highlight_column():
    stories = [c for c in postgres.TABLE_COLUMNS["stories"] if c != "highlight_id"]
    cur = ColumnsCursor(
        {"profiles": postgres.TABLE_COLUMNS["profiles"], "stories": stories}
    )

    postgres.POSTGRES._add_columns(cur)

    assert cur.asked == [
        ASK_FOR_COLUMNS,
        ASK_FOR_STORY_COLUMNS,
        ("ALTER TABLE stories ADD COLUMN IF NOT EXISTS highlight_id BIGINT", None),
        (STEP_DONE[0], ["stories_highlight_id"]),
    ]


def test_tables_that_have_the_columns_are_only_asked():
    # every start after the first: nothing is changed, and nothing locked
    cur = ColumnsCursor({"profiles": postgres.TABLE_COLUMNS["profiles"], **STORIES_NOW})

    postgres.POSTGRES._add_columns(cur)

    assert cur.asked == [ASK_FOR_COLUMNS, ASK_FOR_STORY_COLUMNS]


def test_a_column_that_is_missing_alone_is_added_alone():
    cur = ColumnsCursor(
        {"profiles": ["id", "user_id", "username", "first_seen_at"], **STORIES_NOW}
    )

    postgres.POSTGRES._add_columns(cur)

    assert cur.asked == [
        ASK_FOR_COLUMNS,
        ("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ", None),
        STEP_DONE,
        ASK_FOR_STORY_COLUMNS,
    ]


class TablesCursor(ColumnsCursor):
    """A cursor of a server that has the tables it is told, as a start of
    the scraper uses one."""

    def __enter__(self):
        return self

    def __exit__(self, *error):
        return False

    def execute(self, query, params=None):
        super().execute(query, params)
        if "pg_namespace" in query:
            self.found = [(1,)]
        elif "information_schema.tables" in query:
            self.found = [(1,)] if params[0] in self.columns else []
        return self

    def executemany(self, query, rows):
        self.asked.append((" ".join(query.split()), list(rows)))


def started(monkeypatch, columns):
    """What a start asks of a server whose tables have these columns."""
    cur = TablesCursor(columns)
    engine = postgres.PostgresBackend()
    conn = SimpleNamespace(cursor=lambda: cur, commit=lambda: cur.asked.append("commit"))
    monkeypatch.setattr(engine, "connect", lambda schema, read_only, timeout: conn)
    monkeypatch.setattr(engine, "close", lambda conn: None)
    monkeypatch.setattr(engine, "_pool", lambda schema, timeout: SimpleNamespace())

    engine.create_tables(ALL_FLAGS, schema="onlyfans")

    return [asked for asked in cur.asked if "CREATE " not in asked[0]]


def test_a_start_brings_tables_made_before_up_to_date(monkeypatch):
    asked = started(
        monkeypatch,
        {
            "schema_flags": ["flag_name"],
            "profiles": ["id", "user_id", "username"],
            **STORIES_NOW,
        },
    )

    assert asked[-6:] == [
        ASK_FOR_COLUMNS,
        ("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ", None),
        ("ALTER TABLE profiles ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ", None),
        STEP_DONE,
        ASK_FOR_STORY_COLUMNS,
        # all of it kept, or none
        "commit",
    ]
    # under the lock that lets one program at a time make the tables, and
    # without marking any other step as done
    assert "pg_advisory_xact_lock" in asked[0][0]
    assert [query for query, _ in asked[:-1] if "schema_flags (" in query] == [STEP_DONE[0]]


def test_a_start_on_a_new_database_makes_the_tables_with_the_columns(monkeypatch):
    asked = started(monkeypatch, {})

    # made at today's layout, with every step marked as done: nothing to add
    assert not [query for query, _ in asked[:-1] if "ALTER TABLE" in query]
    assert ASK_FOR_COLUMNS not in asked
    assert asked[-2][1] == [(flag,) for flag in sorted(ALL_FLAGS)]
    assert "first_seen_at TIMESTAMPTZ" in postgres.TABLES["profiles"]
    assert "last_seen_at TIMESTAMPTZ" in postgres.TABLES["profiles"]


def test_sqlite_files_are_still_prepared_the_old_way(sqlite_file):
    assert wrapper.SQLITE.born_current is False

    async def start():
        await operations.table_init_create(model_id=5, username="a_creator")

    asyncio.run(start())

    with contextlib.closing(sqlite3.connect(sqlite_file)) as conn:
        assert conn.execute("SELECT model_id FROM models").fetchall() == [(5,)]
