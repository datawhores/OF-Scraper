"""Pin what an OnlyFans run writes to user_data.db and where it saves files.

The expected values below were recorded from ``main`` before Fansly posts
existed. They must keep passing unchanged.
"""

import asyncio
import contextlib
import copy
import pathlib
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.classes.of.posts as posts_
import ofscraper.classes.placeholder as placeholder
import ofscraper.data.posts.post as post
import ofscraper.db.operations as operations
import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.download import download
from ofscraper.db.operations_.media import batch_mediainsert

MODEL_ID = 12345
USERNAME = "pinmodel"

TIMELINE_POST = {
    "id": 1001,
    "text": "pinned text",
    "price": 0,
    "isOpened": True,
    "postedAt": "2024-05-01T10:00:00+00:00",
    "responseType": "post",
    "media": [
        {
            "id": 2001,
            "type": "photo",
            "canView": True,
            "createdAt": "2024-05-01T10:00:00+00:00",
            "files": {"full": {"url": "https://cdn.example/files/a/b/2001_source.jpg"}},
        },
        {
            "id": 2002,
            "type": "video",
            "canView": True,
            "duration": 12,
            "createdAt": "2024-05-01T10:00:01+00:00",
            "files": {"full": {"url": "https://cdn.example/files/x/2002.mp4"}},
        },
    ],
}
MESSAGE = {
    "id": 3001,
    "text": "message text",
    "price": 5,
    "isOpened": False,
    "createdAt": "2024-06-01T08:30:00+00:00",
    "responseType": "message",
    "fromUser": {"id": MODEL_ID},
    "media": [
        {
            "id": 4001,
            "type": "photo",
            "canView": False,
            "createdAt": "2024-06-01T08:30:00+00:00",
            "files": {"full": {"url": None}},
        }
    ],
}

POST_COLS = ["id", "post_id", "text", "price", "paid", "archived", "created_at", "model_id"]
FLAGS = [
    "labels_model_id", "labels_model_id_constraint_added", "media_bool_changes",
    "media_duration", "media_hash", "media_model_id", "media_post_id_constraint_added",
    "media_posted_at", "media_unlocked", "messages_group_id", "messages_is_deleted",
    "messages_model_id", "messages_model_id_constraint_added", "other_model_id",
    "others_model_id_constraint_added", "posts_is_deleted", "posts_mentions", "posts_model_id",
    "posts_model_id_constraint_added", "posts_opened", "posts_pinned", "posts_purchase_type",
    "posts_stream", "products_model_id", "products_model_id_constraint_added",
    "profile_username_constraint_modified", "stories_model_id",
    "stories_model_id_constraint_added",
]
EXPECTED_ROWS = {
    "labels": (["id", "label_id", "name", "type", "post_id", "model_id"], []),
    "medias": (
        ["id", "media_id", "post_id", "link", "directory", "filename", "size", "api_type",
         "media_type", "preview", "linked", "downloaded", "created_at", "posted_at",
         "duration", "unlocked", "hash", "model_id"],
        [
            (1, 2001, 1001, "https://cdn.example/files/a/b/2001_source.jpg", None, None, None,
             "Timeline", "Images", 0, 1, None, "2024-05-01T10:00:00+00:00",
             "2024-05-01T10:00:00+00:00", None, 1, None, 12345),
            (2, 2002, 1001, "https://cdn.example/files/x/2002.mp4", None, None, None,
             "Timeline", "Videos", 0, 1, None, "2024-05-01T10:00:01+00:00",
             "2024-05-01T10:00:00+00:00", "00:00:00:12", 1, None, 12345),
            (3, 4001, 3001, None, None, None, None, "Messages", "Images", 0, 0, None,
             "2024-06-01T08:30:00+00:00", "2024-06-01T08:30:00+00:00", None, 0, None, 12345),
        ],
    ),
    "messages": (
        ["id", "post_id", "text", "price", "paid", "archived", "created_at", "user_id",
         "model_id", "is_deleted", "group_id"],
        [(1, 3001, "message text", 5, 1, 0, "2024-06-01T08:30:00+00:00", 12345, 12345, 0, None)],
    ),
    "models": (["id", "model_id"], [(1, 12345)]),
    "others": (POST_COLS, []),
    "posts": (
        ["id", "post_id", "text", "price", "paid", "archived", "pinned", "stream", "opened",
         "created_at", "model_id", "is_deleted", "purchase_type", "mentions"],
        [(1, 1001, "pinned text", 0, 1, 0, 0, 0, 1, "2024-05-01T10:00:00+00:00", 12345, 0, None, None)],
    ),
    "products": (
        ["id", "post_id", "text", "price", "paid", "archived", "created_at", "title", "model_id"],
        [],
    ),
    "profiles": (["id", "user_id", "username"], [(1, 12345, "pinmodel")]),
    "schema_flags": (["flag_name", "flag_value"], [(f, "1") for f in FLAGS]),
    "stories": (POST_COLS, []),
}


@pytest.fixture
def tmp_db(monkeypatch, tmp_path):
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    return db


def dump(db):
    out = {}
    with contextlib.closing(sqlite3.connect(db)) as conn:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        for name in names:
            rows = conn.execute(f"SELECT * FROM {name}").fetchall()
            cols = [d[0] for d in conn.execute(f"SELECT * FROM {name}").description]
            out[name] = (cols, sorted(rows, key=repr))
    return out


async def write_onlyfans_run():
    await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
    post = posts_.Post(TIMELINE_POST, MODEL_ID, USERNAME, "Timeline")
    message = posts_.Post(MESSAGE, MODEL_ID, USERNAME)
    await operations.make_post_table_changes([post], model_id=MODEL_ID, username=USERNAME)
    await operations.make_messages_table_changes(
        [message], model_id=MODEL_ID, username=USERNAME
    )
    await batch_mediainsert(
        post.all_media + message.all_media,
        model_id=MODEL_ID,
        username=USERNAME,
        downloaded=False,
    )


def test_onlyfans_run_writes_the_same_database(tmp_db):
    asyncio.run(write_onlyfans_run())
    assert dump(tmp_db) == EXPECTED_ROWS


# ------------------------------------------------------------------ paths


@pytest.fixture
def path_env(monkeypatch, tmp_path):
    async def fake_common(self, ele, username, model_id):
        self._variables.update(
            {
                "model_username": username,
                "response_type": "Timeline",
                "media_type": "Videos",
            }
        )

    # the app's logger gains .trace at startup; tests don't run that setup
    monkeypatch.setattr(placeholder.log, "trace", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(placeholder.Placeholders, "add_common_variables", fake_common)
    monkeypatch.setattr(placeholder.Textholders, "add_common_variables", fake_common)
    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    monkeypatch.setattr(placeholder.me, "get_id", lambda: 1)
    monkeypatch.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(placeholder.common_paths, "get_config_home", lambda: tmp_path / "cfg")
    monkeypatch.setattr(
        placeholder.common_paths, "get_save_location", lambda *a, **k: str(tmp_path / "data")
    )
    monkeypatch.setattr(
        placeholder.data, "get_dirformat", lambda *a, **k: "{model_username}/{response_type}/{media_type}/"
    )
    return tmp_path


@pytest.mark.parametrize("cls", ["Placeholders", "Textholders"])
def test_onlyfans_media_dir_is_unchanged(path_env, cls):
    ele = SimpleNamespace(username=USERNAME, model_id=MODEL_ID)
    holder = getattr(placeholder, cls)(ele, "mp4")
    path = asyncio.run(holder.getmediadir(create=False))
    assert pathlib.Path(path) == path_env / "data" / USERNAME / "Timeline" / "Videos"
    temp_root = path_env / "tmp"
    path = asyncio.run(holder.getmediadir(root=temp_root, create=False))
    assert pathlib.Path(path) == temp_root / USERNAME / "Timeline" / "Videos"


# metadata formats a user may set; the database lands where it always did
@pytest.mark.parametrize(
    "fmt,expected",
    [
        ("{configpath}/{profile}/.data/{model_id}", ("cfg", "main_profile", ".data", str(MODEL_ID))),
        ("{save_location}/{model_username}/metadata", ("data", USERNAME, "metadata")),
        ("{root}/{model_username}/metadata", ("data", USERNAME, "metadata")),
    ],
)
def test_onlyfans_database_path_is_unchanged(path_env, monkeypatch, fmt, expected):
    monkeypatch.setattr(placeholder.data, "get_metadata", lambda *a, **k: fmt)
    path = placeholder.databasePlaceholder().databasePathHelper(MODEL_ID, USERNAME)
    assert path == path_env.joinpath(*expected, "user_data.db")


def test_onlyfans_saving_files_message_is_unchanged(path_env, monkeypatch):
    monkeypatch.setattr(download.config_data, "get_dirformat", lambda *a, **k: "{model_username}/x")
    monkeypatch.setattr(download.config_data, "get_fileformat", lambda *a, **k: "f.{ext}")
    shown = download.save_path_str(USERNAME, MODEL_ID)
    assert str(path_env / "data" / USERNAME / "x" / "f.{ext}") in shown
    assert "Fansly" not in shown


# ------------------------------------------------------------------ routing


@pytest.fixture
def onlyfans(monkeypatch):
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(site="onlyfans", after=None, post_id=None, timeline_strict=False)
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    return stub


def test_onlyfans_preview_post_keeps_preview_in_the_database(tmp_db):
    item = dict(TIMELINE_POST, id=1002, preview=[2001])
    item["media"] = [TIMELINE_POST["media"][0]]

    async def run():
        await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
        p = posts_.Post(item, MODEL_ID, USERNAME, "Timeline")
        assert [m.preview for m in p.all_media] == [1]
        await batch_mediainsert(p.all_media, model_id=MODEL_ID, username=USERNAME, downloaded=False)

    asyncio.run(run())
    with contextlib.closing(sqlite3.connect(tmp_db)) as conn:
        rows = conn.execute("SELECT media_id, post_id, preview FROM medias").fetchall()
    assert rows == [(2001, 1002, 1)]


def test_onlyfans_run_calls_the_onlyfans_fetchers(onlyfans, tmp_db, monkeypatch):
    calls = []

    def record(name, result):
        async def fetch(*args, **kwargs):
            calls.append(name)
            return copy.deepcopy(result)

        return fetch

    async def fansly_fetch(*args, **kwargs):
        raise AssertionError("a Fansly fetcher ran on an OnlyFans run")

    def fail(e):
        raise e if isinstance(e, BaseException) else AssertionError(e)

    monkeypatch.setattr(post.log, "traceback_", fail, raising=False)
    monkeypatch.setattr(post.timeline, "get_timeline_posts", record("timeline", [TIMELINE_POST]))
    monkeypatch.setattr(post.messages, "get_messages", record("messages", [MESSAGE]))
    monkeypatch.setattr(post.paid, "get_paid_posts", record("paid", [MESSAGE]))
    for name in ("get_timeline_posts", "get_messages", "get_paid_posts"):
        monkeypatch.setattr(post.fansly_scrape, name, fansly_fetch)

    async def run():
        await operations.table_init_create(model_id=MODEL_ID, username=USERNAME)
        timeline_posts, _ = await post.process_timeline_posts(MODEL_ID, USERNAME, None)
        messages_, _ = await post.process_messages(MODEL_ID, USERNAME, None)
        paid_, _ = await post.process_paid_post(MODEL_ID, USERNAME, None)
        return timeline_posts, messages_, paid_

    timeline_posts, messages_, paid_ = asyncio.run(run())
    assert calls == ["timeline", "messages", "paid"]
    assert [p.id for p in timeline_posts] == [1001]
    assert [p.id for p in messages_] == [3001]
    assert [p.id for p in paid_] == [3001]


def test_onlyfans_run_keeps_every_area(onlyfans, monkeypatch):
    called = []

    async def fake(name):
        called.append(name)
        return [], name

    names = ["paid_post", "messages", "timeline_posts", "pinned_posts", "archived_posts",
             "highlights", "stories", "labels", "streamed_posts"]
    for name in names:
        monkeypatch.setattr(post, f"process_{name}", lambda *a, _n=name, **k: fake(_n))
    monkeypatch.setattr(post, "process_profile", lambda *a, **k: fake("profile"))
    monkeypatch.setattr(post, "get_final_posts_area", lambda: [
        "Profile", "Purchased", "Messages", "Pinned", "Timeline", "Archived", "Highlights",
        "Stories", "Labels", "Streams"])
    monkeypatch.setattr(post, "get_like_area", lambda: [])
    monkeypatch.setattr(post, "get_download_area", lambda: [])
    monkeypatch.setattr(post.progress_utils, "setup_live", lambda *a, **k: contextlib.nullcontext())
    asyncio.run(post.process_tasks(MODEL_ID, USERNAME, SimpleNamespace(active=True)))
    assert sorted(called) == sorted(names + ["profile"])