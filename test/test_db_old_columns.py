"""`ofscraper db` and the table readers on databases without newer columns (#364).

`ofscraper db` doesn't upgrade a database, so it can meet one that no scrape
has opened since a column was added. A missing optional column counts as not
set, and the database's columns don't change.
"""

import asyncio
import contextlib
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.commands.db as db_command
import ofscraper.db.operations_.labels as labels_ops
import ofscraper.db.operations_.media as media_ops
import ofscraper.db.operations_.messages as messages_ops
import ofscraper.db.operations_.others as others_ops
import ofscraper.db.operations_.posts as posts_ops
import ofscraper.db.operations_.stories as stories_ops

ALL_AREAS = [
    "Timeline",
    "Pinned",
    "Archived",
    "Messages",
    "Streams",
    "Highlights",
    "Stories",
]

# each area's reader, and an api_type it reads
AREA_READERS = {
    "Timeline": "get_timeline_media",
    "Pinned": "get_pinned_media",
    "Archived": "get_archived_media",
    "Messages": "get_messages_media",
    "Streams": "get_streams_media",
    "Highlights": "get_highlights_media",
    "Stories": "get_stories_media",
}
AREA_API_TYPES = {
    "Timeline": "timeline",
    "Pinned": "pinned",
    "Archived": "archived",
    "Messages": "messages",
    "Streams": "streams",
    "Highlights": "highlights",
    "Stories": "stories",
}

# the medias table as released before skip_permanent was added (#357)
MEDIAS_BEFORE_SKIP_PERMANENT = """
CREATE TABLE IF NOT EXISTS medias (
    id INTEGER NOT NULL,
    media_id INTEGER,
    post_id INTEGER NOT NULL,
    link VARCHAR,
    directory VARCHAR,
    filename VARCHAR,
    size INTEGER,
    api_type VARCHAR,
    media_type VARCHAR,
    preview INTEGER,
    linked BOOL,
    downloaded BOOL,
    created_at TIMESTAMP,
    posted_at TIMESTAMP,
    duration VARCHAR,
    unlocked BOOL,
    hash VARCHAR,
    model_id INTEGER,
    PRIMARY KEY (id),
    UNIQUE (media_id,model_id,post_id)
);"""

# an older one still: before hash, duration and unlocked were added
MEDIAS_BEFORE_HASH = """
CREATE TABLE IF NOT EXISTS medias (
    id INTEGER NOT NULL,
    media_id INTEGER,
    post_id INTEGER NOT NULL,
    link VARCHAR,
    directory VARCHAR,
    filename VARCHAR,
    size INTEGER,
    api_type VARCHAR,
    media_type VARCHAR,
    preview INTEGER,
    linked BOOL,
    downloaded BOOL,
    created_at TIMESTAMP,
    posted_at TIMESTAMP,
    model_id INTEGER,
    PRIMARY KEY (id),
    UNIQUE (media_id,model_id,post_id)
);"""

# the query before #364, for comparing output on an up-to-date database
MEDIA_SELECT_BEFORE = """
SELECT  media_id,post_id,link,directory,filename,size,api_type,
media_type,preview,linked,downloaded,created_at,unlocked,
model_id,posted_at,hash,duration,skip_permanent
FROM medias;
"""

MEDIA_ROWS = [
    {
        "media_id": 1,
        "post_id": 100,
        "link": "https://example.invalid/a.jpg",
        "directory": "/media",
        "filename": "a.jpg",
        "size": 2048,
        "api_type": "timeline",
        "media_type": "Images",
        "preview": 0,
        "linked": None,
        "downloaded": 1,
        "created_at": "2024-01-01T10:00:00",
        "posted_at": "2024-01-02T10:00:00",
        "duration": "0:00:00:10",
        "unlocked": 1,
        "hash": "abc",
        "model_id": 5,
        "skip_permanent": 1,
    },
    {
        "media_id": 2,
        "post_id": 101,
        "link": "https://example.invalid/b.mp4",
        "directory": None,
        "filename": None,
        "size": None,
        "api_type": "messages",
        "media_type": "Videos",
        "preview": 1,
        "linked": None,
        "downloaded": 0,
        "created_at": "2024-02-01T10:00:00",
        "posted_at": "2024-02-02T10:00:00",
        "duration": None,
        "unlocked": 0,
        "hash": None,
        "model_id": 5,
        "skip_permanent": None,
    },
]


def make_db(path, create, table, rows):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        conn.execute(create)
        columns = [row[1] for row in conn.execute(f"PRAGMA table_info('{table}')")]
        columns = [c for c in columns if c != "id" or table == "labels"]
        for row in rows:
            names = [c for c in columns if c in row]
            conn.execute(
                f"INSERT INTO {table} ({','.join(names)}) VALUES ({','.join('?' * len(names))})",
                [row[c] for c in names],
            )
        conn.commit()


def schema(path):
    with contextlib.closing(sqlite3.connect(path)) as conn:
        return [
            tuple(row)
            for table in ("medias", "posts", "messages", "stories", "others", "products", "labels")
            for row in conn.execute(f"PRAGMA table_info('{table}')")
        ]


@pytest.fixture
def run_db(monkeypatch):
    """Run `ofscraper db` over all areas on one database; returns its rows."""

    def run(path, areas=ALL_AREAS):
        args = SimpleNamespace(
            download_area=areas,
            downloaded=None,
            protected=False,
            normal=False,
            unlocked=None,
            preview=None,
            post_id=None,
            media_id=None,
        )
        options = SimpleNamespace(
            size_max=None,
            size_min=None,
            length_max=None,
            length_min=None,
            posted_before=None,
            posted_after=None,
            created_after=None,
            created_before=None,
            mediatypes=["Audios", "Videos", "Images"],
            max_post_count=None,
            db_asc=True,
            db_sort="mediaid",
            export=None,
        )
        monkeypatch.setattr(db_command.settings, "get_args", lambda: args)
        monkeypatch.setattr(db_command.settings, "get_settings", lambda: options)
        real = media_ops.get_all_medias

        async def get_all_medias(**kwargs):
            return await real(**kwargs, db_path=path)

        monkeypatch.setattr(db_command, "get_all_medias", get_all_medias)
        for name in AREA_READERS.values():
            area_reader = getattr(media_ops, name)
            monkeypatch.setattr(
                db_command,
                name,
                lambda reader=area_reader, **kwargs: reader(**kwargs, db_path=path),
            )
        manager = db_command.DBManager("a creator", 5)
        # the command's run() keeps the current loop open; close it after
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            manager.get_wanted_media()
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return [dict(row) for row in manager.media]

    return run


def test_db_without_skip_permanent_shows_rows(tmp_path, run_db):
    # Given a database without skip_permanent
    path = tmp_path / "user_data.db"
    make_db(path, MEDIAS_BEFORE_SKIP_PERMANENT, "medias", MEDIA_ROWS)
    before = schema(path)

    # When ofscraper db runs over all areas
    rows = run_db(path)

    # Then it shows the rows, and the missing column counts as not set
    assert [row["media_id"] for row in rows] == [1, 2]
    assert [row["skip_permanent"] for row in rows] == [None, None]
    assert rows[0]["hash"] == "abc"
    # and the database's columns don't change
    assert schema(path) == before


def test_db_without_older_optional_columns_shows_rows(tmp_path, run_db):
    # Given a database from before hash, duration and unlocked
    path = tmp_path / "user_data.db"
    make_db(path, MEDIAS_BEFORE_HASH, "medias", MEDIA_ROWS)
    before = schema(path)

    rows = run_db(path)

    assert [row["media_id"] for row in rows] == [1, 2]
    for row in rows:
        assert row["hash"] is None
        assert row["duration"] is None
        assert row["unlocked"] is None
        assert row["skip_permanent"] is None
    assert rows[0]["filename"] == "a.jpg"
    assert schema(path) == before


def test_db_up_to_date_gives_same_output(tmp_path, run_db, monkeypatch):
    # Given an up-to-date database
    path = tmp_path / "user_data.db"
    make_db(path, media_ops.mediaCreate, "medias", MEDIA_ROWS)
    before = schema(path)

    rows = run_db(path)

    # the output is what the query before #364 gave
    def get_all_medias_before(**kwargs):
        with contextlib.closing(sqlite3.connect(path)) as conn:
            conn.row_factory = sqlite3.Row
            data = [dict(row) for row in conn.execute(MEDIA_SELECT_BEFORE)]
        return [
            dict(row, model_id=row.get("model_id"), duration=row.get("duration"), unlocked=row.get("unlocked"))
            for row in data
        ]

    async def fake(**kwargs):
        return get_all_medias_before()

    monkeypatch.setattr(media_ops, "get_all_medias", fake)
    expected = run_db(path)
    assert rows == expected
    # same keys in the same order too, as the CSV export's header follows it
    assert [list(row) for row in rows] == [list(row) for row in expected]
    assert rows[0]["skip_permanent"] == 1
    assert schema(path) == before


# one row in each area, for the per-area runs
AREA_ROWS = [
    dict(MEDIA_ROWS[0], media_id=i, post_id=200 + i, api_type=api_type)
    for i, api_type in enumerate(AREA_API_TYPES.values(), start=1)
]

# the per-area queries' columns before #364
AREA_COLUMNS_BEFORE = (
    "media_id,post_id,link,directory,filename,size,api_type,media_type,"
    "preview,linked,downloaded,created_at,posted_at,hash,model_id,unlocked,duration"
)


@pytest.mark.parametrize("area", ALL_AREAS)
def test_db_per_area_without_older_optional_columns_shows_rows(tmp_path, run_db, area):
    # Given a database from before hash, duration and unlocked
    path = tmp_path / "user_data.db"
    make_db(path, MEDIAS_BEFORE_HASH, "medias", AREA_ROWS)
    before = schema(path)

    # When ofscraper db runs over one area
    rows = run_db(path, [area])

    # Then it shows that area's rows, the missing columns count as not set
    assert [row["api_type"] for row in rows] == [AREA_API_TYPES[area]]
    assert rows[0]["filename"] == "a.jpg"
    assert rows[0]["hash"] is None
    assert rows[0]["duration"] is None
    assert rows[0]["unlocked"] is None
    # and the database's columns don't change
    assert schema(path) == before


def test_db_per_area_without_model_id_shows_rows(tmp_path, run_db):
    # Given a database from before model_id, which holds one creator's media
    path = tmp_path / "user_data.db"
    create = MEDIAS_BEFORE_HASH.replace("    model_id INTEGER,\n", "").replace(
        "UNIQUE (media_id,model_id,post_id)", "UNIQUE (media_id,post_id)"
    )
    make_db(path, create, "medias", AREA_ROWS)
    before = schema(path)

    rows = run_db(path, ["Timeline", "Messages"])

    assert sorted(row["api_type"] for row in rows) == ["messages", "timeline"]
    assert all(row["model_id"] is None for row in rows)
    assert schema(path) == before


def test_db_per_area_up_to_date_gives_same_output(tmp_path, run_db, monkeypatch):
    # Given an up-to-date database, with rows of another creator too
    path = tmp_path / "user_data.db"
    other = [dict(row, model_id=6) for row in AREA_ROWS]
    make_db(path, media_ops.mediaCreate, "medias", AREA_ROWS + other)
    before = schema(path)
    areas = ["Timeline", "Messages", "Pinned", "Stories"]

    rows = run_db(path, areas)

    # the output is what the queries before #364 gave
    def execute_before(cur, query, model_id):
        cur.execute(
            query.format(columns=AREA_COLUMNS_BEFORE, model_filter="and model_id=(?)"),
            [model_id],
        )

    monkeypatch.setattr(media_ops, "execute_area_media", execute_before)
    expected = run_db(path, areas)
    assert rows == expected
    assert [list(row) for row in rows] == [list(row) for row in expected]
    assert sorted(row["api_type"] for row in rows) == [
        "messages",
        "pinned",
        "stories",
        "timeline",
    ]
    assert {row["model_id"] for row in rows} == {5}
    assert schema(path) == before


# The table readers merge and the scrape-time table rebuilds use: each optional
# column missing at once gives its stand-in, and the rest of the row is kept.
OLD_TABLES = [
    (
        posts_ops.get_all_posts_transition,
        "posts",
        "CREATE TABLE posts (id INTEGER NOT NULL, post_id INTEGER NOT NULL, text VARCHAR,"
        " price INTEGER, paid INTEGER, archived BOOLEAN, created_at TIMESTAMP, PRIMARY KEY (id))",
        {"post_id": 7, "text": "t", "price": 0, "paid": 0, "archived": 0, "created_at": "x"},
        {
            "model_id": 9,
            "pinned": None,
            "stream": None,
            "opened": None,
            "is_deleted": 0,
            "purchase_type": None,
            "mentions": None,
        },
    ),
    (
        messages_ops.get_all_messages_transition,
        "messages",
        "CREATE TABLE messages (id INTEGER NOT NULL, post_id INTEGER NOT NULL, text VARCHAR,"
        " price INTEGER, paid INTEGER, archived BOOLEAN, created_at TIMESTAMP, user_id INTEGER,"
        " PRIMARY KEY (id))",
        {"post_id": 7, "text": "t", "price": 0, "paid": 0, "archived": 0, "created_at": "x", "user_id": 3},
        {"model_id": 9, "is_deleted": 0, "group_id": None},
    ),
    (
        stories_ops.get_all_stories_transition,
        "stories",
        "CREATE TABLE stories (id INTEGER NOT NULL, post_id INTEGER NOT NULL, text VARCHAR,"
        " price INTEGER, paid INTEGER, archived BOOLEAN, created_at TIMESTAMP, PRIMARY KEY (id))",
        {"post_id": 7, "text": "t", "price": 0, "paid": 0, "archived": 0, "created_at": "x"},
        {"model_id": 9},
    ),
    (
        others_ops.get_all_others_transition,
        "others",
        "CREATE TABLE others (id INTEGER NOT NULL, post_id INTEGER NOT NULL, text VARCHAR,"
        " price INTEGER, paid INTEGER, archived BOOLEAN, created_at TIMESTAMP, PRIMARY KEY (id))",
        {"post_id": 7, "text": "t", "price": 0, "paid": 0, "archived": 0, "created_at": "x"},
        {"model_id": 9},
    ),
    (
        others_ops.get_all_products_transition,
        "products",
        "CREATE TABLE products (id INTEGER NOT NULL, post_id INTEGER NOT NULL, text VARCHAR,"
        " price INTEGER, paid INTEGER, archived BOOLEAN, created_at TIMESTAMP, title VARCHAR,"
        " PRIMARY KEY (id))",
        {"post_id": 7, "text": "t", "price": 0, "paid": 0, "archived": 0, "created_at": "x", "title": "p"},
        {"model_id": 9},
    ),
    (
        # before label_id, the label's id was the row id
        labels_ops.get_all_labels_transition,
        "labels",
        "CREATE TABLE labels (id INTEGER NOT NULL, name VARCHAR, type VARCHAR,"
        " post_id INTEGER, PRIMARY KEY (id))",
        {"id": 4, "name": "n", "type": "custom", "post_id": 7},
        {"label_id": 4, "model_id": 9},
    ),
    (
        media_ops.get_all_medias_transition,
        "medias",
        MEDIAS_BEFORE_HASH.replace("    model_id INTEGER,\n", "").replace(
            "UNIQUE (media_id,model_id,post_id)", "UNIQUE (media_id,post_id)"
        ).replace("    posted_at TIMESTAMP,\n", ""),
        {k: v for k, v in MEDIA_ROWS[0].items() if k in (
            "media_id", "post_id", "link", "directory", "filename", "size", "api_type",
            "media_type", "preview", "linked", "downloaded", "created_at",
        )},
        {
            "model_id": 9,
            "posted_at": None,
            "hash": None,
            "duration": None,
            "unlocked": None,
            "skip_permanent": None,
        },
    ),
]


@pytest.mark.parametrize(
    "reader,table,create,row,stand_ins", OLD_TABLES, ids=[t[1] for t in OLD_TABLES]
)
def test_transition_readers_on_old_tables(tmp_path, reader, table, create, row, stand_ins):
    path = tmp_path / "user_data.db"
    make_db(path, create, table, [row])
    before = schema(path)

    rows = asyncio.run(reader(db_path=path, database_model=9))

    expected = {k: v for k, v in row.items() if k != "id"}
    expected.update(stand_ins)
    assert rows == [expected]
    assert schema(path) == before
