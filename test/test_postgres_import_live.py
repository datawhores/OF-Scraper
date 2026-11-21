"""Bringing user_data.db files into a real PostgreSQL server (#608).

Skipped unless OFSC_TEST_POSTGRES_URL names a server the tests may use (see
test_db_postgres_live.py). Each test gives the sites schemas of its own and
drops them.
"""

import asyncio
import datetime
import os
import uuid

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.postgres_import as importer
import ofscraper.db.operations_.media as media
import ofscraper.db.operations_.messages as messages
import ofscraper.db.operations_.others as others
import ofscraper.db.operations_.posts as posts
import ofscraper.db.postgres as postgres
import ofscraper.sites as sites
from ofscraper.db.difference import ALL_FLAGS
from test.db_scenario import plain
from test.import_files import current_file, file_2023, sql, without_the_dates

URL = os.environ.get("OFSC_TEST_POSTGRES_URL", "")
if not URL:
    pytest.skip(
        "needs a PostgreSQL server: set OFSC_TEST_POSTGRES_URL", allow_module_level=True
    )

# with a server named, a missing driver is a failure, not a skip
import psycopg  # noqa: E402


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
    postgres.POSTGRES.shutdown()
    with psycopg.connect(URL, autocommit=True) as conn:
        for schema in schemas.values():
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


def run(folder, **kwargs):
    lines = []
    code = importer.run(folder, out=lines.append, **kwargs)
    return code, "\n".join(lines)


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


def library(tmp_path):
    folder = tmp_path / "data"
    current_file(folder / "111" / "user_data.db", 111)
    file_2023(folder / "222" / "user_data.db", 222, name="an_old_creator")
    current_file(folder / "Fansly" / "111" / "user_data.db", 111, site="fansly")
    return folder


def test_a_library_is_brought_in(tmp_path, pg):
    folder = library(tmp_path)

    code, said = run(folder, apply=True)

    assert code == 0, said
    assert counts(pg["onlyfans"]) == {
        "labels": 1,
        "medias": 5,
        "messages": 2,
        "models": 2,
        "others": 0,
        "posts": 4,
        "products": 0,
        "profiles": 2,
        "schema_flags": len(ALL_FLAGS),
        "stories": 1,
    }
    assert counts(pg["fansly"])["medias"] == 3
    # the values, as PostgreSQL's own types
    row = server(
        "SELECT post_id, text, price, paid, archived, pinned, created_at, model_id,"
        f" is_deleted FROM {pg['onlyfans']}.posts WHERE post_id = 10 AND model_id = 111"
    )[0]
    assert row[:2] == (10, "first\nline two\ttab \\ slash")
    assert float(row[2]) == 9.99
    assert row[3:6] == (True, True, False)
    assert row[6].isoformat() == "2024-03-01T09:30:00+00:00"
    assert row[7:] == (111, True)
    media_row = server(
        "SELECT size, downloaded, created_at, skip_permanent FROM"
        f" {pg['onlyfans']}.medias WHERE media_id = '2' AND model_id = 111"
    )[0]
    assert media_row == (None, False, None, True)
    # oldest first: the rows keep their order under their new ids
    assert [
        row[0]
        for row in server(
            f"SELECT post_id FROM {pg['onlyfans']}.posts WHERE model_id = 111 ORDER BY id"
        )
    ] == [20, 10]


def test_the_scraper_reads_what_was_brought_in(tmp_path, pg, monkeypatch):
    folder = library(tmp_path)
    code, said = run(folder, apply=True)
    assert code == 0, said

    async def read(**where):
        creator = dict(model_id=111, username="a_creator", **where)
        return plain(
            dict(
                downloaded=media.get_media_ids_downloaded_model_sync(**creator),
                pairs=media.get_media_post_ids(**creator),
                skips=await media.get_permanent_skip_media_ids(**creator),
                posts=await posts.get_all_post_ids(**creator),
                deleted=await posts.get_deleted_post_ids(**creator),
                messages=await messages.get_all_messages_ids(**creator),
                flags=others.get_schema_changes(**creator),
            )
        )

    on_postgres = asyncio.run(read())
    # the same file, brought up to date as a scan would, read as SQLite
    staged = importer.stage(folder / "111" / "user_data.db", tmp_path / "copy", 0)
    source = importer.Source(path=folder / "111" / "user_data.db", staged=staged)
    importer.upgrade(source)
    assert source.problems == []
    with monkeypatch.context() as patch:
        patch.delenv(postgres.URL_KEY)
        on_sqlite = asyncio.run(read(db_path=staged))

    assert on_postgres["downloaded"] == [1]
    assert on_postgres["skips"] == [2]
    assert on_postgres["posts"] == [10, 20]
    assert on_postgres == on_sqlite


def test_without_apply_the_server_is_left_empty(tmp_path, pg):
    code, said = run(library(tmp_path))

    assert code == 0, said
    assert "Nothing was written" in said
    assert counts(pg["onlyfans"]) == {} and counts(pg["fansly"]) == {}


def test_a_second_run_is_refused_and_changes_nothing(tmp_path, pg):
    folder = library(tmp_path)
    assert run(folder, apply=True)[0] == 0
    before = counts(pg["onlyfans"])

    code, said = run(folder, apply=True)

    assert code == 1
    assert "PostgreSQL already has rows for creator 111" in said
    assert "PostgreSQL already has rows for creator 222" in said
    assert counts(pg["onlyfans"]) == before


def test_another_creator_can_be_brought_in_later(tmp_path, pg):
    assert run(library(tmp_path), apply=True)[0] == 0
    later = tmp_path / "later"
    # a creator the scraper has already seen: its profile row is there
    current_file(later / "333" / "user_data.db", 333, name="a_third")
    sql(later / "333" / "user_data.db", "INSERT INTO models (model_id) VALUES (111)")

    code, said = run(later, apply=True)

    assert code == 0, said
    assert counts(pg["onlyfans"])["medias"] == 8
    assert counts(pg["onlyfans"])["models"] == 3


def names_and_dates(schema):
    """Each name with the moments it was seen at, in UTC."""
    utc = datetime.timezone.utc
    return [
        (name, *(moment and moment.astimezone(utc).isoformat() for moment in seen))
        for name, *seen in server(
            f"SELECT username, first_seen_at, last_seen_at FROM {schema}.profiles"
            " ORDER BY id"
        )
    ]


def test_the_dates_of_a_creators_names_are_brought_in(tmp_path, pg):
    folder = tmp_path / "data"
    path = current_file(folder / "111" / "user_data.db", 111)
    sql(
        path,
        "INSERT INTO profiles (user_id, username, first_seen_at, last_seen_at)"
        " VALUES (111, ?, ?, ?)",
        [
            ("newer_name", "2024-03-01T09:30:00+00:00", "2024-04-01T09:30:00+00:00"),
            ("half_dated", None, "2024-02-01T00:00:00+00:00"),
        ],
    )
    # a file from before the dates were kept has none to bring
    without_the_dates(current_file(folder / "222" / "user_data.db", 222, name="b_creator"))

    code, said = run(folder, apply=True)

    assert code == 0, said
    assert sorted(names_and_dates(pg["onlyfans"])) == [
        ("a_creator", None, None),
        ("b_creator", None, None),
        ("half_dated", None, "2024-02-01T00:00:00+00:00"),
        ("newer_name", "2024-03-01T09:30:00+00:00", "2024-04-01T09:30:00+00:00"),
    ]


EARLIER, EARLY, LATE, LATER = (
    "2024-01-01T00:00:00+00:00",
    "2024-02-01T00:00:00+00:00",
    "2024-06-01T00:00:00+00:00",
    "2024-07-01T00:00:00+00:00",
)


@pytest.mark.parametrize(
    "has, brought, after",
    [
        # the server has the name without dates, and the file has them
        ((None, None), (EARLY, LATE), (EARLY, LATE)),
        # a date is never emptied
        ((EARLY, LATE), (None, None), (EARLY, LATE)),
        ((None, LATE), (EARLY, None), (EARLY, LATE)),
        # the file's dates are older than the server's, then newer
        ((EARLY, LATER), (EARLIER, LATE), (EARLIER, LATER)),
        ((EARLIER, LATE), (EARLY, LATER), (EARLIER, LATER)),
        # wider, then narrower
        ((EARLY, LATE), (EARLIER, LATER), (EARLIER, LATER)),
        ((EARLIER, LATER), (EARLY, LATE), (EARLIER, LATER)),
        ((EARLY, LATE), (EARLY, LATE), (EARLY, LATE)),
    ],
)
def test_a_name_the_server_already_has_gets_the_dates_of_both(
    tmp_path, pg, has, brought, after
):
    schema = pg["onlyfans"]
    assert run(library(tmp_path), apply=True)[0] == 0
    # the scraper has started on the creator here, and saved nothing yet
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute(
            f"INSERT INTO {schema}.profiles"
            " (user_id, username, first_seen_at, last_seen_at)"
            " VALUES (333, 'a_third', %s, %s)",
            list(has),
        )
    its_row = f"SELECT id, user_id FROM {schema}.profiles WHERE username = 'a_third'"
    # where the server keeps the row: it moves when the row is written again
    its_place = f"SELECT ctid::text FROM {schema}.profiles WHERE username = 'a_third'"
    held, place = server(its_row), server(its_place)
    names = counts(schema)["profiles"]
    later = tmp_path / "later"
    path = current_file(later / "333" / "user_data.db", 333, name="a_third")
    sql(path, "UPDATE profiles SET first_seen_at = ?, last_seen_at = ?", [brought])
    sql(
        path,
        "INSERT INTO profiles (user_id, username, last_seen_at)"
        f" VALUES (333, 'another_name', '{EARLIER}')",
    )

    code, said = run(later, apply=True)

    assert code == 0, said
    assert names_and_dates(schema)[-2:] == [
        ("a_third", *after),
        ("another_name", None, EARLIER),
    ]
    # the row it had, and one row more for the name that is new
    assert server(its_row) == held
    assert counts(schema)["profiles"] == names + 1
    # and a row whose dates stay as they are isn't written at all
    assert (server(its_place) == place) is (after == has)
    # a date that was widened is no row added: the count is the file's
    # posts, media and the like, as for any file
    assert "onlyfans: 8 rows added." in said


def test_tables_made_before_the_dates_get_the_columns_when_a_file_is_brought_in(
    tmp_path, pg
):
    schema = pg["onlyfans"]
    first = tmp_path / "first"
    current_file(first / "111" / "user_data.db", 111)
    assert run(first, apply=True)[0] == 0
    postgres.POSTGRES.shutdown()
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute(f"ALTER TABLE {schema}.profiles DROP COLUMN first_seen_at")
        conn.execute(f"ALTER TABLE {schema}.profiles DROP COLUMN last_seen_at")
        conn.execute(
            f"DELETE FROM {schema}.schema_flags WHERE flag_name = 'profiles_seen_at'"
        )
    later = tmp_path / "later"
    path = current_file(later / "333" / "user_data.db", 333, name="a_third")
    sql(
        path,
        "UPDATE profiles SET first_seen_at = '2024-03-01T09:30:00+00:00',"
        " last_seen_at = '2024-04-01T09:30:00+00:00'",
    )

    code, said = run(later, apply=True)

    assert code == 0, said
    assert names_and_dates(schema) == [
        ("a_creator", None, None),
        ("a_third", "2024-03-01T09:30:00+00:00", "2024-04-01T09:30:00+00:00"),
    ]
    assert counts(schema)["schema_flags"] == len(ALL_FLAGS)


def test_a_bad_file_leaves_the_server_as_it_was(tmp_path, pg):
    folder = library(tmp_path)
    sql(folder / "111" / "user_data.db", "UPDATE posts SET paid = 2 WHERE post_id = 10")

    code, said = run(folder, apply=True)

    assert code == 1
    assert "posts row 2, paid: 2 is neither yes (1) nor no (0)" in said
    assert counts(pg["onlyfans"]) == {}


def test_a_failure_part_way_keeps_nothing_and_a_rerun_works(tmp_path, pg, monkeypatch):
    folder = library(tmp_path)
    write = importer.Target.write

    stories = []

    def fails_late(self, site, table, columns, rows):
        # in the second file: the first is fully written by then
        if table == "stories":
            stories.append(site)
            if len(stories) == 2:
                raise importer.Refused("stopped for the test")
        return write(self, site, table, columns, rows)

    with monkeypatch.context() as patch:
        patch.setattr(importer.Target, "write", fails_late)
        code, said = run(folder, apply=True)

    assert code == 1
    assert "Nothing was written. stopped for the test" in said
    # the tables were made, and hold nothing
    assert counts(pg["onlyfans"])["medias"] == 0
    assert counts(pg["onlyfans"])["posts"] == 0
    assert counts(pg["onlyfans"])["profiles"] == 0

    code, said = run(folder, apply=True)

    assert code == 0, said
    assert counts(pg["onlyfans"])["medias"] == 5
