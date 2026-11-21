"""Writing what a real PostgreSQL server holds back to user_data.db files
(#632).

Skipped unless OFSC_TEST_POSTGRES_URL names a server the tests may use (see
test_db_postgres_live.py). Each test gives the sites schemas of its own and
drops them.
"""

import asyncio
import os
import uuid

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.postgres_export as exporter
import ofscraper.commands.postgres_import as importer
import ofscraper.db.operations_.others as others
import ofscraper.db.postgres as postgres
import ofscraper.sites as sites
from ofscraper.db.difference import ALL_FLAGS
from test.db_scenario import ONE, TWO, check, scenario
from test.import_files import current_file, file_2023, sql
from test.test_postgres_export import (
    TAKEN_ON_THE_WAY_IN,
    canonical,
    dump,
    each_creator_has_their_rows,
    files,
    layout,
    moments,
)

URL = os.environ.get("OFSC_TEST_POSTGRES_URL", "")
if not URL:
    pytest.skip(
        "needs a PostgreSQL server: set OFSC_TEST_POSTGRES_URL", allow_module_level=True
    )

# with a server named, a missing driver is a failure, not a skip
import psycopg  # noqa: E402

DATABASE = exporter.DATABASE


def emptied(schemas):
    """Drop the schemas, and the engine's connections to them."""
    postgres.POSTGRES.shutdown()
    with psycopg.connect(URL, autocommit=True) as conn:
        for schema in schemas.values():
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


@pytest.fixture
def pg(monkeypatch):
    """PostgreSQL is configured, and each site's schema is this test's own:
    {site: schema}."""
    tag = uuid.uuid4().hex[:12]
    schemas = {site: f"t_{tag}_{site}" for site in sites.SITES}
    real = postgres.schema_name
    monkeypatch.setenv(postgres.URL_KEY, URL)
    monkeypatch.setattr(
        postgres, "schema_name", lambda site: schemas.get(site) or real(site)
    )
    yield schemas
    emptied(schemas)


def run(folder, **kwargs):
    lines = []
    code = exporter.run(folder, out=lines.append, **kwargs)
    return code, "\n".join(lines)


def bring_in(folder):
    lines = []
    code = importer.run(folder, apply=True, out=lines.append)
    assert code == 0, "\n".join(lines)


def server(statement):
    with psycopg.connect(URL) as conn:
        return conn.execute(statement).fetchall()


def counts(schema):
    there = [
        row[0]
        for row in server(
            "SELECT table_name FROM information_schema.tables"
            f" WHERE table_schema = '{schema}' ORDER BY table_name"
        )
    ]
    return {
        table: server(f"SELECT COUNT(*) FROM {schema}.{table}")[0][0] for table in there
    }


def carried(path, owner=None):
    """What the import reads from a file, with every date as its moment."""
    source = importer.Source(path=path, staged=path, owner=owner)
    found = {}

    def keep(table, columns, rows):
        found["onlyfans", table] = [dict(zip(columns, row)) for row in rows]

    importer.read(source, keep)
    assert source.problems == []
    return moments(found)


def library(tmp_path):
    folder = tmp_path / "data"
    canonical(current_file(folder / "111" / DATABASE, 111))
    file_2023(folder / "222" / DATABASE, 222, name="an_old_creator")
    return folder


def test_a_library_goes_in_and_comes_back_out(tmp_path, pg):
    folder = library(tmp_path)
    bring_in(folder)
    held = counts(pg["onlyfans"])
    out = tmp_path / "out"

    code, said = run(out, apply=True)

    assert code == 0, said
    assert "onlyfans: 2 files written" in said
    assert files(out) == [f"111/{DATABASE}", f"222/{DATABASE}"]
    # a file the scraper wrote comes back row for row: every table, every
    # value and its type, each row's own id too
    assert dump(out / "111" / DATABASE) == dump(folder / "111" / DATABASE)
    assert layout(out / "111" / DATABASE) == layout(folder / "111" / DATABASE)
    # an old file comes back as its copy, brought up to date, was read
    staged = importer.stage(folder / "222" / DATABASE, tmp_path / "copy", 0)
    old = importer.Source(path=folder / "222" / DATABASE, staged=staged)
    importer.upgrade(old)
    assert old.problems == []
    assert carried(out / "222" / DATABASE) == carried(staged, owner=old.owner)
    assert others.get_schema_changes(db_path=out / "222" / DATABASE) == set(ALL_FLAGS)
    # PostgreSQL was only read
    assert counts(pg["onlyfans"]) == held


def test_a_second_trip_changes_nothing(tmp_path, pg):
    # values the import reads its own way: a date without an offset, a date
    # as a number of seconds, nothing where a date would be
    folder = tmp_path / "data"
    current_file(folder / "111" / DATABASE, 111)
    file_2023(folder / "222" / DATABASE, 222, name="an_old_creator")
    bring_in(folder)
    first = tmp_path / "first"
    code, said = run(first, apply=True)
    assert code == 0, said

    emptied(pg)
    bring_in(first)
    second = tmp_path / "second"
    code, said = run(second, apply=True)

    assert code == 0, said
    assert files(second) == files(first) == [f"111/{DATABASE}", f"222/{DATABASE}"]
    for name in files(first):
        assert dump(second / name) == dump(first / name)
        assert layout(second / name) == layout(first / name)


def test_what_a_scan_saved_comes_out_as_the_scraper_reads_it(tmp_path, pg):
    # two creators, saved through the functions a scan uses
    on_postgres = asyncio.run(scenario())
    check(on_postgres)
    out = tmp_path / "out"

    code, said = run(out, apply=True)

    assert code == 0, said
    assert files(out) == [f"{ONE}/{DATABASE}", f"{TWO}/{DATABASE}"]
    each_creator_has_their_rows(out, on_postgres)


def test_without_apply_nothing_is_written(tmp_path, pg):
    bring_in(library(tmp_path))
    held = counts(pg["onlyfans"])
    out = tmp_path / "out"

    code, said = run(out)

    assert code == 0, said
    assert "onlyfans: 2 creators" in said
    assert "medias             5 rows" in said
    assert "Nothing was written. Run again with --apply to write 2 files" in said
    assert not out.exists()
    assert counts(pg["onlyfans"]) == held


def test_a_file_that_is_already_there_is_left_and_another_folder_gets_it_out(
    tmp_path, pg
):
    bring_in(library(tmp_path))
    out = tmp_path / "out"
    theirs = out / "111" / DATABASE
    theirs.parent.mkdir(parents=True)
    theirs.write_bytes(b"theirs")

    code, said = run(out, apply=True)

    assert code == 1
    assert exporter.ALREADY_THERE in said
    assert theirs.read_bytes() == b"theirs"
    assert files(out) == [f"111/{DATABASE}", f"222/{DATABASE}"]

    code, said = run(tmp_path / "elsewhere", apply=True)

    assert code == 0, said
    assert dump(tmp_path / "elsewhere" / "222" / DATABASE) == dump(out / "222" / DATABASE)


@pytest.mark.parametrize("row, why", TAKEN_ON_THE_WAY_IN)
def test_a_value_the_import_took_can_stop_the_file_on_the_way_back(
    tmp_path, pg, row, why
):
    folder = tmp_path / "data"
    sql(current_file(folder / "111" / DATABASE, 111), row)
    bring_in(folder)
    out = tmp_path / "out"

    code, said = run(out, apply=True)

    # the value, and that PostgreSQL is where it has to be changed
    assert code == 1
    assert f"    - {why}\n    - {exporter.IN_POSTGRESQL}" in said, said
    assert list(out.iterdir()) == []


def test_each_site_is_written_by_a_run_of_its_own(tmp_path, pg):
    folder = tmp_path / "data"
    current_file(folder / "111" / DATABASE, 111)
    current_file(folder / "Fansly" / "111" / DATABASE, 111, site="fansly")
    bring_in(folder)
    out = tmp_path / "out"

    code, said = run(out, apply=True)
    assert code == 2
    assert "--site" in said
    assert not out.exists()

    assert run(out / "of", apply=True, site="onlyfans")[0] == 0
    assert run(out / "fansly", apply=True, site="fansly")[0] == 0
    assert files(out) == [f"fansly/111/{DATABASE}", f"of/111/{DATABASE}"]
    assert others.get_site_flag(db_path=out / "of" / "111" / DATABASE) is None
    assert others.get_site_flag(db_path=out / "fansly" / "111" / DATABASE) == "fansly"


def test_the_database_is_read_as_it_was_at_one_moment(tmp_path, pg):
    bring_in(library(tmp_path))
    database = exporter.Database()
    database.open()
    try:
        before = database.held("onlyfans")
        assert set(before) == {111, 222}
        assert before[111]["medias"] == 3
        # a scraper saves a creator while the files are being written
        with psycopg.connect(URL, autocommit=True) as conn:
            conn.execute(f"INSERT INTO {pg['onlyfans']}.models (model_id) VALUES (999)")
        assert database.held("onlyfans") == before
        assert database.flags("onlyfans") == set(ALL_FLAGS)
        assert [
            tuple(row)
            for row in database.rows("onlyfans", "profiles", ["user_id", "username"], 222)
        ] == [(222, "an_old_creator")]
        # and nothing can be written through the export's connection
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            with database.conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {pg['onlyfans']}.models (model_id) VALUES (998)"
                )
    finally:
        database.close()
    assert server(f"SELECT model_id FROM {pg['onlyfans']}.models ORDER BY model_id") == [
        (111,),
        (222,),
        (999,),
    ]
