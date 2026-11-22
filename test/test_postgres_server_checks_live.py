"""Two checks on a real PostgreSQL server that #634 lists: two scrapers
writing to one database at the same time, and remove_hash_match's queries
(#619).

Skipped unless OFSC_TEST_POSTGRES_URL names a server the tests may use (see
test_db_postgres_live.py). Each test works in schemas of its own and drops
them.
"""

import asyncio
import contextlib
import multiprocessing
import os
import queue
import sys
import time
import traceback

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.db.operations as operations
import ofscraper.db.operations_.media as media
import ofscraper.db.operations_.posts as posts
import ofscraper.db.operations_.profile as profile
import ofscraper.db.postgres as postgres
import ofscraper.sites as sites
from ofscraper.commands.scraper.actions.download.download import HASH_MEDIA_TYPES

URL = os.environ.get("OFSC_TEST_POSTGRES_URL", "")
if not URL:
    pytest.skip(
        "needs a PostgreSQL server: set OFSC_TEST_POSTGRES_URL", allow_module_level=True
    )

# with a server named, a missing driver is a failure, not a skip
import psycopg  # noqa: E402,F401

from test.db_scenario import NAMES, ONE, item, plain, post, table_rows  # noqa: E402
from test.test_db_postgres_live import CREATOR, drop, new_schema, pg, start  # noqa: E402,F401
from test.test_remove_hash_duplicates import (  # noqa: E402,F401  (env is a fixture)
    MODEL_ID,
    OTHER_MODEL,
    USERNAME,
    clean,
    env,
    files,
    save,
)


def rows(table, folder=None, leave_out=(), **who):
    """A table's rows as plain data, without the row ids and in one order.
    A file's folder is named from `folder`."""
    found = []
    for row in table_rows(table, read_only=True, **(who or CREATOR)):
        row = {k: v for k, v in row.items() if k != "id" and k not in leave_out}
        if folder and row.get("directory"):
            row["directory"] = os.path.relpath(row["directory"], folder)
        found.append(plain(row))
    return sorted(found, key=repr)


# --- two scrapers writing to one database at the same time ---

ROUNDS = 10


async def one_scraper(writer, barrier=None):
    """What a scraper run of the creator writes, round by round. The two
    writers save posts 0-5 and 3-8 of each round: half of each one's posts
    and media are the other's too. With a barrier, each round starts at
    once in both."""
    await operations.table_init_create(**CREATOR)
    for round in range(ROUNDS):
        if barrier:
            # the first wait also covers the other program's start
            barrier.wait(timeout=120 if round == 0 else None)
        ids = range(round * 100 + writer * 3, round * 100 + writer * 3 + 6)
        await posts.make_post_table_changes([post(i) for i in ids], from_api=True, **CREATOR)
        found = [item(i * 10 + n, i) for i in ids for n in (0, 1)]
        await media.batch_mediainsert(found, **CREATOR)
        for each in found[::2]:
            await media.mark_media_as_downloaded(
                each, filename=f"{each.id}.jpg", directory="/files",
                downloaded=True, hashdata=f"hash {each.id}", size=5, **CREATOR,
            )
        await profile.write_profile_table(**CREATOR)


def scraper_process(writer, schema, barrier, results):
    """One scraper run in a program of its own, as a second scraper is."""
    sys.argv = sys.argv[:1]
    os.environ[postgres.URL_KEY] = URL
    sites.current_site = lambda: schema
    try:
        asyncio.run(one_scraper(writer, barrier))
        results.put((writer, None))
    except BaseException:
        barrier.abort()
        results.put((writer, traceback.format_exc()))
    finally:
        postgres.POSTGRES.shutdown()


def reports(programs, results):
    """{writer: its error or None}. A program that ended without saying
    (a crash, a failed import) fails the test with its exit code."""
    found = {}
    deadline = time.monotonic() + 180
    while len(found) < len(programs):
        try:
            writer, error = results.get(timeout=5)
            found[writer] = error
            continue
        except queue.Empty:
            pass
        for writer, program in enumerate(programs):
            if writer not in found and program.exitcode is not None:
                # a report sent just before it ended may still be on its way
                with contextlib.suppress(queue.Empty):
                    late, error = results.get(timeout=1)
                    found[late] = error
                if writer not in found:
                    pytest.fail(
                        f"writer {writer} ended with exit code {program.exitcode}"
                        " without reporting"
                    )
        if len(found) < len(programs) and time.monotonic() > deadline:
            pytest.fail(f"no report from writers {set(range(len(programs))) - set(found)}")
    return found


def everything():
    return {
        "medias": rows("medias"),
        "posts": rows("posts"),
        # the dates are the time each program ran
        "profiles": rows("profiles", leave_out=("first_seen_at", "last_seen_at")),
        "models": rows("models"),
    }


def test_two_scrapers_writing_at_once_save_what_one_after_the_other_saves(
    pg, monkeypatch
):
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2, timeout=30)
    results = context.Queue()
    programs = [
        context.Process(target=scraper_process, args=(writer, pg, barrier, results))
        for writer in (0, 1)
    ]
    try:
        for program in programs:
            program.start()
        errors = reports(programs, results)
    finally:
        for program in programs:
            if program.pid is None:
                continue
            program.join(timeout=30)
            if program.is_alive():
                program.terminate()
    assert errors == {0: None, 1: None}, "\n".join(filter(None, errors.values()))
    at_once = everything()

    serial = new_schema()
    try:
        monkeypatch.setattr(sites, "current_site", lambda: serial)
        for writer in (0, 1):
            asyncio.run(one_scraper(writer))
        one_after_the_other = everything()
    finally:
        drop(serial)

    assert at_once == one_after_the_other
    # each post and media once
    post_ids = {r * 100 + n for r in range(ROUNDS) for n in range(9)}
    assert sorted(row["post_id"] for row in at_once["posts"]) == sorted(post_ids)
    assert len(at_once["medias"]) == 2 * len(post_ids)
    assert at_once["profiles"] == [{"user_id": ONE, "username": NAMES[ONE]}]
    assert at_once["models"] == [{"model_id": ONE}]


# --- remove_hash_match (#619) ---


def remove_hash_match(env, folder):
    """Saves a creator's files and removes the duplicates: what the two
    queries found and what was left."""
    env.out = folder
    folder.mkdir()
    save(env, 1, 10, "first.jpg")
    save(env, 2, 11, "copy.jpg")
    # one media in two posts: two rows, one file
    save(env, 2, 12, "copy.jpg")
    save(env, 3, 13, "other.jpg", content=b"another picture")
    # the same content as another type: not a copy
    save(env, 4, 14, "clip", kind="video")
    # another creator's copy
    save(env, 5, 15, "theirs.jpg", model_id=OTHER_MODEL)
    who = dict(model_id=MODEL_ID, username=USERNAME)
    copies = media.get_dupe_media_copies(mediatypes=HASH_MEDIA_TYPES, **who)
    removed = clean()
    return {
        "copies": [
            plain(dict(row, directory=os.path.relpath(row["directory"], folder)))
            for row in copies
        ],
        "removed": [path.name for path in removed],
        "files": files(env),
        "rows": rows("medias", folder, **who),
    }


def test_remove_hash_match_does_on_a_server_what_it_does_on_sqlite(
    env, pg, monkeypatch, tmp_path
):
    with monkeypatch.context() as patch:
        patch.delenv(postgres.URL_KEY, raising=False)
        on_sqlite = remove_hash_match(env, tmp_path / "sqlite")
    start(model_id=MODEL_ID, username=USERNAME)
    on_postgres = remove_hash_match(env, tmp_path / "postgres")

    assert on_postgres == on_sqlite
    # and it is what remove_hash_match is for
    assert [row["filename"] for row in on_sqlite["copies"]] == [
        "first.jpg", "copy.jpg", "copy.jpg", "clip",
    ]
    assert on_sqlite["removed"] == ["copy.jpg"]
    assert on_sqlite["files"] == ["clip", "first.jpg", "other.jpg", "theirs.jpg"]
    assert sorted(
        (row["model_id"], row["media_id"], row["post_id"], row["filename"])
        for row in on_sqlite["rows"]
    ) == [
        (MODEL_ID, 1, 10, "first.jpg"),
        (MODEL_ID, 2, 11, "first.jpg"),
        (MODEL_ID, 2, 12, "first.jpg"),
        (MODEL_ID, 3, 13, "other.jpg"),
        (MODEL_ID, 4, 14, "clip"),
        (OTHER_MODEL, 5, 15, "theirs.jpg"),
    ]
