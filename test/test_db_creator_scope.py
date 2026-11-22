"""A read that decides what a creator already has counts only that creator's
rows (#608).

One database can hold several creators: a merged database, or a `metadata`
folder that doesn't name the creator. These reads had no creator in them, so
one creator's rows answered for another: a post or media the other creator
already had was never saved for this one, and removing duplicate files by
hash could delete the other creator's file.

Each test builds a real SQLite database with the app's own create and
migration code, and puts two creators' rows in it.
"""

import asyncio
import contextlib
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.db.operations as operations
import ofscraper.db.operations_.media as media
import ofscraper.db.operations_.messages as messages
import ofscraper.db.operations_.posts as posts
import ofscraper.db.operations_.stories as stories
import ofscraper.utils.hash as hash_
import ofscraper.utils.settings as settings
from ofscraper.db.transition import modify_tables

ONE, TWO = 111, 222
DATE = "2024-01-03T03:04:05+00:00"


def execute(db, sql, rows):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.executemany(sql, rows)
        conn.commit()


def media_rows(db):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return sorted(
            conn.execute("SELECT media_id, post_id, model_id FROM medias").fetchall()
        )


@pytest.fixture
def db(tmp_path):
    """Two creators in one database. Post 10 and media 1 belong to both."""
    path = tmp_path / "user_data.db"

    async def make():
        await operations.create_tables(db_path=path)
        await modify_tables(db_path=path, new_db=True)

    asyncio.run(make())
    for table in ("posts", "messages", "stories"):
        execute(
            path,
            f"INSERT INTO {table} (post_id, model_id) VALUES (?, ?)",
            [(10, ONE), (11, ONE), (10, TWO), (22, TWO)],
        )
    execute(
        path,
        "INSERT INTO medias (media_id, post_id, model_id, downloaded, directory,"
        " filename, hash, size, media_type) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (1, 10, ONE, 1, "/one", "/one/a.jpg", "same", 5, "Images"),
            (2, 11, ONE, 1, "/one", "/one/b.jpg", "other", 5, "Images"),
            (1, 10, TWO, 1, "/two", "/two/a.jpg", "same", 5, "Images"),
            (3, 22, TWO, 0, None, None, None, None, "Videos"),
        ],
    )
    return path


@pytest.mark.parametrize(
    "read",
    [posts.get_all_post_ids, messages.get_all_messages_ids, stories.get_all_stories_ids],
    ids=["posts", "messages", "stories"],
)
def test_the_ids_a_creator_has_are_its_own(db, read):
    assert sorted(asyncio.run(read(model_id=ONE, db_path=db))) == [10, 11]
    assert sorted(asyncio.run(read(model_id=TWO, db_path=db))) == [10, 22]


def test_the_media_a_creator_has_is_its_own(db):
    assert sorted(asyncio.run(media.get_media_ids(model_id=ONE, db_path=db))) == [1, 2]
    assert sorted(asyncio.run(media.get_media_ids(model_id=TWO, db_path=db))) == [1, 3]
    assert sorted(media.get_media_post_ids(model_id=ONE, db_path=db)) == [
        (1, 10),
        (2, 11),
    ]
    assert sorted(media.get_media_post_ids(model_id=TWO, db_path=db)) == [
        (1, 10),
        (3, 22),
    ]


def test_the_downloaded_files_of_a_creator_are_its_own(db):
    # the check table opens the folder of the file it gets here (#424)
    assert media.get_media_post_files_downloaded(model_id=TWO, db_path=db) == {
        (1, 10): ("/two", "/two/a.jpg")
    }
    assert media.get_media_post_files_downloaded(
        model_id=ONE, db_path=db, media_id=1
    ) == {(1, 10): ("/one", "/one/a.jpg")}


def in_running_loop(read, **kwargs):
    """read(**kwargs) called from a coroutine, as the GUI calls it: a plain
    function inside a running event loop, which can't await."""

    async def call():
        return read(**kwargs)

    return asyncio.run(call())


def test_the_post_prices_and_texts_of_a_creator_are_its_own(db):
    # the GUI's table shows them beside get_all_medias_sync's rows
    for table, price in (("posts", 1), ("messages", 2), ("stories", 3)):
        execute(
            db,
            f"UPDATE {table} SET price=?, text=? WHERE post_id=? AND model_id=?",
            [
                (price, f"{table} {post} {who}", post, who)
                for post, who in ((10, ONE), (11, ONE), (10, TWO), (22, TWO))
            ],
        )
    execute(db, "INSERT INTO messages (post_id, model_id) VALUES (?, ?)", [(33, ONE)])

    info = in_running_loop(
        media.get_post_info, model_id=ONE, db_path=db, read_only=True
    )
    # a post, a message and a story with the same id: the post's is kept
    assert info == {
        10: {"price": 1, "text": f"posts 10 {ONE}"},
        11: {"price": 1, "text": f"posts 11 {ONE}"},
        33: {"price": None, "text": None},
    }
    assert in_running_loop(media.get_post_info, model_id=TWO, db_path=db) == {
        10: {"price": 1, "text": f"posts 10 {TWO}"},
        22: {"price": 1, "text": f"posts 22 {TWO}"},
    }


def test_the_media_rows_a_creator_has_are_its_own_without_awaiting(db):
    # get_all_medias' rows, for the GUI, which can't await
    for who in (ONE, TWO):
        rows = in_running_loop(
            media.get_all_medias_sync, model_id=who, db_path=db, read_only=True
        )
        assert rows == asyncio.run(media.get_all_medias(model_id=who, db_path=db))
        assert {row["model_id"] for row in rows} == {who}
    assert [
        (row["media_id"], row["post_id"])
        for row in in_running_loop(media.get_all_medias_sync, model_id=TWO, db_path=db)
    ] == [(1, 10), (3, 22)]


def test_a_read_without_a_creator_is_the_whole_database(db):
    # tools that read a database by its path (merge, the tests) give no creator
    assert sorted(asyncio.run(posts.get_all_post_ids(db_path=db))) == [10, 10, 11, 22]
    assert len(media.get_media_post_ids(db_path=db)) == 4
    assert len(media.get_media_post_files_downloaded(db_path=db)) == 2


def test_across_all_models_still_reads_every_creator(db):
    # "unique media across all models" means the whole database, as before
    assert media.get_media_ids_downloaded(model_id=TWO, db_path=db) == {1, 2}
    assert sorted(media.get_media_post_ids_downloaded(model_id=TWO, db_path=db)) == [
        (1, 10),
        (1, 10),
        (2, 11),
    ]


def test_a_table_from_before_model_id_is_not_filtered(tmp_path):
    # such a table holds one creator's rows, and has no column to filter on
    path = tmp_path / "user_data.db"
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, post_id INTEGER)")
        conn.execute("INSERT INTO posts (post_id) VALUES (10)")
        conn.commit()
    assert asyncio.run(
        posts.get_all_post_ids(model_id=ONE, db_path=path, read_only=True)
    ) == [10]


def test_a_creator_given_as_text_reads_the_same_rows(db):
    # the check commands and manual mode pass the id as text
    assert sorted(asyncio.run(posts.get_all_post_ids(model_id=str(TWO), db_path=db))) == [
        10,
        22,
    ]
    assert sorted(media.get_media_post_ids(model_id=str(TWO), db_path=db)) == [
        (1, 10),
        (3, 22),
    ]


def test_media_reads_of_a_table_from_before_model_id_are_not_filtered(tmp_path):
    path = tmp_path / "user_data.db"
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute(
            "CREATE TABLE medias (id INTEGER PRIMARY KEY, media_id INTEGER,"
            " post_id INTEGER, downloaded INTEGER, directory VARCHAR,"
            " filename VARCHAR, hash VARCHAR, size INTEGER, media_type VARCHAR)"
        )
        conn.executemany(
            "INSERT INTO medias (media_id, post_id, downloaded, directory,"
            " filename, hash, size) VALUES (?,?,1,'/d',?,'same',5)",
            [(1, 10, "/d/a.jpg"), (2, 10, "/d/b.jpg")],
        )
        conn.commit()
    read = dict(model_id=ONE, db_path=path, read_only=True)

    assert sorted(asyncio.run(media.get_media_ids(**read))) == [1, 2]
    assert sorted(media.get_media_post_ids(**read)) == [(1, 10), (2, 10)]
    assert len(media.get_media_post_files_downloaded(**read)) == 2


@pytest.fixture
def no_creator_rows(db):
    """Rows an upgrade left without a creator: it fills model_id in from the
    database's one profile, and leaves it empty when there is none or more
    than one."""
    for table in ("posts", "messages", "stories"):
        execute(db, f"INSERT INTO {table} (post_id, model_id) VALUES (?, ?)", [(33, None)])
    execute(
        db,
        "INSERT INTO medias (media_id, post_id, model_id, downloaded, directory,"
        " filename) VALUES (?,?,?,?,?,?)",
        [(7, 33, None, 1, "/old", "/old/c.jpg")],
    )
    return db


def test_rows_without_a_creator_still_count_as_the_creators(no_creator_rows):
    db = no_creator_rows
    for read in (
        posts.get_all_post_ids,
        messages.get_all_messages_ids,
        stories.get_all_stories_ids,
    ):
        assert 33 in asyncio.run(read(model_id=TWO, db_path=db))
    assert (7, 33) in media.get_media_post_ids(model_id=TWO, db_path=db)
    assert media.get_media_post_files_downloaded(
        model_id=TWO, db_path=db, media_id=7
    ) == {(7, 33): ("/old", "/old/c.jpg")}


def test_media_without_a_creator_is_not_saved_a_second_time(no_creator_rows):
    db = no_creator_rows
    before = media_rows(db)

    async def save():
        await media.batch_mediainsert([_media(7, 33)], model_id=TWO, db_path=db)

    asyncio.run(save())

    assert media_rows(db) == before


def _post(post_id):
    return SimpleNamespace(
        id=post_id,
        db_text="text",
        price=0,
        paid=False,
        archived=False,
        pinned=False,
        stream=False,
        opened=True,
        date=DATE,
        purchase_type=None,
        db_mentions=None,
    )


def test_a_post_another_creator_has_is_still_saved_for_this_one(db, monkeypatch):
    # post 11 is creator ONE's: it counted as creator TWO's too, so it was
    # never written for TWO
    import ofscraper.classes.placeholder as placeholder

    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )

    async def save():
        await posts.make_post_table_changes(
            [_post(11), _post(22)], model_id=TWO, username="creator_two"
        )

    asyncio.run(save())

    with contextlib.closing(sqlite3.connect(db)) as conn:
        saved = sorted(conn.execute("SELECT post_id, model_id FROM posts").fetchall())
    assert saved == [(10, ONE), (10, TWO), (11, ONE), (11, TWO), (22, TWO)]


def _media(media_id, post_id):
    return SimpleNamespace(
        id=media_id,
        post_id=post_id,
        link=None,
        responsetype="timeline",
        mediatype="images",
        preview=0,
        linked=None,
        date=DATE,
        postdate=DATE,
        duration_string=None,
        canview=True,
    )


def test_media_another_creator_has_is_still_saved_for_this_one(db):
    # media 2 of post 11 is creator ONE's. It counted as already saved, so
    # the update that followed matched no row of creator TWO and nothing was
    # written for it.
    async def save():
        await media.batch_mediainsert([_media(2, 11)], model_id=TWO, db_path=db)

    asyncio.run(save())

    assert (2, 11, TWO) in media_rows(db)
    assert (2, 11, ONE) in media_rows(db)


def test_duplicate_files_are_only_looked_for_within_the_creator(
    db, tmp_path, monkeypatch
):
    # both creators have a file with the hash "same". Neither has two, so
    # there's nothing to remove: before, the two counted as duplicates and
    # one creator's file was deleted
    images = dict(db_path=db, mediatypes=("Images",))
    assert media.get_dupe_media_copies(model_id=ONE, **images) == []
    assert media.get_dupe_media_copies(model_id=TWO, **images) == []

    # a real duplicate inside one creator is still found, with its own files
    execute(
        db,
        "INSERT INTO medias (media_id, post_id, model_id, downloaded, directory,"
        " filename, hash, size, media_type) VALUES (?,?,?,?,?,?,?,?,?)",
        [(4, 11, ONE, 1, "/one", "/one/copy.jpg", "same", 5, "Images")],
    )
    assert [
        row["filename"] for row in media.get_dupe_media_copies(model_id=ONE, **images)
    ] == ["/one/a.jpg", "/one/copy.jpg"]
    assert (
        media.get_dupe_media_copies(model_id=ONE, db_path=db, mediatypes=("Videos",))
        == []
    )
    # the other creator's file has that hash too, and still isn't a duplicate
    assert media.get_dupe_media_copies(model_id=TWO, **images) == []


def test_removing_duplicates_leaves_the_other_creators_file(tmp_path, monkeypatch):
    path = tmp_path / "user_data.db"

    async def make():
        await operations.create_tables(db_path=path)
        await modify_tables(db_path=path, new_db=True)

    asyncio.run(make())
    files = {}
    for name, model_id in (("one.jpg", ONE), ("two.jpg", TWO), ("again.jpg", 0)):
        files[model_id] = tmp_path / name
        files[model_id].write_bytes(b"same bytes")
    execute(
        path,
        "INSERT INTO medias (media_id, post_id, model_id, downloaded, directory,"
        " filename, hash, size, media_type) VALUES (?,?,?,?,?,?,?,?,'Images')",
        [
            (1, 10, ONE, 1, str(tmp_path), files[ONE].name, "same", 10),
            (2, 10, TWO, 1, str(tmp_path), files[TWO].name, "same", 10),
            (3, 11, TWO, 1, str(tmp_path), files[0].name, "same", 10),
        ],
    )
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    monkeypatch.setattr(settings, "get_settings", lambda: Stub(hash=True))
    monkeypatch.setattr(
        hash_,
        "get_dupe_media_copies",
        lambda **kwargs: media.get_dupe_media_copies(db_path=path, **kwargs),
    )
    monkeypatch.setattr(
        hash_,
        "point_media_at_kept_files",
        lambda changes, **kwargs: media.point_media_at_kept_files(
            changes, db_path=path, **kwargs
        ),
    )

    assert hash_.remove_dupes_hash("creator_two", TWO, ["Images"]) == [files[0]]

    assert files[ONE].is_file() and files[TWO].is_file()
