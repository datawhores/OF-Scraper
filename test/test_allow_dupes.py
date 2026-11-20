"""--allow-dupes: media that is in several posts is downloaded once per post.

Off (the default, ALLOW_DUPE_MEDIA unset) a media is downloaded once, by
media id. On, each post gets its own copy: "already downloaded" goes by
(media id, post id), on OnlyFans and Fansly, each copy gets its own file and
database row, Purchased copies are downloaded too, and the metadata command
reads and writes each post's own record.
"""

import asyncio
import contextlib
import logging
import sqlite3
from types import SimpleNamespace

import click
import pytest
from click.testing import CliRunner

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.metadata.manager as metadata_manager
import ofscraper.commands.scraper.actions.download.download as of_download
import ofscraper.commands.scraper.actions.download.managers.alt_download as ad
import ofscraper.commands.scraper.actions.utils.globals as common_globals
import ofscraper.commands.scraper.actions.utils.paths as action_paths
import ofscraper.db.operations as operations
import ofscraper.db.operations_.media as media_ops
import ofscraper.filters.media.filters as filters
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.classes.of.media import Media
from ofscraper.classes.of.posts import Post
from ofscraper.db.operations_.media import batch_mediainsert, mark_media_as_downloaded
from ofscraper.utils.args.parse.arguments.download import allow_dupes_option

from test_fansly_pipeline import (  # noqa: F401  (harness and settings_stub are fixtures)
    MODEL_ID as FANSLY_ID,
    harness,
    page,
    post_dict,
    settings_stub,
)

MODEL_ID = 12345
USERNAME = "a-creator"


# ------------------------------------------------------------------ the switch


@pytest.fixture
def command():
    @click.command()
    @allow_dupes_option
    def cmd(allow_dupe_downloads):
        click.echo(f"{allow_dupe_downloads}")

    return cmd


@pytest.mark.parametrize(
    "argv, expected",
    [
        ([], "None"),
        (["--allow-dupes"], "True"),
        (["--allow-dupe-downloads"], "True"),
        (["-ad"], "True"),
        (["--no-allow-dupes"], "False"),
    ],
)
def test_the_options_parse(command, argv, expected):
    result = CliRunner().invoke(command, argv)
    assert result.exit_code == 0, result.output
    assert result.output.strip() == expected


@pytest.mark.parametrize(
    "env, option, expected",
    [
        (False, None, False),  # the default: off
        (True, None, True),  # ALLOW_DUPE_MEDIA is the default
        (True, False, False),  # --no-allow-dupes overrides it
        (False, True, True),  # --allow-dupes overrides it
    ],
)
def test_the_env_default_and_the_option_make_one_switch(monkeypatch, env, option, expected):
    args = settings.get_args(copy=True)
    args.allow_dupe_downloads = option
    monkeypatch.setattr(read_args, "retriveArgs", lambda: args)
    real = of_env.getattr
    monkeypatch.setattr(
        of_env,
        "getattr",
        lambda key, *a, **k: env if key == "ALLOW_DUPE_MEDIA" else real(key, *a, **k),
    )
    merged = settings.merged_settings()
    assert merged.allow_dupe_downloads is expected
    monkeypatch.setattr(settings, "get_settings", lambda *a, **k: merged)
    assert settings.allow_dupes() is expected


# ------------------------------------------------------------------ OnlyFans


@pytest.fixture
def env(monkeypatch, tmp_path):
    real = settings.get_settings()
    stub = SimpleNamespace(**{
        **dict(real), "force_all": False, "force_model_unique": False,
        "skip_download_script": None, "allow_dupe_downloads": False,
    })
    monkeypatch.setattr(settings, "get_settings", lambda *a, **k: stub)
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    monkeypatch.setattr(filters.separate, "seperate_avatars", lambda m: m)

    async def create():
        await operations.create_tables(db_path=db)

    asyncio.run(create())
    return SimpleNamespace(stub=stub, db=db, out=tmp_path)


def item(media_id, post_id, area="timeline"):
    post = Post(
        {"id": post_id, "postedAt": f"2026-01-0{post_id}T03:04:05+00:00", "text": ""},
        MODEL_ID, USERNAME, responsetype=area,
    )
    return Media(
        {"id": media_id, "type": "photo", "canView": True,
         "files": {"full": {"url": f"https://cdn.example/{media_id}.jpg"}}},
        0, post,
    )


def todo(items):
    """The media a download run would fetch: the scrape saves the rows, the
    duplicates are dropped and what's already downloaded is left out."""
    async def save():
        # inside a running loop: called outside one, it opens a loop it never closes
        await batch_mediainsert(items, model_id=MODEL_ID, username=USERNAME)

    asyncio.run(save())
    media = filters.dupefiltermedia(items)
    media = filters.previous_download_filter(media, username=USERNAME, model_id=MODEL_ID)
    return sorted((m.id, m.post_id) for m in media)


def mark(ele, name):
    asyncio.run(
        mark_media_as_downloaded(
            ele, model_id=MODEL_ID, username=USERNAME, downloaded=True,
            filename=name, directory="out",
        )
    )


def rows(env):
    with contextlib.closing(sqlite3.connect(env.db)) as conn:
        return sorted(
            conn.execute("SELECT media_id, post_id, downloaded, filename FROM medias")
        )


def test_off_downloads_a_media_once(env):
    items = [item(7, 1), item(7, 2)]
    assert todo(items) == [(7, 1)]
    mark(items[0], "a.jpg")
    # every row of the media counts as downloaded, as before
    assert rows(env) == [(7, 1, 1, "a.jpg"), (7, 2, 1, "a.jpg")]
    assert todo(items) == []


def test_on_downloads_a_copy_per_post_and_a_later_run_fetches_the_missing_one(env):
    env.stub.allow_dupe_downloads = True
    items = [item(7, 1), item(7, 2), item(8, 2)]
    assert todo(items) == [(7, 1), (7, 2), (8, 2)]
    mark(items[0], "a.jpg")
    mark(items[2], "b.jpg")
    # only the post whose copy was saved is marked
    assert rows(env) == [(7, 1, 1, "a.jpg"), (7, 2, None, None), (8, 2, 1, "b.jpg")]
    assert todo(items) == [(7, 2)]
    mark(items[1], "a_7.jpg")
    assert todo(items) == []


def test_on_force_model_unique_reads_pairs_of_this_creator(env):
    env.stub.allow_dupe_downloads = True
    env.stub.force_model_unique = True
    items = [item(7, 1), item(7, 2)]
    todo(items)
    mark(items[0], "a.jpg")
    assert filters.downloaded_media_ids(username=USERNAME, model_id=MODEL_ID) == {(7, 1)}
    assert filters.downloaded_media_ids(username=USERNAME, model_id=MODEL_ID + 1) == set()


def test_off_messages_and_purchased_download_once(env):
    assert todo([item(7, 2, "paid"), item(7, 1, "message")]) == [(7, 1)]


def test_on_the_purchased_copy_is_downloaded_too(env):
    env.stub.allow_dupe_downloads = True
    assert todo([item(7, 2, "paid"), item(7, 1, "message")]) == [(7, 1), (7, 2)]


def test_on_purchased_copy_of_a_media_downloaded_earlier_is_downloaded(env):
    env.stub.allow_dupe_downloads = True
    message = item(7, 1, "message")
    todo([message])
    mark(message, "a.jpg")
    # a later run that sees the purchase: its copy hasn't been saved yet
    assert todo([item(7, 2, "paid")]) == [(7, 2)]


# ------------------------------------------------------------------ records


class FakePlaceholder:
    def __init__(self, path):
        self.trunicated_filepath = path
        self.trunicated_filename = path.name
        self.trunicated_filedir = path.parent
        self.size = None

    async def init(self, create=False):
        return self


def first_post_saved(env):
    """Two posts share media 7; only post 1's copy is saved, as caption.jpg."""
    env.stub.allow_dupe_downloads = True
    items = [item(7, 1), item(7, 2)]
    todo(items)
    saved = env.out / "caption.jpg"
    saved.write_bytes(b"post 1's copy")
    asyncio.run(
        mark_media_as_downloaded(
            items[0], model_id=MODEL_ID, username=USERNAME, downloaded=True,
            filename=saved.name, directory=str(env.out),
        )
    )
    return items


@pytest.mark.parametrize("mode, downloaded", [("check", None), ("update", 0)])
def test_on_metadata_reads_this_posts_record(env, monkeypatch, mode, downloaded):
    # post 2's copy isn't on disk: it must not take post 1's record or file
    items = first_post_saved(env)
    env.stub.metadata = mode
    env.stub.hash = False
    monkeypatch.setattr(common_globals, "log", logging.getLogger("shared"))

    async def run():
        await metadata_manager.MetaDataManager()._change_metadata(
            None, items[1], USERNAME, MODEL_ID,
            placeholderObj=FakePlaceholder(env.out / "caption_7.jpg"),
        )

    asyncio.run(run())
    assert rows(env) == [(7, 1, 1, "caption.jpg"), (7, 2, downloaded, "caption_7.jpg")]


def test_on_the_silent_recheck_finds_this_posts_file(env):
    items = first_post_saved(env)

    async def saved(ele):
        return await of_download._saved_path(ele, model_id=MODEL_ID, username=USERNAME)

    assert asyncio.run(saved(items[0])) == env.out / "caption.jpg"
    assert asyncio.run(saved(items[1])) is None


def test_on_own_file_reads_the_callers_database_without_writing(env, monkeypatch, tmp_path):
    items = first_post_saved(env)
    other = tmp_path / "elsewhere" / "user_data.db"
    # the database path goes by the run's username, which keeps its case;
    # a media's username is lowercased
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: env.db if model_username == "A-Creator" else other,
    )
    assert items[0].username == "a-creator"
    assert action_paths._own_file(items[0], "A-Creator", MODEL_ID) == env.out / "caption.jpg"
    # no database for that creator: none is made
    assert action_paths._own_file(items[0], "another", MODEL_ID) is None
    assert not other.exists() and not other.parent.exists()


# ------------------------------------------------------------------ files


@pytest.fixture
def files(monkeypatch, tmp_path):
    """moveHelper with the switch on and a fake record of saved files."""
    monkeypatch.setattr(action_paths.config_data, "get_filename_collision", lambda: "media_id")
    monkeypatch.setattr(
        settings, "get_settings", lambda *a, **k: SimpleNamespace(allow_dupe_downloads=True)
    )
    recorded = {}
    monkeypatch.setattr(
        media_ops, "get_media_post_files_downloaded", lambda media_id=None, **k: dict(recorded)
    )
    return recorded


def move(tmp_path, ele, data=b"the same media"):
    temp = tmp_path / f"dl_{ele.post_id}.part"
    temp.write_bytes(data)
    return action_paths.moveHelper(
        temp, tmp_path / "caption.jpg", ele, username=USERNAME, model_id=MODEL_ID
    )


def copy_of(post_id):
    return SimpleNamespace(id=7, post_id=post_id, model_id=MODEL_ID, username=USERNAME)


def test_on_two_posts_copies_get_their_own_files(tmp_path, files):
    first = move(tmp_path, copy_of(1))
    files[(7, 1)] = (str(first.parent), first.name)
    second = move(tmp_path, copy_of(2))
    assert first != second
    assert first.read_bytes() == second.read_bytes() == b"the same media"


def test_on_a_copy_downloaded_again_keeps_its_file(tmp_path, files):
    first = move(tmp_path, copy_of(1))
    files[(7, 1)] = (str(first.parent), first.name)
    second = move(tmp_path, copy_of(2))
    files[(7, 2)] = (str(second.parent), second.name)
    # --force-all: each copy finds its own file, nothing new is written
    assert [move(tmp_path, copy_of(2)), move(tmp_path, copy_of(1))] == [second, first]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["caption.jpg", "caption_7.jpg"]


def test_on_overwrite_mode_leaves_another_posts_copy_alone(tmp_path, files, monkeypatch):
    monkeypatch.setattr(action_paths.config_data, "get_filename_collision", lambda: "overwrite")
    first = move(tmp_path, copy_of(1))
    files[(7, 1)] = (str(first.parent), first.name)
    second = move(tmp_path, copy_of(2), b"the same media, a larger copy")
    assert second != first
    assert first.read_bytes() == b"the same media"


def test_drm_merge_temp_file_is_per_post(monkeypatch):
    names = []

    class Stop(Exception):
        pass

    class FakeTemp:
        def __init__(self, ele, name):
            names.append(name)

        async def init(self):
            raise Stop()

    monkeypatch.setattr(placeholder, "tempFilePlaceholder", FakeTemp)
    manager = ad.AltDownloadManager(ctx=SimpleNamespace())
    for post_id in (1, 2):
        with pytest.raises(Stop):
            asyncio.run(
                manager._handle_result_alt(None, copy_of(post_id), None, None, USERNAME, MODEL_ID)
            )
    assert names[0] != names[1]


# ------------------------------------------------------------------ Fansly


def message(pid, media_ids):
    out = post_dict(pid, media_ids, from_user=FANSLY_ID)
    out["responseType"] = "message"
    return out


def downloads(harness):
    """Record which post each download was for."""
    got = []

    async def hook(ele):
        got.append((ele.id, ele.post_id))

    harness.on_download = {mid: hook for mid in range(100, 200)}
    return got


def test_fansly_off_downloads_a_media_once(harness):
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [101])), page(post_dict(2, [101, 102]))]
    got = downloads(harness)
    harness.run()
    assert got == [(101, 1), (102, 2)]


def test_fansly_on_downloads_a_copy_per_post(harness, settings_stub):
    settings_stub.allow_dupe_downloads = True
    harness.areas = ["Timeline"]
    harness.pages["Timeline"] = [page(post_dict(1, [101])), page(post_dict(2, [101, 102]))]
    got = downloads(harness)
    harness.run()
    assert got == [(101, 1), (101, 2), (102, 2)]


def test_fansly_on_a_later_run_fetches_the_missing_copy(harness, settings_stub):
    settings_stub.allow_dupe_downloads = True
    harness.areas = ["Timeline"]
    harness.downloaded = {(101, 1)}
    harness.pages["Timeline"] = [page(post_dict(1, [101])), page(post_dict(2, [101]))]
    got = downloads(harness)
    harness.run()
    assert got == [(101, 2)]


def messages_and_purchased(harness):
    harness.areas = ["Messages", "Purchased"]
    harness.pages["Messages"] = [page(message(1, [101]))]
    harness.pages["Purchased"] = [page(post_dict(2, [101]))]
    return downloads(harness)


def test_fansly_off_messages_and_purchased_download_once(harness):
    got = messages_and_purchased(harness)
    harness.run()
    assert got == [(101, 1)]


def test_fansly_on_the_purchased_copy_is_downloaded_too(harness, settings_stub):
    settings_stub.allow_dupe_downloads = True
    got = messages_and_purchased(harness)
    harness.run()
    assert got == [(101, 1), (101, 2)]


def test_fansly_on_purchased_copy_of_a_media_downloaded_earlier_is_downloaded(
    harness, settings_stub
):
    settings_stub.allow_dupe_downloads = True
    harness.downloaded = {(101, 1)}
    got = messages_and_purchased(harness)
    harness.run()
    assert got == [(101, 2)]
