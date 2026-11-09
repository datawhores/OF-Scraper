"""The check command records the purchase type of the purchases it saves (#315).

The purchased check (``purchase_check_retriver``) and the messages check
(``message_check_retriver``, which also lists purchases) build their posts with
the post's own type, so a bought post is saved to ``posts`` and a bought
message to ``messages``. That must stay exactly as it is; the only difference
is that ``posts.purchase_type`` is now set for the bought post.

The expected rows were recorded from the branch before this fix, with
``purchase_type`` then ``NULL``. Each test drives the command's real save path
(the runner, ``process_post_media`` and ``make_changes_to_content_tables``)
into a real SQLite database in a temporary folder. Only the network, the
progress display and the UI table are replaced.
"""

import asyncio
import contextlib
import copy
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.check as check
import ofscraper.db.operations as operations
import ofscraper.utils.settings as settings

MODEL_ID = 31501
USERNAME = "checkmodel"

BOUGHT_POST = {
    "id": 6001,
    "text": "bought post",
    "price": 3,
    "isOpened": True,
    "postedAt": "2024-08-01T10:00:00+00:00",
    "responseType": "post",
    "media": [
        {
            "id": 6101,
            "type": "photo",
            "canView": True,
            "createdAt": "2024-08-01T10:00:00+00:00",
            "files": {"full": {"url": "https://cdn.example/files/6101.jpg"}},
        }
    ],
}
BOUGHT_MESSAGE = {
    "id": 6002,
    "text": "bought message",
    "price": 4,
    "isOpened": True,
    "createdAt": "2024-08-02T10:00:00+00:00",
    "responseType": "message",
    "fromUser": {"id": MODEL_ID},
    "media": [
        {
            "id": 6102,
            "type": "video",
            "canView": True,
            "duration": 5,
            "createdAt": "2024-08-02T10:00:00+00:00",
            "files": {"full": {"url": "https://cdn.example/files/6102.mp4"}},
        }
    ],
}

MEDIA_COLS = [
    "id", "media_id", "post_id", "link", "directory", "filename", "size", "api_type",
    "media_type", "preview", "linked", "downloaded", "created_at", "posted_at", "duration",
    "unlocked", "hash", "model_id", "skip_permanent",
]
EXPECTED = {
    "posts": (
        ["id", "post_id", "text", "price", "paid", "archived", "pinned", "stream", "opened",
         "created_at", "model_id", "is_deleted", "purchase_type", "mentions"],
        [(1, 6001, "bought post", 3, 1, 0, 0, 0, 1, "2024-08-01T10:00:00+00:00", MODEL_ID, 0,
          "post", None)],
    ),
    "messages": (
        ["id", "post_id", "text", "price", "paid", "archived", "created_at", "user_id",
         "model_id", "is_deleted", "group_id"],
        [(1, 6002, "bought message", 4, 1, 0, "2024-08-02T10:00:00+00:00", MODEL_ID, MODEL_ID,
          0, None)],
    ),
    "medias": (
        MEDIA_COLS,
        [
            (1, 6101, 6001, "https://cdn.example/files/6101.jpg", None, None, None, "Timeline",
             "Images", 0, 1, None, "2024-08-01T10:00:00+00:00", "2024-08-01T10:00:00+00:00",
             None, 1, None, MODEL_ID, None),
            (2, 6102, 6002, "https://cdn.example/files/6102.mp4", None, None, None, "Messages",
             "Videos", 0, 1, None, "2024-08-02T10:00:00+00:00", "2024-08-02T10:00:00+00:00",
             "00:00:00:05", 1, None, MODEL_ID, None),
        ],
    ),
}
# tables these checks don't write keep only what table_init_create puts there
UNTOUCHED = ("labels", "others", "products", "stories")


@pytest.fixture
def check_env(monkeypatch, tmp_path):
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder, "databasePathHelper", lambda self, mid, name: db
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(
        site="onlyfans", force=False, metadata=None, check_usernames=[USERNAME],
        file_usernames=None, file=None, url=[USERNAME],
    )
    monkeypatch.setattr(settings, "get_settings", lambda: stub)

    @contextlib.asynccontextmanager
    async def session(*args, **kwargs):
        yield None

    async def fetch(*args, **kwargs):
        return copy.deepcopy([BOUGHT_POST, BOUGHT_MESSAGE])

    async def no_messages(*args, **kwargs):
        return []

    async def no_rows(*args, **kwargs):
        return None

    monkeypatch.setattr(
        check.manager, "Manager", SimpleNamespace(session=SimpleNamespace(aget_ofsession=session))
    )
    monkeypatch.setattr(check.auth_requests, "make_headers", lambda *a, **k: None)
    monkeypatch.setattr(check.profile, "scrape_profile", lambda *a, **k: {"username": USERNAME})
    monkeypatch.setattr(check.profile, "get_id", lambda *a, **k: MODEL_ID)
    monkeypatch.setattr(check, "read_check", lambda *a, **k: None)
    monkeypatch.setattr(check, "set_check", lambda *a, **k: None)
    monkeypatch.setattr(check.paid_, "get_paid_posts", fetch)
    monkeypatch.setattr(check.messages_, "get_messages", no_messages)
    monkeypatch.setattr(check, "row_gather", no_rows)
    monkeypatch.setattr(check.progress_utils, "setup_live", lambda *a, **k: contextlib.nullcontext())
    monkeypatch.setattr(
        check.progress_updater, "activity", SimpleNamespace(update_task=lambda *a, **k: None)
    )
    monkeypatch.setattr(check, "check_user_dict", check.defaultdict(dict))
    return db


def dump(db):
    out = {}
    with contextlib.closing(sqlite3.connect(db)) as conn:
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            cursor = conn.execute(f"SELECT * FROM {name}")
            out[name] = ([d[0] for d in cursor.description], sorted(cursor.fetchall(), key=repr))
    return out


@pytest.mark.parametrize("runner", ["purchase_checker_runner", "message_checker_runner"])
def test_check_command_saves_purchases_with_their_type(check_env, runner):
    # inside a running loop the app's @run functions return a coroutine
    async def go():
        await getattr(check, runner)()

    asyncio.run(go())

    saved = dump(check_env)
    for table, expected in EXPECTED.items():
        assert saved[table] == expected
    for table in UNTOUCHED:
        assert saved[table][1] == []
