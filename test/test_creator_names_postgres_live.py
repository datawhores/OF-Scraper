"""scripts/creator_names.py --postgres on a real PostgreSQL server (#631).

Skipped unless OFSC_TEST_POSTGRES_URL names a server the tests may use (see
test_db_postgres_live.py). Each test gives the sites schemas of its own and
drops them. The rows are brought in from files by the real import.
"""

import contextlib
import os
import sqlite3

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)

URL = os.environ.get("OFSC_TEST_POSTGRES_URL", "")
if not URL:
    pytest.skip(
        "needs a PostgreSQL server: set OFSC_TEST_POSTGRES_URL", allow_module_level=True
    )

# with a server named, a missing driver is a failure, not a skip
import psycopg  # noqa: E402,F401

from test.test_collision_recovery_postgres import write_file  # noqa: E402
from test.test_creator_names import APRIL, MARCH, MAY, creator_names  # noqa: E402
from test.test_stash_sync_postgres_live import (  # noqa: E402,F401  (the fixtures)
    bring_in,
    everything_held,
    no_url,
    pg,
    server,
)

MEDIA = [(1, 101, None, None, 0, None, None), (2, 102, None, None, 0, None, None)]


def names(db, model_id, rows):
    with contextlib.closing(sqlite3.connect(db)) as conn, conn:
        conn.executemany(
            "INSERT INTO profiles (user_id, username, first_seen_at, last_seen_at) VALUES (?, ?, ?, ?)",
            [(model_id, *row) for row in rows],
        )


@pytest.fixture
def data(tmp_path):
    """Two OnlyFans creators and a Fansly one with the first one's id, in files."""
    data = tmp_path / ".data"
    names(write_file(data / "1" / "user_data.db", 1, "undated_name", MEDIA), 1,
          [("old_name", MARCH, APRIL), ("current_name", MAY, MAY)])
    names(write_file(data / "2" / "user_data.db", 2, "zeta_name", MEDIA[:1]), 2, [])
    names(write_file(data / "1" / "fansly" / "user_data.db", 1, "fansly_name", MEDIA, site="fansly"),
          1, [("fansly_other", MARCH, MARCH)])
    return data


def run(capsys, *args):
    capsys.readouterr()
    code = creator_names.main([str(arg) for arg in args])
    said = capsys.readouterr()
    return code, said.out, said.err


def test_the_same_listing_from_a_file_and_from_the_server(data, pg, tmp_path, capsys):
    bring_in(data)

    code, from_files, _ = run(capsys, "--data-dir", data, "--all", "--csv", tmp_path / "f.csv")
    assert code == 0
    code, out, err = run(capsys, "--postgres", "--all", "--csv", tmp_path / "p.csv")

    assert code == 0, err
    assert out == from_files
    assert "folder if deleted: current_name" in out
    assert (tmp_path / "p.csv").read_text("utf-8") == (tmp_path / "f.csv").read_text("utf-8")
    _, out, _ = run(capsys, "--postgres", "--site", "fansly")
    assert "fansly_name   also known as: fansly_other (seen 2024-03-01)" in out


def test_add_writes_one_row_for_that_creator_and_site(data, pg, capsys):
    bring_in(data)
    before = everything_held(pg)
    profiles = (pg["onlyfans"], "profiles")

    # an undated name first by name would become creator 2's folder name
    code, _, err = run(capsys, "--postgres", "--add", 2, "alpha_name")
    assert code == 1 and "pass --force" in err
    assert everything_held(pg) == before

    code, out, err = run(capsys, "--postgres", "--add", 1, "newest_name", "--seen", "2024-06-01", "--force")
    assert code == 0, err
    assert out == "Added: newest_name -> 1, seen 2024-06-01T00:00:00+00:00\n"
    after = everything_held(pg)
    added = [row for row in after[profiles] if row not in before[profiles]]
    assert len(added) == 1 and added[0][1:3] == (1, "newest_name")
    assert added[0][3] == added[0][4] and added[0][3].year == 2024 and added[0][3].month == 6
    # everything else, the other creator and the other site, as it was
    assert {key: rows for key, rows in after.items() if key != profiles} == {
        key: rows for key, rows in before.items() if key != profiles
    }
    assert [row for row in after[profiles] if row != added[0]] == before[profiles]
    _, out, _ = run(capsys, "--postgres", "--find", "newest_name")
    assert "folder if deleted: newest_name" in out
