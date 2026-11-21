"""move_creator_files working on a real PostgreSQL server (#644).

Skipped unless OFSC_TEST_POSTGRES_URL names a server the tests may use (see
test_db_postgres_live.py). Each test gives the sites schemas of its own and
drops them. The `check_...` functions are the ones
test_move_creator_files_postgres.py runs against its stand-in; here the rows
are in a server, brought in by the real import. The last test is what only a
server can answer: what it does when another program changed a row
meanwhile. The files are real ones, under pytest's tmp_path.
"""

import os

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.move_creator_files as tool
import ofscraper.db.creator_rows as creator_rows

URL = os.environ.get("OFSC_TEST_POSTGRES_URL", "")
if not URL:
    pytest.skip(
        "needs a PostgreSQL server: set OFSC_TEST_POSTGRES_URL", allow_module_level=True
    )

from test.test_move_creator_files import AFTER, NEW, OLD, under  # noqa: E402
from test.test_move_creator_files_postgres import (  # noqa: E402,F401  (the fixtures)
    check_only_that_creator,
    check_same_move,
    one_creator,
    postgres_rows,
    recorded,
    three_creators,
)
from test.test_stash_sync_postgres_live import (  # noqa: E402,F401  (the fixtures)
    bring_in,
    everything_held,
    no_url,
    pg,
    server,
)


def test_the_same_rows_give_the_same_move_from_either(one_creator, pg, tmp_path):
    bring_in(tmp_path / ".data")

    check_same_move(URL, one_creator)


def test_only_that_creators_rows_and_files_are_touched(three_creators, pg, tmp_path):
    bring_in(tmp_path / ".data")

    check_only_that_creator(URL, lambda: everything_held(pg), pg["onlyfans"], three_creators)


def test_a_row_the_scraper_changed_meanwhile_stops_the_run_with_no_row_changed(
    one_creator, pg, tmp_path, monkeypatch, capsys
):
    bring_in(tmp_path / ".data")
    before = postgres_rows(URL)
    real = creator_rows.PostgresRows.change
    done = []

    def change(self, table, row_id, was, to):
        # the first file's row is changed; then, before the second one's
        # is, the scraper saves something in that second row and keeps it
        changed = real(self, table, row_id, was, to)
        if not done:
            done.append(server(f"UPDATE {pg['onlyfans']}.medias SET hash = 'saved since' WHERE filename = 'a.jpg'"))
        return changed

    with monkeypatch.context() as patch:
        patch.setattr(creator_rows.PostgresRows, "change", change)
        capsys.readouterr()
        with pytest.raises(SystemExit) as stopped:
            tool.main(["--postgres", "--creator", OLD, "--apply"])

    assert done and stopped.value.code == 1
    said = capsys.readouterr()
    # two files were moved before the server refused the second row's change
    note, error = said.err.splitlines()
    assert (said.out, note) == ("", tool.AGAIN.format(2))
    assert error.startswith(
        "Move failed: Another program changed or is using the same rows of the PostgreSQL database at "
    )
    assert "could not serialize access due to concurrent update" in error
    # no row of the run was kept: only the scraper's change is there
    after = postgres_rows(URL)
    assert after[0] == before[0][:6] + ("saved since",) + before[0][7:]
    assert after[1:] == before[1:]

    # running it again finishes it
    assert tool.on_postgres(URL, OLD, apply=True)["rows_changed"] == 4
    assert recorded(postgres_rows(URL)) == under(one_creator, NEW, *AFTER)
