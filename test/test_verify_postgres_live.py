"""ofscraper verify on a real PostgreSQL server.

Skipped unless OFSC_TEST_POSTGRES_URL names a server the tests may use (see
test_db_postgres_live.py). check_same_findings is the one
test_verify_postgres.py runs against its stand-in; here the rows are in a
server, brought in by the real import.
"""

import os

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)

URL = os.environ.get("OFSC_TEST_POSTGRES_URL", "")
if not URL:
    pytest.skip(
        "needs a PostgreSQL server: set OFSC_TEST_POSTGRES_URL", allow_module_level=True
    )

from test.test_verify import library  # noqa: E402,F401  (the fixture)
from test.test_verify_postgres import check_same_findings  # noqa: E402
from test.test_stash_sync_postgres_live import (  # noqa: E402,F401  (the fixtures)
    bring_in,
    no_url,
    pg,
    server,
)


def test_the_same_rows_give_the_same_findings_from_either(library, pg, tmp_path):  # noqa: F811
    db, _ = library
    bring_in(tmp_path / ".data")
    check_same_findings(URL, db)


def test_apply_and_undo(library, pg, tmp_path):  # noqa: F811
    from test.test_verify_postgres import check_apply_and_undo

    bring_in(tmp_path / ".data")
    check_apply_and_undo(URL, library, tmp_path)
