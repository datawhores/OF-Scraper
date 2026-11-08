import asyncio
import contextlib
import logging
from types import SimpleNamespace

import pytest

import ofscraper.data.posts.post as post
import ofscraper.data.posts.scrape_paid as scrape_paid
import ofscraper.utils.settings as settings
from ofscraper.utils.args.callbacks.parse.username import UsernameParse

PLACEHOLDER = "modeldeleted"

# model_id -> username the profile lookup returns
PROFILES = {1: "Alice", 2: "bob", 3: "Carol", 4: PLACEHOLDER, 5: PLACEHOLDER}
# usernames recorded for deleted models in an earlier run
RECORDED = {4: "dave"}


class _Activity:
    def __getattr__(self, name):
        return lambda *a, **k: None


class _Collection:
    def __init__(self, username, model_id):
        self.posts = []
        self.all_unique_media = []

    def add_posts(self, posts, actions=None):
        self.posts = posts

    def get_posts_for_text_download(self):
        return self.posts

    def get_media_for_processing(self):
        return self.posts


@pytest.fixture
def paid_run(monkeypatch):
    """Run process_all_paid against stubbed API/db calls; returns (output, db_calls, warnings)."""
    db_calls = []

    async def get_all_paid_posts():
        return {model_id: [{"id": model_id}] for model_id in PROFILES}

    async def record(*args, model_id=None, username=None, **kwargs):
        db_calls.append(username)

    async def profile_exists(model_id=None, username=None):
        return model_id in RECORDED

    async def profile_info(model_id=None, username=None):
        return RECORDED.get(model_id)

    monkeypatch.setattr(post.paid, "get_all_paid_posts", get_all_paid_posts)
    monkeypatch.setattr(post.profile, "scrape_profile", lambda model_id: {"username": PROFILES[model_id]})
    monkeypatch.setattr(post, "check_profile_table_exists", profile_exists)
    monkeypatch.setattr(post, "get_profile_info", profile_info)
    monkeypatch.setattr(post.operations, "table_init_create", record)
    monkeypatch.setattr(post.operations, "make_post_table_changes", record)
    monkeypatch.setattr(post, "batch_mediainsert", record)
    monkeypatch.setattr(post, "PostCollection", _Collection)
    monkeypatch.setattr(post.posts_, "Post", lambda raw, *a, **k: raw)
    monkeypatch.setattr(post.progress_utils, "setup_live", lambda *a, **k: contextlib.nullcontext())
    monkeypatch.setattr(post.progress_updater, "activity", _Activity())
    monkeypatch.setenv("OFSC_DELETED_MODEL_PLACEHOLDER", PLACEHOLDER)

    warnings = []

    class Capture(logging.Handler):
        def emit(self, record):
            if record.levelno == logging.WARNING:
                warnings.append(record.getMessage())

    handler = Capture()
    post.log.addHandler(handler)

    def run(cli_values, command="scraper"):
        # Same normalization the --excluded-username option applies.
        excluded = UsernameParse(None, None, cli_values)
        monkeypatch.setattr(
            settings,
            "get_settings",
            lambda: SimpleNamespace(
                excluded_username=excluded, system_free_min=0, command=command
            ),
        )

        async def collect():
            return [ele async for ele in scrape_paid.process_paid_dict()]

        yielded = asyncio.run(collect())
        return yielded, db_calls, warnings

    yield run
    post.log.removeHandler(handler)


def _names(yielded):
    return [value["username"] for _, value, _ in yielded]


@pytest.mark.parametrize("command", ["scraper", "metadata"])
def test_excluded_model_is_skipped_before_db_and_totals(paid_run, command):
    yielded, db_calls, warnings = paid_run(("bob",), command=command)

    assert _names(yielded) == ["Alice", "Carol", "dave", f"{PLACEHOLDER}_5"]
    assert {length for _, _, length in yielded} == {4}
    assert "bob" not in db_calls
    assert warnings == ["Skipping bob_2: excluded by --excluded-username"]


def test_match_is_case_insensitive(paid_run):
    yielded, db_calls, warnings = paid_run(("aLiCe",))

    assert "Alice" not in _names(yielded)
    assert "Alice" not in db_calls
    assert warnings == ["Skipping Alice_1: excluded by --excluded-username"]


@pytest.mark.parametrize("cli_values", [("alice,carol",), ("alice", "CAROL")])
def test_multiple_exclusions(paid_run, cli_values):
    yielded, db_calls, warnings = paid_run(cli_values)

    assert _names(yielded) == ["bob", "dave", f"{PLACEHOLDER}_5"]
    assert {length for _, _, length in yielded} == {3}
    assert not {"Alice", "Carol"} & set(db_calls)
    assert len(warnings) == 2


def test_account_id_is_excluded(paid_run):
    yielded, db_calls, warnings = paid_run(("2",))

    assert "bob" not in _names(yielded)
    assert "bob" not in db_calls
    assert warnings == ["Skipping bob_2: excluded by --excluded-username"]


def test_unmatched_exclusion_leaves_models_alone(paid_run):
    yielded, _, warnings = paid_run(("someoneelse",))

    assert _names(yielded) == ["Alice", "bob", "Carol", "dave", f"{PLACEHOLDER}_5"]
    assert warnings == []


def test_no_exclusions(paid_run):
    yielded, db_calls, warnings = paid_run(())

    assert len(yielded) == 5
    assert set(PROFILES) == {value["model_id"] for _, value, _ in yielded}
    assert warnings == []


def test_deleted_model_matches_recorded_username(paid_run):
    yielded, db_calls, _ = paid_run(("dave",))

    assert "dave" not in _names(yielded)
    assert "dave" not in db_calls


def test_deleted_model_without_recorded_username_is_not_matched(paid_run):
    # Only the placeholder is known, which is not the model's real name.
    yielded, _, _ = paid_run(("eve",))

    assert f"{PLACEHOLDER}_5" in _names(yielded)
