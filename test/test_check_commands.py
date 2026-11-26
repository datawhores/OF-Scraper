"""Check commands: paid lookups, -f files and msg_check's help (#202)."""

import ast
import asyncio
import contextlib
import gc
import io
import pathlib
import sys
import warnings
from types import SimpleNamespace

import click
import pytest

import ofscraper.commands.check as check
import ofscraper.utils.args.parse.commands.message as message
import ofscraper.utils.args.parse.commands.paid as paid_cmd
import ofscraper.utils.args.parse.commands.story as story_cmd


def test_get_paid_ids_passes_username_then_id(monkeypatch):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    calls = []

    async def fake_get_paid_posts(username, model_id, c=None):
        calls.append((username, model_id))
        return []

    @contextlib.asynccontextmanager
    async def fake_session(**kwargs):
        yield object()

    async def no_media(*args):
        return []

    monkeypatch.setattr(check, "read_check", lambda *a: None)
    monkeypatch.setattr(check, "set_check", lambda *a: None)
    monkeypatch.setattr(check.paid_, "get_paid_posts", fake_get_paid_posts)
    monkeypatch.setattr(check, "process_post_media", no_media)
    monkeypatch.setattr(check.settings, "get_settings", lambda: SimpleNamespace(force=False))
    monkeypatch.setattr(check.manager, "Manager", SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)))

    try:
        check.get_paid_ids(12345, "a_creator")
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    assert calls == [("a_creator", 12345)]


def test_every_paid_lookup_in_check_passes_username_first():
    tree = ast.parse(pathlib.Path(check.__file__).read_text(encoding="utf-8"))
    def named(n, name):
        f = n.func
        return isinstance(f, ast.Name) and f.id == name or (
            isinstance(f, ast.Attribute)
            and f.attr == name.split(".")[-1]
            and isinstance(f.value, ast.Name)
            and f.value.id == name.split(".")[0]
        )

    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    # OnlyFans' paid lookup is called only through _get_paid, which also
    # picks Fansly's (model id first) for a Fansly profile
    (onlyfans,) = [n for n in calls if named(n, "paid_.get_paid_posts")]
    routed = [n for n in calls if named(n, "_get_paid")]
    assert len(routed) == 3
    for call in [onlyfans, *routed]:
        assert [a.id for a in call.args[:2]] == ["user_name", "model_id"], ast.unparse(call)


def _parse(command, args):
    return command.main(args=args, standalone_mode=False, prog_name="OF-Scraper")


def test_paid_check_reads_usernames_from_a_file(tmp_path):
    f = tmp_path / "users.txt"
    f.write_text("creator_one\ncreator_two\n", encoding="utf-8")
    params, _ = _parse(paid_cmd.paid_check, ["-f", str(f)])
    assert set(params["file_usernames"]) == {"creator_one", "creator_two"}


def test_story_check_reads_usernames_from_a_file(tmp_path):
    f = tmp_path / "users.txt"
    f.write_text("creator_one\n", encoding="utf-8")
    params, _ = _parse(story_cmd.story_check, ["-f", str(f)])
    assert set(params["file_usernames"]) == {"creator_one"}


def _usage_error_warnings(command, args):
    # a usage error after -f was read must not leave the file open (#220)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(click.UsageError):
            _parse(command, args)
        gc.collect()
    return [w for w in caught if issubclass(w.category, ResourceWarning)]


def test_paid_check_usage_error_closes_the_username_file(tmp_path):
    f = tmp_path / "users.txt"
    f.write_text("creator_one\n", encoding="utf-8")
    assert _usage_error_warnings(paid_cmd.paid_check, ["-u", "a", "-f", str(f)]) == []


def test_msg_check_usage_error_closes_the_url_file(tmp_path):
    f = tmp_path / "urls.txt"
    f.write_text("https://onlyfans.com/1/a\n", encoding="utf-8")
    args = ["--url", "https://onlyfans.com/2/b", "-f", str(f)]
    assert _usage_error_warnings(message.message_check, args) == []


def test_check_file_from_stdin_is_read_and_left_open(monkeypatch):
    stdin = io.StringIO("creator_one\ncreator_two\n")
    monkeypatch.setattr(sys, "stdin", stdin)
    params, _ = _parse(paid_cmd.paid_check, ["-f", "-"])
    assert set(params["file_usernames"]) == {"creator_one", "creator_two"}
    assert not stdin.closed


def test_check_usernames_combines_u_and_f(monkeypatch):
    current = SimpleNamespace(check_usernames=["from_u"], file_usernames=["from_f"])
    monkeypatch.setattr(check.settings, "get_settings", lambda: current)
    assert check.check_usernames() == ["from_u", "from_f"]
    current.check_usernames = None
    assert check.check_usernames() == ["from_f"]


def _post(post_id, media_id, **extra):
    return {"id": post_id, "media": [{"id": media_id, "canView": True}], **extra}


def _run_post_check(monkeypatch):
    # the real post_check retriever, with the API calls and the database faked
    calls = []

    async def fake_timeline(model_id, username, c=None):
        calls.append("Timeline")
        return [_post(1, 101)]

    async def fake_archived(model_id, username, c=None):
        calls.append("Archived")
        return [_post(2, 102, isArchived=True)]

    async def fake_pinned(model_id, c=None):
        calls.append("Pinned")
        return [_post(3, 103, isPinned=True)]

    async def fake_labels(model_id, c=None):
        calls.append("Labels")
        return [{"id": 9, "name": "a label", "posts": [_post(4, 104)]}]

    async def fake_streams(model_id, username, c=None):
        calls.append("Streams")
        return [_post(5, 105, streamId=77), _post(6, 106, streamId=78)]

    async def nothing(*args, **kwargs):
        return None

    @contextlib.asynccontextmanager
    async def fake_session(**kwargs):
        yield object()

    current = SimpleNamespace(
        force=False,
        file=None,
        url=["a_creator"],
        check_area=["Timeline", "Archived", "Pinned", "Labels", "Streams"],
        timeline_strict=False,
    )
    monkeypatch.setattr(check.settings, "get_settings", lambda: current)
    monkeypatch.setattr(check.manager, "Manager", SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)))
    monkeypatch.setattr(check, "read_check", lambda *a: None)
    monkeypatch.setattr(check, "set_check", lambda *a: None)
    monkeypatch.setattr(check.profile, "get_id", lambda name, **kw: 12345)
    monkeypatch.setattr(check.operations, "table_init_create", nothing)
    monkeypatch.setattr(check.operations, "make_label_table_changes", nothing)
    monkeypatch.setattr(check.operations, "make_post_table_changes", nothing)
    monkeypatch.setattr(check.timeline, "get_timeline_posts", fake_timeline)
    monkeypatch.setattr(check.archived, "get_archived_posts", fake_archived)
    monkeypatch.setattr(check.pinned, "get_pinned_posts", fake_pinned)
    monkeypatch.setattr(check.labels, "get_labels", fake_labels)
    monkeypatch.setattr(check.streams, "get_streams_posts", fake_streams)

    async def collect():
        return [item async for item in check.post_check_retriver()]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(collect())
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    assert len(results) == 1
    user_name, model_id, posts, _ = results[0]
    assert (user_name, model_id) == ("a_creator", 12345)
    return calls, posts


def test_post_check_lists_streams_posts_and_media(monkeypatch):
    calls, posts = _run_post_check(monkeypatch)
    assert "Streams" in calls
    streams_posts = [p for p in posts if p.responsetype == "Streams"]
    assert sorted(p.id for p in streams_posts) == [5, 6]
    assert sorted(m.id for p in streams_posts for m in p.all_media) == [105, 106]


def test_post_check_other_areas_are_listed_as_before(monkeypatch):
    calls, posts = _run_post_check(monkeypatch)
    assert sorted(calls) == ["Archived", "Labels", "Pinned", "Streams", "Timeline"]
    by_id = {p.id: p for p in posts if p.responsetype != "Streams"}
    assert sorted(by_id) == [1, 2, 3, 4]
    assert by_id[2].responsetype == "Archived"
    assert by_id[3].responsetype == "Pinned"
    assert sorted(m.id for i in (1, 2, 3, 4) for m in by_id[i].all_media) == [101, 102, 103, 104]


def test_msg_check_help_describes_messages():
    assert message.message_check.name == "msg_check"
    assert "messages" in message.message_check.short_help
    assert "post_check" not in message.message_check.help


def _run_msg_check(monkeypatch, inputs):
    # drives the real retriever; profile lookups and the cache are faked
    @contextlib.asynccontextmanager
    async def fake_session(**kwargs):
        yield object()

    async def nothing(*args, **kwargs):
        return None

    ids = {"a_creator": "111", "user123": "222"}
    names = {v: k for k, v in ids.items()}
    looked_up = []
    warned = []

    def scrape_profile(model_id):
        looked_up.append(("id", model_id))
        return {"username": names.get(model_id, "creator_" + model_id)}

    def get_id(username, asked_for=None):
        looked_up.append(("name", username))
        return ids.get(username, "999")

    monkeypatch.setattr(check.settings, "get_settings", lambda: SimpleNamespace(force=False, file=None, url=inputs))
    monkeypatch.setattr(check.manager, "Manager", SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)))
    monkeypatch.setattr(check.profile, "scrape_profile", scrape_profile)
    monkeypatch.setattr(check.profile, "get_id", get_id)
    monkeypatch.setattr(check, "read_check", lambda *a: [])
    monkeypatch.setattr(check.operations, "table_init_create", nothing)
    monkeypatch.setattr(check.operations, "make_messages_table_changes", nothing)
    monkeypatch.setattr(check.log, "warning", lambda msg, *a, **k: warned.append(msg))

    async def collect():
        return [(name, model_id) async for name, model_id, *_ in check.message_check_retriver()]

    return asyncio.run(collect()), looked_up, warned


def test_msg_check_skips_unmatched_input_and_checks_the_rest(monkeypatch):
    checked, _, warned = _run_msg_check(monkeypatch, ["onlyfans.com/my/chats", "a_creator"])
    assert checked == [("a_creator", "111")]
    assert len(warned) == 1 and "onlyfans.com/my/chats" in warned[0]


def test_msg_check_skips_blank_line(monkeypatch):
    checked, looked_up, _ = _run_msg_check(monkeypatch, ["", "a_creator"])
    assert checked == [("a_creator", "111")]
    assert looked_up == [("name", "a_creator")]


def test_msg_check_reads_username_with_digits_as_username(monkeypatch):
    checked, looked_up, _ = _run_msg_check(monkeypatch, ["user123"])
    assert looked_up == [("name", "user123")]
    assert checked == [("user123", "222")]


def test_msg_check_reads_chat_link_and_bare_id_as_model_id(monkeypatch):
    checked, looked_up, _ = _run_msg_check(
        monkeypatch, ["https://onlyfans.com/my/chats/chat/111/", "222"]
    )
    assert looked_up == [("id", "111"), ("id", "222")]
    assert checked == [("a_creator", "111"), ("user123", "222")]


def test_msg_check_reads_message_link_without_chat_part_as_model_id(monkeypatch):
    # the app's own message link format, my/chats/<id>/?id=<message id>
    checked, looked_up, warned = _run_msg_check(
        monkeypatch,
        ["https://onlyfans.com/my/chats/111/?id=999", "https://onlyfans.com/my/chats/a_creator/?id=999"],
    )
    assert looked_up == [("id", "111")]
    assert checked == [("a_creator", "111")]
    assert len(warned) == 1 and "my/chats/a_creator" in warned[0]


def test_msg_check_unmatched_input_does_not_recheck_previous_creator(monkeypatch):
    checked, _, _ = _run_msg_check(monkeypatch, ["a_creator", "onlyfans.com/my/chats"])
    assert checked == [("a_creator", "111")]


# ----------------------------------------------------------------------
# From test_check_missing_creator.py
# A creator OnlyFans can't find is skipped; the check table goes on.
#
# The session passes a 404 through instead of raising, so get_id read
# ``r.json()["id"]`` from OnlyFans' error body and raised KeyError: 'id'.
# That stopped the whole check run at the first deleted, renamed or banned
# account ("Perform Action(s) failed: KeyError: 'id'"). get_id now warns
# and returns None, and each check command skips that creator.
# ----------------------------------------------------------------------

import asyncio
import contextlib
import logging
from types import SimpleNamespace

import pytest

import ofscraper.commands.check as check
import ofscraper.data.api.profile as profile

# --- get_id ---------------------------------------------------------------


class _Response:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class _Session:
    def __init__(self, response):
        self.response = response
        self.urls = []

    @contextlib.contextmanager
    def requests(self, url):
        self.urls.append(url)
        yield self.response


@pytest.fixture
def cache(monkeypatch):
    saved = {}
    monkeypatch.setattr(profile.cache, "get", lambda key, default=None: saved.get(key, default))
    monkeypatch.setattr(profile.cache, "set", lambda key, value, *a, **k: saved.__setitem__(key, value))
    return saved


@pytest.mark.parametrize(
    "response",
    [
        _Response(404, {"error": {"code": 0, "message": "User not found"}}),
        _Response(404, ValueError("not json")),
        _Response(200, {"error": {"message": "something else"}}),
    ],
    ids=["404 error body", "404 not json", "200 without id"],
)
def test_missing_account_warns_and_returns_none(cache, caplog, response):
    with caplog.at_level(logging.WARNING, logger="shared"):
        assert profile.get_id_helper(_Session(response), "gone_creator") is None
    assert "Skipping gone_creator: OnlyFans has no account by that name" in caplog.text
    assert f"HTTP {response.status}" in caplog.text
    # not cached, so a later run asks again
    assert cache == {}


def test_found_account_is_returned_and_cached(cache):
    session = _Session(_Response(200, {"id": 4242, "username": "here"}))
    assert profile.get_id_helper(session, "here") == 4242
    assert cache == {"model_id_here": 4242}
    # the second lookup comes from the cache
    assert profile.get_id_helper(session, "here") == 4242
    assert len(session.urls) == 1


def test_deleted_placeholder_returns_none(cache, caplog):
    name = profile.of_env.getattr("DELETED_MODEL_PLACEHOLDER")
    with caplog.at_level(logging.WARNING, logger="shared"):
        assert profile.get_id_helper(_Session(None), name) is None
    assert "Skipping a deleted account" in caplog.text


def test_deleted_placeholder_names_the_creator_asked_for(cache, caplog):
    """The purchase and stories checks look the profile up first, which turns
    a deleted account into the placeholder; the warning names what was asked."""
    name = profile.of_env.getattr("DELETED_MODEL_PLACEHOLDER")
    with caplog.at_level(logging.WARNING, logger="shared"):
        assert profile.get_id_helper(_Session(None), name, asked_for="gone_creator") is None
    assert "Skipping gone_creator: OnlyFans lists it as a deleted account" in caplog.text


# --- the check commands -----------------------------------------------------

# "gone" sits between two creators that exist, as in the report
NAMES = ["creator_a", "gone", "creator_b"]
IDS = {"creator_a": "111", "creator_b": "222"}


def _run(monkeypatch, retriver):
    fetched = []

    def fetch(*args, **kwargs):
        model = next(str(a) for a in args if str(a) in IDS.values())

        async def inner():
            fetched.append(model)
            return []

        return inner()

    async def nothing(*args, **kwargs):
        return None

    @contextlib.asynccontextmanager
    async def fake_session(**kwargs):
        yield object()

    current = SimpleNamespace(
        force=False,
        file=None,
        url=list(NAMES),
        check_usernames=list(NAMES),
        file_usernames=None,
        check_area=["Timeline"],
        timeline_strict=False,
    )
    monkeypatch.setattr(check.settings, "get_settings", lambda: current)
    monkeypatch.setattr(
        check.manager,
        "Manager",
        SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)),
    )
    monkeypatch.setattr(check.auth_requests, "make_headers", lambda: None)
    asked = []

    def get_id(name, asked_for=None):
        asked.append(asked_for)
        return IDS.get(name)

    monkeypatch.setattr(check.profile, "get_id", get_id)
    monkeypatch.setattr(check.profile, "scrape_profile", lambda name: {"username": name})
    monkeypatch.setattr(check, "read_check", lambda *a: None)
    monkeypatch.setattr(check, "set_check", lambda *a: None)
    for name in ("table_init_create", "make_post_table_changes", "make_messages_table_changes"):
        monkeypatch.setattr(check.operations, name, nothing)
    monkeypatch.setattr(check.timeline, "get_timeline_posts", fetch)
    monkeypatch.setattr(check.messages_, "get_messages", fetch)
    monkeypatch.setattr(check.paid_, "get_paid_posts", fetch)
    monkeypatch.setattr(check.highlights, "get_stories_post", fetch)
    monkeypatch.setattr(check.highlights, "get_highlight_post", fetch)

    async def collect():
        return [str(row[1]) async for row in getattr(check, retriver)()]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yielded = loop.run_until_complete(collect())
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    return yielded, fetched, asked


@pytest.mark.parametrize(
    "retriver",
    [
        "post_check_retriver",
        "message_check_retriver",
        "purchase_check_retriver",
        "stories_check_retriver",
    ],
)
def test_check_skips_the_missing_creator_and_goes_on(monkeypatch, retriver):
    yielded, fetched, asked = _run(monkeypatch, retriver)
    # both real creators, in order; nothing for the missing one
    assert yielded == ["111", "222"]
    assert "None" not in fetched and set(fetched) == {"111", "222"}
    if retriver in ("purchase_check_retriver", "stories_check_retriver"):
        # these look the profile up first, so get_id is told the name asked for
        assert asked == NAMES


# ----------------------------------------------------------------------
# From test_check_purchase_type.py
# The check command records the purchase type of the purchases it saves (#315).
#
# The purchased check (``purchase_check_retriver``) and the messages check
# (``message_check_retriver``, which also lists purchases) build their posts with
# the post's own type, so a bought post is saved to ``posts`` and a bought
# message to ``messages``. That must stay exactly as it is; the only difference
# is that ``posts.purchase_type`` is now set for the bought post.
#
# The expected rows were recorded from the branch before this fix, with
# ``purchase_type`` then ``NULL``. Each test drives the command's real save path
# (the runner, ``process_post_media`` and ``make_changes_to_content_tables``)
# into a real SQLite database in a temporary folder. Only the network, the
# progress display and the UI table are replaced.
# ----------------------------------------------------------------------

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
        check.progress_updater, "activity", SimpleNamespace(update_task=lambda *a, **k: None, desc=None, get_desc_id=lambda: None)
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


# ----------------------------------------------------------------------
# From test_check_timeline_strict.py
# post_check applies timeline_strict to timeline posts, as a normal scrape does (#329).
# ----------------------------------------------------------------------

import asyncio
import contextlib
from types import SimpleNamespace

import ofscraper.commands.check as check


def _strict_post(post_id, media_id, **extra):
    return {"id": post_id, "media": [{"id": media_id, "canView": True}], **extra}


TIMELINE = [_strict_post(1, 101), _strict_post(7, 107, isPinned=True), _strict_post(8, 108, isArchived=True)]
ARCHIVED = [_strict_post(2, 102, isArchived=True)]
PINNED = [_strict_post(3, 103, isPinned=True)]
LABELS = [{"id": 9, "name": "a label", "posts": [_strict_post(4, 104)]}]
STREAMS = [_strict_post(5, 105, streamId=77)]


def _run_strict_post_check(monkeypatch, timeline_strict, timeline=TIMELINE, archived=ARCHIVED, pinned=PINNED, labels=LABELS):
    # the real post_check retriever, with the API calls and the database faked
    async def fake_timeline(model_id, username, c=None):
        return list(timeline)

    async def fake_archived(model_id, username, c=None):
        return list(archived)

    async def fake_pinned(model_id, c=None):
        return list(pinned)

    async def fake_labels(model_id, c=None):
        return list(labels)

    async def fake_streams(model_id, username, c=None):
        return list(STREAMS)

    async def nothing(*args, **kwargs):
        return None

    @contextlib.asynccontextmanager
    async def fake_session(**kwargs):
        yield object()

    current = SimpleNamespace(
        force=False,
        file=None,
        url=["a_creator"],
        check_area=["Timeline", "Archived", "Pinned", "Labels", "Streams"],
        timeline_strict=timeline_strict,
    )
    monkeypatch.setattr(check.settings, "get_settings", lambda: current)
    monkeypatch.setattr(check.manager, "Manager", SimpleNamespace(session=SimpleNamespace(aget_ofsession=fake_session)))
    monkeypatch.setattr(check, "read_check", lambda *a: None)
    monkeypatch.setattr(check, "set_check", lambda *a: None)
    monkeypatch.setattr(check.profile, "get_id", lambda name, **kw: 12345)
    monkeypatch.setattr(check.operations, "table_init_create", nothing)
    monkeypatch.setattr(check.operations, "make_label_table_changes", nothing)
    monkeypatch.setattr(check.operations, "make_post_table_changes", nothing)
    monkeypatch.setattr(check.timeline, "get_timeline_posts", fake_timeline)
    monkeypatch.setattr(check.archived, "get_archived_posts", fake_archived)
    monkeypatch.setattr(check.pinned, "get_pinned_posts", fake_pinned)
    monkeypatch.setattr(check.labels, "get_labels", fake_labels)
    monkeypatch.setattr(check.streams, "get_streams_posts", fake_streams)

    async def collect():
        return [item async for item in check.post_check_retriver()]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(collect())
    finally:
        asyncio.set_event_loop(None)
        loop.close()
    assert len(results) == 1
    user_name, model_id, posts, _ = results[0]
    assert (user_name, model_id) == ("a_creator", 12345)
    return posts


def _ids(posts):
    return [p.id for p in posts]


def test_timeline_strict_leaves_pinned_and_archived_out_of_timeline_posts(monkeypatch):
    posts = _run_strict_post_check(monkeypatch, timeline_strict=True)
    ids = _ids(posts)
    assert 1 in ids
    assert 7 not in ids
    assert 8 not in ids


def test_timeline_strict_off_lists_every_timeline_post(monkeypatch):
    posts = _run_strict_post_check(monkeypatch, timeline_strict=False)
    ids = _ids(posts)
    assert [i for i in ids if i in (1, 7, 8)] == [1, 7, 8]


def test_timeline_strict_does_not_change_other_areas(monkeypatch):
    strict = _ids(_run_strict_post_check(monkeypatch, timeline_strict=True))
    loose = _ids(_run_strict_post_check(monkeypatch, timeline_strict=False))
    timeline_ids = {1, 7, 8}
    others = [i for i in loose if i not in timeline_ids]
    assert [i for i in strict if i not in timeline_ids] == others
    # pinned, archived and labels posts are listed in that order, and only once
    assert others[:3] == [3, 2, 4]


def test_timeline_strict_with_empty_areas(monkeypatch):
    # empty lists compare equal, so nothing may pick the timeline posts out by value
    posts = _run_strict_post_check(monkeypatch, timeline_strict=True, archived=[], pinned=[], labels=[])
    assert [i for i in _ids(posts) if i != 5] == [1]
    posts = _run_strict_post_check(monkeypatch, timeline_strict=True, timeline=[])
    assert [i for i in _ids(posts) if i != 5] == [3, 2, 4]


def test_timeline_strict_only_filters_the_timeline_area(monkeypatch):
    # labels holding the same posts as the timeline keep their pinned and archived posts
    same = [{"id": 9, "name": "a label", "posts": list(TIMELINE)}]
    posts = _run_strict_post_check(monkeypatch, timeline_strict=True, labels=same)
    assert _ids(posts).count(7) == 1
    assert _ids(posts).count(8) == 1
    assert _ids(posts).count(1) == 2


# ----------------------------------------------------------------------
# From test_check_table_large.py
# The check table is built in one pass over the creator's media.
#
# row_gather filled each row's "other posts with this media" by calling
# collection.posts_with_media_id, which reads collection.all_media again, and
# that rebuilds every media object of every post. One rebuild per row made the
# table quadratic, so for a creator with about 14,000 items it never finished.
# ----------------------------------------------------------------------

import asyncio
from types import SimpleNamespace

import pytest

import ofscraper.commands.check as check
from ofscraper.managers.postcollection import PostCollection


class _Log:
    def info(self, *a, **k):
        pass

    warning = debug = info


class _CountingCollection(PostCollection):
    """A real PostCollection that counts how often its media list is rebuilt."""

    def __init__(self, posts, max_reads=None):
        super().__init__(model_id=1, username="a creator")
        for post in posts:
            self._posts_map[post.id] = post
        self.all_media_reads = 0
        self.max_reads = max_reads

    @property
    def all_media(self):
        self.all_media_reads += 1
        if self.max_reads is not None and self.all_media_reads > self.max_reads:
            raise AssertionError(
                f"collection.all_media rebuilt {self.all_media_reads} times "
                "for one check table"
            )
        return super().all_media


def _large_post(post_id, media_ids, day):
    post = SimpleNamespace(id=post_id, post_media=list(media_ids), price=0)
    date = f"2024-01-{day:02d} 00:00:00"
    post.all_media = [
        SimpleNamespace(
            id=media_id,
            post_id=post_id,
            date=date,
            postdate=date,
            formatted_postdate=date,
            canview=True,
            mpd=None,
            url="https://example.invalid/x.jpg",
            _post=post,
            post=SimpleNamespace(db_sanitized_text="t"),
            mediatype="images",
            numeric_duration="N/A",
            responsetype="timeline",
            modified_responsetype="Posts",
        )
        for media_id in media_ids
    ]
    return post


def _rows(monkeypatch, collection):
    monkeypatch.setattr(check, "log", _Log())
    monkeypatch.setattr(check, "get_media_post_files_downloaded", lambda **kw: {})
    monkeypatch.setattr(check, "build_post_centric_rows", lambda *a, **k: [])
    monkeypatch.setattr(check, "check_user_dict", {"1": {"collection": collection}})
    monkeypatch.setattr(check, "ROWS", [])
    monkeypatch.setattr(check, "POST_ROWS", [])
    asyncio.run(check.row_gather("a creator", 1))
    return check.ROWS


def test_large_creator_reads_media_once(monkeypatch):
    # 7,000 posts with two items each: 14,000 rows
    posts = [_large_post(p, (p * 10, p * 10 + 1), p % 28 + 1) for p in range(1, 7001)]
    collection = _CountingCollection(posts, max_reads=1)
    rows = _rows(monkeypatch, collection)
    assert len(rows) == 14000
    assert collection.all_media_reads == 1


@pytest.mark.parametrize("dupes", [False, True])
def test_other_posts_column_unchanged(monkeypatch, dupes):
    # media 100 is in posts 1, 2 and 3; media 200 only in post 2
    posts = [
        _large_post(1, (100,), 3),
        _large_post(2, (100, 200), 2),
        _large_post(3, (100,), 1),
    ]
    if dupes:
        # the same media twice in one post must not list that post as "other"
        posts.append(_large_post(4, (300, 300), 4))
    collection = _CountingCollection(posts)
    # what the per-row lookup gave
    expected = {
        (m.id, m.post_id): [
            p for p in collection.posts_with_media_id(m.id) if p != m.post_id
        ]
        for m in collection.all_media
    }
    rows = _rows(monkeypatch, collection)
    got = {(r["media_id"], r["post_id"]): r["other_posts_with_media"] for r in rows}
    assert got == expected
    assert sorted(got[(100, 1)]) == [2, 3]
    assert got[(200, 2)] == []
