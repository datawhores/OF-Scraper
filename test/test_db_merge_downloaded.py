"""Merge DB's keeps a media item downloaded if any merged database has it
downloaded (#296).

Each test builds real SQLite databases in a temporary folder with the app's
own create, migration and write code, then runs the merge.
"""

import asyncio
import contextlib
import sqlite3

import pytest

import ofscraper.db.merge as merge
import ofscraper.db.operations as operations
from ofscraper.db.operations_.media import write_media_table_transition
from ofscraper.db.operations_.profile import write_models_table, write_profile_table
from ofscraper.db.transition import modify_tables

MODEL_ID = 12345
USERNAME = "dbmodel"
MEDIA_ID = 1201

DOWNLOAD_COLS = ["media_id", "directory", "filename", "size", "downloaded", "hash"]


def media(media_id=MEDIA_ID, post_id=1001, directory=None, filename=None, size=None,
          downloaded=0, hash=None):
    return {
        "media_id": media_id,
        "post_id": post_id,
        "link": f"https://example.invalid/{media_id}.jpg",
        "directory": directory,
        "filename": filename,
        "size": size,
        "api_type": "Posts",
        "media_type": "Images",
        "preview": 0,
        "linked": None,
        "downloaded": downloaded,
        "created_at": "2024-01-03T03:04:05+00:00",
        "posted_at": "2024-01-03T03:04:06+00:00",
        "hash": hash,
        "model_id": MODEL_ID,
        "duration": None,
        "unlocked": 1,
    }


NOT_DOWNLOADED = media()
DOWNLOADED_B = media(directory="/dl/b", filename="b.jpg", size=200, downloaded=1,
                     hash="hash-b")
DOWNLOADED_C = media(directory="/dl/c", filename="c.jpg", size=300, downloaded=1,
                     hash="hash-c")
EXPECTED_B = [(MEDIA_ID, "/dl/b", "b.jpg", 200, 1, "hash-b")]


async def make_db(db, medias):
    db.parent.mkdir(parents=True, exist_ok=True)
    await operations.create_tables(db_path=db)
    await write_profile_table(model_id=MODEL_ID, username=USERNAME, db_path=db)
    await write_models_table(model_id=MODEL_ID, db_path=db)
    await modify_tables(db_path=db)
    await write_media_table_transition(medias, db_path=db)


def download_rows(db):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return sorted(
            conn.execute(f"SELECT {','.join(DOWNLOAD_COLS)} FROM medias").fetchall()
        )


@pytest.fixture
def merge_dbs(tmp_path, monkeypatch):
    """Merge sources, in the given order, into a target that may hold rows."""

    def fail(e):
        raise e if isinstance(e, BaseException) else AssertionError(e)

    monkeypatch.setattr(merge.log, "traceback_", fail, raising=False)

    def run(sources, target=None, name="run"):
        root = tmp_path / name
        new_db = root / "new" / "user_data.db"
        paths = [root / "old" / f"db{i}" / "user_data.db" for i in range(len(sources))]
        # the merge reads databases in folder-walk order; fix the order here
        monkeypatch.setattr(merge.paths_db, "get_all_db", lambda folder: list(paths))

        async def go():
            for path, medias in zip(paths, sources):
                await make_db(path, medias)
            if target is not None:
                await make_db(new_db, target)
            return await merge.MergeDatabase()(root / "old", new_db)

        failures, _, _ = asyncio.run(go())
        assert failures == []
        return download_rows(new_db)

    return run


def test_downloaded_copy_in_a_later_database_is_kept(merge_dbs):
    only_first = media(media_id=1301, post_id=1003)
    only_second = media(media_id=1302, post_id=1004, directory="/dl/x",
                        filename="x.jpg", size=5, downloaded=1, hash="hash-x")
    result = merge_dbs([[NOT_DOWNLOADED, only_first], [DOWNLOADED_B, only_second]])
    assert result == EXPECTED_B + [
        (1301, None, None, None, 0, None),
        (1302, "/dl/x", "x.jpg", 5, 1, "hash-x"),
    ]


def test_merge_result_does_not_depend_on_source_order(merge_dbs):
    forward = merge_dbs([[NOT_DOWNLOADED], [DOWNLOADED_B]], name="forward")
    backward = merge_dbs([[DOWNLOADED_B], [NOT_DOWNLOADED]], name="backward")
    assert forward == backward == EXPECTED_B


def test_target_row_not_downloaded_is_updated(merge_dbs):
    assert merge_dbs([[DOWNLOADED_B]], target=[NOT_DOWNLOADED]) == EXPECTED_B


def test_first_downloaded_copy_is_kept(merge_dbs):
    assert merge_dbs([[NOT_DOWNLOADED], [DOWNLOADED_B], [DOWNLOADED_C]]) == EXPECTED_B
