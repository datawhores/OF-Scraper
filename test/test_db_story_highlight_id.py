"""The highlight a story came from is saved (#728).

``stories.highlight_id`` is the id of the highlight a story was scraped
from, so a highlight's files can be grouped later. It is empty for stories
seen only in the Stories area, and for rows saved before the column existed:
the next highlights scan that sees the story fills it in.

Each test builds a real SQLite database in a temporary folder and writes it
through the app's own scrape, upgrade, rebuild and merge code. Only the
OnlyFans API is replaced, by a session that answers its story endpoints.
"""

import asyncio
import contextlib
import copy
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.data.api.highlights as highlights
import ofscraper.data.posts.post as post
import ofscraper.db.merge as merge
import ofscraper.db.operations as operations
import ofscraper.db.postgres as postgres
import ofscraper.db.transition as transition
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.db.difference import get_group_difference
from ofscraper.db.operations_.profile import write_models_table, write_profile_table

MODEL_ID = 72800
USERNAME = "highlightmodel"
FLAG = "stories_highlight_id"
HIGHLIGHT_A = 9001
HIGHLIGHT_B = 9002


def story(story_id):
    return {
        "id": story_id,
        "createdAt": f"2024-07-0{story_id % 9 + 1}T10:00:00+00:00",
        "isReady": True,
        "media": [],
    }


# the stories of each highlight, as the highlight endpoint sends them
HIGHLIGHTS = {HIGHLIGHT_A: [story(1), story(2)], HIGHLIGHT_B: [story(3)]}
# what the Stories area sees: the creator's current stories
CURRENT = [story(1), story(4)]


class Response:
    def __init__(self, data):
        self.status = 200
        self._data = data

    async def json_(self):
        return copy.deepcopy(self._data)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class Session:
    """Answers the OnlyFans story and highlight endpoints."""

    def __init__(self, highlights_=HIGHLIGHTS, current=CURRENT):
        self.answers = {
            of_env.getattr("highlightsWithStoriesEP").format(MODEL_ID, 0): {
                "list": [{"id": h} for h in highlights_],
                "hasMore": False,
            },
            of_env.getattr("highlightsWithAStoryEP").format(MODEL_ID): current,
        }
        for highlight_id, stories in highlights_.items():
            url = of_env.getattr("storyEP").format(highlight_id)
            self.answers[url] = {"id": highlight_id, "stories": stories}

    def requests_async(self, url=None, **kwargs):
        return Response(self.answers[url])


@pytest.fixture
def model_db(monkeypatch, tmp_path):
    db = tmp_path / "data" / "user_data.db"
    db.parent.mkdir()
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )
    # only the backup taken before an upgrade is under test
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    store = {}
    monkeypatch.setattr(cache, "get", lambda key, default=None: store.get(key, default))
    monkeypatch.setattr(cache, "set", lambda key, value, **k: store.update({key: value}))

    def fail(e):
        raise e if isinstance(e, BaseException) else AssertionError(e)

    # surface errors the area functions would otherwise only log
    monkeypatch.setattr(post.log, "traceback_", fail, raising=False)
    monkeypatch.setattr(highlights.log, "traceback_", fail, raising=False)
    return db


@pytest.fixture(params=[None, "check"], ids=["scan", "metadata"])
def onlyfans(request, monkeypatch, model_db):
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(site="onlyfans", metadata=request.param)
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    return stub


def call(func, *args, **kwargs):
    async def go():
        return await func(*args, **kwargs)

    return asyncio.run(go())


def rows(db, sql, *args):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return conn.execute(sql, args).fetchall()


def columns(db, table):
    return [r[1] for r in rows(db, f"PRAGMA table_info({table})")]


def saved(db):
    return rows(db, "SELECT post_id, highlight_id FROM stories ORDER BY post_id")


async def scrape(area, session):
    await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
    await area(MODEL_ID, USERNAME, session)


def scrape_highlights(session=None):
    asyncio.run(scrape(post.process_highlights, session or Session()))


def scrape_stories(session=None):
    asyncio.run(scrape(post.process_stories, session or Session()))


# ------------------------------------------------------------------ scans


def test_each_highlight_story_records_its_highlight(onlyfans, model_db):
    scrape_highlights()

    assert saved(model_db) == [(1, HIGHLIGHT_A), (2, HIGHLIGHT_A), (3, HIGHLIGHT_B)]


def test_a_current_story_has_no_highlight(onlyfans, model_db):
    scrape_stories()

    assert saved(model_db) == [(1, None), (4, None)]


def test_a_highlights_scan_fills_in_a_story_saved_from_the_stories_area(
    onlyfans, model_db
):
    scrape_stories()
    scrape_highlights()

    assert saved(model_db) == [
        (1, HIGHLIGHT_A),
        (2, HIGHLIGHT_A),
        (3, HIGHLIGHT_B),
        (4, None),
    ]
    # and a later stories scan doesn't empty it
    scrape_stories()
    assert saved(model_db)[0] == (1, HIGHLIGHT_A)


def story_check(session=None):
    """What ``ofscraper story_check`` saves: the Stories and Highlights areas
    fetched together and written in one batch."""
    import ofscraper.classes.of.posts as posts_

    session = session or Session()

    async def go():
        await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
        stories = await highlights.get_stories_post(MODEL_ID, c=session)
        highlights_ = await highlights.get_highlight_post(MODEL_ID, c=session)
        batch = [posts_.Post(x, MODEL_ID, USERNAME, "stories") for x in stories]
        batch += [posts_.Post(x, MODEL_ID, USERNAME, "highlights") for x in highlights_]
        await operations.make_changes_to_content_tables(
            batch, model_id=MODEL_ID, username=USERNAME
        )

    asyncio.run(go())


def test_story_check_records_the_highlight_of_a_new_story_also_in_stories(
    onlyfans, model_db
):
    # story 1 is both a current story and in a highlight: the Stories copy is
    # written first, without a highlight
    story_check()

    assert saved(model_db) == [
        (1, HIGHLIGHT_A),
        (2, HIGHLIGHT_A),
        (3, HIGHLIGHT_B),
        (4, None),
    ]


# ------------------------------------------------------------------ upgrade


def layout_before_728(db):
    """A database as the previous version left it: every earlier flag, no column."""
    call(operations.create_tables, db_path=db)
    call(write_profile_table, model_id=MODEL_ID, username=USERNAME, db_path=db)
    call(write_models_table, model_id=MODEL_ID, db_path=db)
    call(transition.modify_tables, db_path=db, new_db=True)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute("ALTER TABLE stories DROP COLUMN highlight_id")
        conn.execute("DELETE FROM schema_flags WHERE flag_name = ?", (FLAG,))
        conn.execute(
            "INSERT INTO stories (post_id, text, price, paid, archived, created_at,"
            " model_id) VALUES (2, 'old story', 0, 1, 0, '2024-07-03T10:00:00+00:00', ?)",
            (MODEL_ID,),
        )
        conn.commit()
    assert get_group_difference(db_path=db) == {FLAG}


def old_schema_backups(db):
    folder = db.parent / "backup"
    return sorted(folder.glob("old_schema_*")) if folder.exists() else []


def test_old_database_is_backed_up_and_upgraded_with_an_empty_field(onlyfans, model_db):
    layout_before_728(model_db)

    call(operations.table_init_create, model_id=MODEL_ID, username=USERNAME)

    (backup,) = old_schema_backups(model_db)
    assert "highlight_id" not in columns(backup, "stories")
    assert not get_group_difference(db_path=model_db)
    assert rows(model_db, "SELECT post_id, text, model_id, highlight_id FROM stories") == [
        (2, "old story", MODEL_ID, None)
    ]


def test_the_step_that_adds_the_column_can_run_again(model_db):
    layout_before_728(model_db)

    for _ in range(2):
        call(transition.add_column_stories_highlight_id, db_path=model_db)

    assert columns(model_db, "stories")[-1] == "highlight_id"


def test_upgraded_database_fills_in_the_highlight_on_the_next_scan(onlyfans, model_db):
    layout_before_728(model_db)

    scrape_highlights()

    assert saved(model_db) == [(1, HIGHLIGHT_A), (2, HIGHLIGHT_A), (3, HIGHLIGHT_B)]
    # the text isn't rewritten outside the metadata command
    if not onlyfans.metadata:
        assert rows(model_db, "SELECT text FROM stories WHERE post_id = 2") == [
            ("old story",)
        ]


# ------------------------------------------------------------------ rebuilds and merge


def filled_database(db):
    call(operations.create_tables, db_path=db)
    call(write_profile_table, model_id=MODEL_ID, username=USERNAME, db_path=db)
    call(write_models_table, model_id=MODEL_ID, db_path=db)
    call(transition.modify_tables, db_path=db, new_db=True)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "INSERT INTO stories (post_id, text, price, paid, archived, created_at,"
            " model_id, highlight_id) VALUES (2, 's', 0, 1, 0,"
            " '2024-07-03T10:00:00+00:00', ?, ?)",
            (MODEL_ID, HIGHLIGHT_A),
        )
        conn.commit()


def test_the_table_rebuild_keeps_the_highlight(tmp_path):
    db = tmp_path / "user_data.db"
    filled_database(db)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "DELETE FROM schema_flags WHERE flag_name = 'stories_model_id_constraint_added'"
        )
        conn.commit()

    call(transition.modify_tables, db_path=db)

    assert not get_group_difference(db_path=db)
    assert saved(db) == [(2, HIGHLIGHT_A)]


def test_merge_keeps_the_highlight(tmp_path):
    source = tmp_path / "old" / "a" / "user_data.db"
    source.parent.mkdir(parents=True)
    filled_database(source)
    target = tmp_path / "new"
    target.mkdir()

    failures, _, _ = asyncio.run(merge.MergeDatabase()(tmp_path / "old", target))

    assert failures == []
    assert saved(target / "user_data.db") == [(2, HIGHLIGHT_A)]


# ------------------------------------------------------------------ PostgreSQL


def test_postgresql_has_the_column_and_adds_it_to_older_databases():
    assert postgres.COLUMN_TYPES["stories"]["highlight_id"] == "BIGINT"
    assert (FLAG, "stories", ("highlight_id",)) in postgres.ADDED_COLUMNS


@pytest.mark.parametrize(
    "value, expected",
    [(123, 123), ("123", 123), (None, None), ("", None), ("abc", None),
     # digits Python's isdigit() accepts but int() doesn't, or reads as another number
     ("\u00b2", None), ("\u0663", None), ("\uff11\uff12", None)],
)
def test_highlight_id_is_read_only_from_plain_digits(value, expected):
    from ofscraper.classes.of.posts import Post

    story = Post({"id": 1, "highlightId": value}, 10, "a creator", responsetype="stories")
    assert story.highlight_id == expected
