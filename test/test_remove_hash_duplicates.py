"""remove_hash_match: after a creator's downloads, later copies of a file the
creator already has are deleted (#609).

It deletes files, so most of this is about what it must leave alone. The rows
are written by the app's own code (the scrape's insert, then the download's
update), and the files are real files in a temporary folder.
"""

import asyncio
import contextlib
import logging
import os
import sqlite3
import threading
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.scraper.actions.download.download as download
import ofscraper.db.operations as operations
import ofscraper.utils.hash as hash_util
import ofscraper.utils.settings as settings
from ofscraper.classes.of.media import Media
from ofscraper.classes.of.posts import Post
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.db.operations_.media import batch_mediainsert, mark_media_as_downloaded

MODEL_ID = 12345
OTHER_MODEL = 54321
USERNAME = "a-creator"
PICTURE = b"the same picture"


@pytest.fixture
def env(monkeypatch, tmp_path):
    real = settings.get_settings()
    stub = SimpleNamespace(**{**dict(real), "hash": True, "allow_dupe_downloads": False})
    monkeypatch.setattr(settings, "get_settings", lambda *a, **k: stub)
    db = tmp_path / "user_data.db"
    # one database for both creators, as a shared `metadata` folder gives
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )
    monkeypatch.setattr(operations, "create_backup", lambda *a, **k: None)
    monkeypatch.setattr(stop, "requested", threading.Event())

    async def create():
        await operations.create_tables(db_path=db)

    asyncio.run(create())
    out = tmp_path / "out"
    out.mkdir()
    return SimpleNamespace(stub=stub, out=out, db=db)


def save(
    env, media_id, post_id, name, content=PICTURE, kind="photo", model_id=MODEL_ID,
    folder=None,
):
    """A download: the scrape's row, the file, and the row marked as saved
    with the file's hash. Returns the file."""
    post = Post(
        {"id": post_id, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""},
        model_id, USERNAME, responsetype="timeline",
    )
    item = Media(
        {"id": media_id, "type": kind, "canView": True,
         "files": {"full": {"url": f"https://cdn.example/{media_id}"}}},
        0, post,
    )
    path = (folder or env.out) / name
    path.write_bytes(content)

    async def go():
        await batch_mediainsert([item], model_id=model_id, username=USERNAME)
        await mark_media_as_downloaded(
            item, model_id=model_id, username=USERNAME, downloaded=True,
            filepath=path, hashdata=hash_util.get_hash(path), size=path.stat().st_size,
        )

    asyncio.run(go())
    return path


def clean(model_id=MODEL_ID):
    return download.remove_downloads_with_hashes(USERNAME, model_id)


def files(env):
    return sorted(path.name for path in env.out.iterdir())


def query(env, sql, params=()):
    with contextlib.closing(sqlite3.connect(env.db)) as conn:
        found = conn.execute(sql, params).fetchall()
        conn.commit()
        return found


def named(env):
    """{(media id, post id): the file its row names}"""
    return {
        (media_id, post_id): os.path.join(directory, filename)
        for media_id, post_id, directory, filename in query(
            env, "SELECT media_id, post_id, directory, filename FROM medias"
        )
    }


def test_a_later_copy_is_deleted_and_the_first_is_kept(env, caplog):
    save(env, 1, 10, "first.jpg")
    copy = save(env, 2, 11, "copy.jpg")
    again = save(env, 3, 12, "again.jpg")
    save(env, 4, 13, "other.jpg", content=b"another picture")

    with caplog.at_level(logging.INFO, logger="shared"):
        removed = clean()

    assert removed == [copy, again]
    assert files(env) == ["first.jpg", "other.jpg"]
    assert "Removed 2 duplicate files of a-creator" in caplog.text
    # a second run finds nothing more
    assert clean() == []
    assert files(env) == ["first.jpg", "other.jpg"]


@pytest.mark.parametrize(
    "setting", [False, None, "false", "False", "0", "no", "off", "", " ", 0, 1, "2"]
)
def test_nothing_is_deleted_unless_the_setting_is_on(env, setting):
    # false records hashes without deleting; null (the default) doesn't hash.
    # From the environment (OFSC_HASHED_DEFAULT) the value is text, and
    # "false" is not a yes
    save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "copy.jpg")
    env.stub.hash = setting

    assert clean() == []
    assert files(env) == ["copy.jpg", "first.jpg"]


@pytest.mark.parametrize("setting", ["true", "True", " TRUE ", "1", "yes", "on"])
def test_true_as_text_turns_it_on(env, setting):
    save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "copy.jpg")
    env.stub.hash = setting

    clean()

    assert files(env) == ["first.jpg"]


@pytest.mark.parametrize("kind, name", [("video", "clip"), ("audio", "sound")])
def test_videos_and_audio_are_cleaned_too(env, kind, name):
    save(env, 1, 10, f"{name}_1", kind=kind)
    save(env, 2, 11, f"{name}_2", kind=kind)

    clean()

    assert files(env) == [f"{name}_1"]


def test_a_file_that_two_posts_share_is_not_deleted(env):
    # one media in two posts: two rows, one file
    save(env, 1, 10, "shared.jpg")
    save(env, 1, 11, "shared.jpg")
    assert len(named(env)) == 2

    assert clean() == []
    assert files(env) == ["shared.jpg"]


def test_a_removed_copy_that_two_posts_share_is_removed_once(env, caplog):
    first = save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "copy.jpg")
    copy = save(env, 2, 12, "copy.jpg")

    with caplog.at_level(logging.WARNING, logger="shared"):
        assert clean() == [copy]

    assert files(env) == ["first.jpg"]
    assert "Could not remove" not in caplog.text
    assert set(named(env).values()) == {str(first)}


def test_the_rows_of_a_removed_copy_name_the_kept_file(env):
    # so the media still has a file: a script run afterwards, the metadata
    # command and a sync to Stash all look for the file its row names
    save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "copy.jpg")
    other = save(env, 3, 12, "other.jpg", content=b"another picture")
    save(env, 2, 11, "copy.jpg", model_id=OTHER_MODEL)

    clean()

    assert query(
        env,
        "SELECT media_id, model_id, directory, filename, downloaded FROM medias"
        " ORDER BY model_id, media_id",
    ) == [
        (1, MODEL_ID, str(env.out), "first.jpg", 1),
        (2, MODEL_ID, str(env.out), "first.jpg", 1),
        (3, MODEL_ID, str(env.out), other.name, 1),
        # another creator's row isn't touched, even one just like the removed
        (2, OTHER_MODEL, str(env.out), "copy.jpg", 1),
    ]


def test_an_empty_file_is_not_taken_for_a_copy(env):
    # two downloads that went wrong have the same hash too
    save(env, 1, 10, "first.jpg", content=b"")
    save(env, 2, 11, "second.jpg", content=b"")

    assert clean() == []
    assert files(env) == ["first.jpg", "second.jpg"]


def test_a_row_that_names_no_creator_is_left_out(env):
    # in a database creators share, such a row could be anyone's: its file
    # is neither removed nor the reason another is
    save(env, 1, 10, "whose.jpg")
    query(env, "UPDATE medias SET model_id = NULL")
    save(env, 2, 11, "mine.jpg")

    assert clean() == []
    assert clean(OTHER_MODEL) == []
    assert files(env) == ["mine.jpg", "whose.jpg"]

    again = save(env, 3, 12, "mine_again.jpg")

    assert clean(OTHER_MODEL) == []
    assert clean() == [again]
    assert files(env) == ["mine.jpg", "whose.jpg"]


def test_a_file_that_changed_since_it_was_saved_is_not_deleted(env):
    # the database still says the two are the same; the files no longer are
    save(env, 1, 10, "first.jpg")
    edited = save(env, 2, 11, "edited.jpg")
    edited.write_bytes(b"edited by hand!!")
    assert edited.stat().st_size == len(PICTURE)

    assert clean() == []
    assert files(env) == ["edited.jpg", "first.jpg"]


def test_another_creators_copy_is_not_deleted(env):
    save(env, 1, 10, "mine.jpg")
    save(env, 2, 11, "theirs.jpg", model_id=OTHER_MODEL)

    assert clean() == []
    assert clean(OTHER_MODEL) == []
    assert files(env) == ["mine.jpg", "theirs.jpg"]

    # nor when this creator has a spare copy of its own to remove
    spare = save(env, 3, 12, "mine_again.jpg")

    assert clean(OTHER_MODEL) == []
    assert clean() == [spare]
    assert files(env) == ["mine.jpg", "theirs.jpg"]


def test_a_copy_of_another_media_type_is_not_deleted(env):
    save(env, 1, 10, "picture.jpg")
    save(env, 2, 11, "clip.mp4", kind="video")
    copy = save(env, 3, 12, "picture_copy.jpg")

    assert clean() == [copy]
    assert files(env) == ["clip.mp4", "picture.jpg"]


def test_the_first_copy_still_there_is_the_one_kept(env):
    gone = save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "second.jpg")
    third = save(env, 3, 12, "third.jpg")
    gone.unlink()

    assert clean() == [third]
    assert files(env) == ["second.jpg"]


def test_another_name_for_the_kept_file_is_left(env):
    first = save(env, 1, 10, "first.jpg")
    link = env.out / "link.jpg"
    try:
        os.link(first, link)
    except OSError:
        pytest.skip("hard links aren't available here")
    save_row_only = save(env, 2, 11, "placeholder.jpg")
    save_row_only.unlink()
    # media 2's row names the link
    os.link(first, save_row_only)

    assert clean() == []
    assert first.is_file() and save_row_only.is_file()


def other_route(folder, name):
    """A second path to `folder` that the path's text doesn't give away."""
    route = folder.parent / name
    try:
        os.symlink(folder, route, target_is_directory=True)
    except OSError:
        try:
            import _winapi

            _winapi.CreateJunction(str(folder), str(route))
        except (ImportError, AttributeError, OSError):
            pytest.skip("no second route to a folder can be made here")
    return route


def test_one_file_reached_by_two_routes_is_not_lost(env, monkeypatch):
    # a share mounted twice: the system doesn't say the two paths are one file
    first = save(env, 1, 10, "first.jpg")
    route = other_route(env.out, "mounted-again")
    try:
        save(env, 2, 11, "first.jpg", folder=route)
        monkeypatch.setattr(hash_util.os.path, "samefile", lambda a, b: False)

        assert clean() == []
        assert files(env) == ["first.jpg"]
        assert first.read_bytes() == PICTURE
    finally:
        os.unlink(route) if os.path.islink(route) else os.rmdir(route)


def test_a_file_in_the_way_of_the_removal_stops_it(env, caplog):
    save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "copy.jpg")
    (env.out / "copy.jpg.duplicate").write_bytes(b"something of the user's")

    with caplog.at_level(logging.WARNING, logger="shared"):
        assert clean() == []

    assert files(env) == ["copy.jpg", "copy.jpg.duplicate", "first.jpg"]
    assert (env.out / "copy.jpg.duplicate").read_bytes() == b"something of the user's"
    assert "Could not remove the duplicate file" in caplog.text


def test_the_copies_allow_dupes_made_of_one_media_are_kept(env):
    # with --allow-dupes a media has a file per post, on purpose
    env.stub.allow_dupe_downloads = True
    save(env, 7, 10, "seven.jpg")
    save(env, 7, 11, "seven_11.jpg")
    repost = save(env, 9, 12, "repost.jpg")

    assert clean() == [repost]
    assert files(env) == ["seven.jpg", "seven_11.jpg"]


@pytest.mark.parametrize("step", ["rename", "unlink"])
def test_a_copy_that_cant_be_deleted_doesnt_stop_the_rest(env, monkeypatch, caplog, step):
    save(env, 1, 10, "first.jpg")
    locked = save(env, 2, 11, "locked.jpg")
    free = save(env, 3, 12, "free.jpg")
    real = getattr(os, step)

    def in_use(path, *to):
        # the first step on the locked file fails: moving it aside, or
        # deleting it once it has been
        if os.path.basename(path) == locked.name + (".duplicate" if to == () else ""):
            if step == "unlink" or not os.path.basename(to[0]) == locked.name:
                raise PermissionError("the file is open in another program")
        return real(path, *to)

    monkeypatch.setattr(hash_util.os, step, in_use)

    with caplog.at_level(logging.WARNING, logger="shared"):
        removed = clean()

    assert removed == [free]
    # still there, under its own name, and its row still names it
    assert files(env) == ["first.jpg", "locked.jpg"]
    assert named(env)[(2, 11)] == str(locked)
    assert "Could not remove the duplicate file" in caplog.text


def test_a_stop_ends_the_removal(env, monkeypatch):
    save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "second.jpg")
    save(env, 3, 12, "third.jpg")
    save(env, 4, 13, "clip_1", kind="video")
    save(env, 5, 14, "clip_2", kind="video")
    delete = hash_util._delete_copy

    def delete_then_stop(kept, path):
        stop.requested.set()
        return delete(kept, path)

    monkeypatch.setattr(hash_util, "_delete_copy", delete_then_stop)

    assert len(clean()) == 1
    assert len(files(env)) == 4


def test_a_run_that_only_saves_text_removes_nothing(env):
    save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "copy.jpg")
    env.stub.text_only = True

    assert clean() == []
    assert files(env) == ["copy.jpg", "first.jpg"]


def run_download(env):
    async def nothing_to_download(username, model_id, medialist, posts):
        return (0, 0, 0, 0, 0)

    async def go():
        return await download.download_process(USERNAME, MODEL_ID, [], [])

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(download, "process_dicts", nothing_to_download)
        return asyncio.run(go())


def test_a_download_run_removes_the_duplicates_when_it_is_done(env):
    save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "copy.jpg")

    assert run_download(env) == (0, 0, 0, 0, 0)
    assert files(env) == ["first.jpg"]


def busy(*args, **kwargs):
    raise sqlite3.OperationalError("database is locked")


def test_a_database_error_doesnt_fail_the_download(env, monkeypatch, caplog):
    save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "copy.jpg")
    monkeypatch.setattr(hash_util, "get_dupe_media_copies", busy)

    with caplog.at_level(logging.WARNING, logger="shared"):
        assert run_download(env) == (0, 0, 0, 0, 0)

    assert files(env) == ["copy.jpg", "first.jpg"]
    assert "Could not look for duplicate files of a-creator" in caplog.text


def test_rows_that_cant_be_updated_dont_fail_the_download(env, monkeypatch, caplog):
    save(env, 1, 10, "first.jpg")
    copy = save(env, 2, 11, "copy.jpg")
    monkeypatch.setattr(hash_util, "point_media_at_kept_files", busy)

    with caplog.at_level(logging.WARNING, logger="shared"):
        assert run_download(env) == (0, 0, 0, 0, 0)

    assert files(env) == ["first.jpg"]
    assert named(env)[(2, 11)] == str(copy)
    assert "still names the duplicate files" in caplog.text


def test_a_stopped_run_removes_nothing(env):
    save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "copy.jpg")
    stop.requested.set()

    run_download(env)

    assert files(env) == ["copy.jpg", "first.jpg"]
