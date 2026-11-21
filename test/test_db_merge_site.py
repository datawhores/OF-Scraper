"""Merge DB's keeps which site a database is for (#615).

A Fansly database records its site; an OnlyFans one records nothing. The
merged database gets the record of what was merged into it, and a database
for the other site is refused: the rows don't say which site they are from.

Each test builds real SQLite databases in a temporary folder with the app's
own create, migration and write code, then runs the merge.
"""

import asyncio
import contextlib
import sqlite3

import pytest

import ofscraper.db.merge as merge
import ofscraper.db.operations as operations
import ofscraper.sites as sites
from ofscraper.db.operations_.media import write_media_table_transition
from ofscraper.db.operations_.others import get_site_flag, write_site_flag
from ofscraper.db.operations_.profile import write_models_table, write_profile_table
from ofscraper.db.transition import modify_tables

MODEL_ID = 12345
# as long as a Fansly creator's id
FANSLY_ID = 285000000000000001
USERNAME = "dbmodel"
# a Fansly database merged by a version that didn't keep the site record
UNRECORDED_FANSLY = "fansly, not recorded"


def media(media_id, model_id=MODEL_ID):
    return {
        "media_id": media_id,
        "post_id": 1001,
        "link": f"https://example.invalid/{media_id}.jpg",
        "directory": None,
        "filename": None,
        "size": None,
        "api_type": "Posts",
        "media_type": "Images",
        "preview": 0,
        "linked": None,
        "downloaded": 0,
        "created_at": "2024-01-03T03:04:05+00:00",
        "posted_at": "2024-01-03T03:04:06+00:00",
        "hash": None,
        "model_id": model_id,
        "duration": None,
        "unlocked": 1,
    }


async def make_db(db, site, media_ids):
    model_id = MODEL_ID if site == sites.ONLYFANS else FANSLY_ID
    db.parent.mkdir(parents=True, exist_ok=True)
    await operations.create_tables(db_path=db)
    await write_profile_table(model_id=model_id, username=USERNAME, db_path=db)
    await write_models_table(model_id=model_id, db_path=db)
    await modify_tables(db_path=db)
    if site == sites.FANSLY:
        # as a scan of a creator on that site records it
        await write_site_flag(site, db_path=db)
    await write_media_table_transition(
        [media(i, model_id) for i in media_ids], db_path=db
    )


def media_ids(db):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return sorted(row[0] for row in conn.execute("SELECT media_id FROM medias"))


@pytest.fixture
def merged(tmp_path, monkeypatch):
    """Merge sources (their sites, in order) into a target that may exist.
    Returns the target, and the reasons the refused sources were given."""

    # a refused database is logged with the app's own logger method
    monkeypatch.setattr(merge.log, "traceback_", lambda *args: None, raising=False)

    def run(sources, target=None):
        new_db = tmp_path / "new" / "user_data.db"
        paths = [tmp_path / "old" / f"db{i}" / "user_data.db" for i in range(len(sources))]
        # the merge reads databases in folder-walk order; fix the order here
        monkeypatch.setattr(merge.paths_db, "get_all_db", lambda folder: list(paths))

        async def go():
            for number, (path, site) in enumerate(zip(paths, sources)):
                await make_db(path, site, [number + 1])
            if target is not None:
                site, ids = target
                await make_db(new_db, site, ids)
            return await merge.MergeDatabase()(tmp_path / "old", new_db)

        failures, _, _ = asyncio.run(go())
        refused = {
            paths.index(path): str(failure["reason"]) for path, failure in failures
        }
        return new_db, refused

    return run


def test_fansly_databases_make_a_fansly_database(merged):
    new_db, refused = merged([sites.FANSLY, sites.FANSLY])

    assert refused == {}
    assert get_site_flag(db_path=new_db) == sites.FANSLY
    assert media_ids(new_db) == [1, 2]


def test_onlyfans_databases_record_no_site_as_before(merged):
    new_db, refused = merged([sites.ONLYFANS, sites.ONLYFANS])

    assert refused == {}
    assert get_site_flag(db_path=new_db) is None
    assert media_ids(new_db) == [1, 2]


def test_a_fansly_database_is_not_merged_into_an_onlyfans_one(merged):
    new_db, refused = merged([sites.FANSLY], target=(sites.ONLYFANS, [50]))

    assert refused == {
        0: "It is for Fansly, and the merged database is for Onlyfans"
    }
    assert get_site_flag(db_path=new_db) is None
    assert media_ids(new_db) == [50]


def test_an_onlyfans_database_is_not_merged_into_a_fansly_one(merged):
    new_db, refused = merged(
        [sites.ONLYFANS, sites.FANSLY], target=(sites.FANSLY, [50])
    )

    assert refused == {
        0: "It is for Onlyfans, and the merged database is for Fansly"
    }
    assert get_site_flag(db_path=new_db) == sites.FANSLY
    assert media_ids(new_db) == [2, 50]


def test_a_new_database_is_for_the_site_of_the_first_one_merged(merged):
    new_db, refused = merged([sites.FANSLY, sites.ONLYFANS, sites.FANSLY])

    assert list(refused) == [1]
    assert get_site_flag(db_path=new_db) == sites.FANSLY
    assert media_ids(new_db) == [1, 3]


def test_an_empty_fansly_database_stays_fansly(merged):
    # a creator scanned on Fansly before anything was saved
    new_db, refused = merged([sites.ONLYFANS, sites.FANSLY], target=(sites.FANSLY, []))

    assert list(refused) == [0]
    assert get_site_flag(db_path=new_db) == sites.FANSLY
    assert media_ids(new_db) == [2]


def test_a_fansly_database_merged_by_an_older_version_takes_fansly_databases(merged):
    # it has rows and no site record; its creators' ids say whose it is
    new_db, refused = merged(
        [sites.FANSLY, sites.ONLYFANS], target=(UNRECORDED_FANSLY, [50])
    )

    assert refused == {
        1: "It is for Onlyfans, and the merged database is for Fansly"
    }
    assert media_ids(new_db) == [1, 50]
    # and it has the record from now on
    assert get_site_flag(db_path=new_db) == sites.FANSLY


def test_a_fansly_database_merged_by_an_older_version_is_merged_as_fansly(merged):
    new_db, refused = merged([UNRECORDED_FANSLY], target=(sites.ONLYFANS, [50]))

    assert list(refused) == [0]
    assert media_ids(new_db) == [50]


def test_a_new_database_takes_the_site_of_an_unrecorded_fansly_one(merged):
    new_db, refused = merged([UNRECORDED_FANSLY, sites.FANSLY, sites.ONLYFANS])

    assert list(refused) == [2]
    assert get_site_flag(db_path=new_db) == sites.FANSLY


def test_a_merge_that_fails_before_it_adds_anything_leaves_the_database_open(
    merged, monkeypatch
):
    real = merge.MergeDatabase.merge_individual

    async def first_fails(self, db_path):
        if db_path.parent.name == "db0":
            raise OSError("the first database can't be read")
        await real(self, db_path)

    monkeypatch.setattr(merge.MergeDatabase, "merge_individual", first_fails)

    new_db, refused = merged([sites.FANSLY, sites.ONLYFANS, sites.ONLYFANS])

    assert list(refused) == [0]
    assert get_site_flag(db_path=new_db) is None
    assert media_ids(new_db) == [2, 3]


def test_a_merge_that_fails_part_way_still_decides_the_site(merged, monkeypatch):
    real = merge.MergeDatabase.merge_individual

    async def first_fails_late(self, db_path):
        await real(self, db_path)
        if db_path.parent.name == "db0":
            raise OSError("the first database can't be read to its end")

    monkeypatch.setattr(merge.MergeDatabase, "merge_individual", first_fails_late)

    new_db, refused = merged([sites.FANSLY, sites.ONLYFANS, sites.FANSLY])

    assert list(refused) == [0, 1]
    assert get_site_flag(db_path=new_db) == sites.FANSLY
    assert media_ids(new_db) == [1, 3]


def test_a_database_with_only_a_creator_in_it_is_not_open_to_the_other_site(merged):
    new_db, refused = merged([sites.FANSLY], target=(sites.ONLYFANS, []))

    assert refused == {
        0: "It is for Fansly, and the merged database is for Onlyfans"
    }
    assert get_site_flag(db_path=new_db) is None
    assert media_ids(new_db) == []
