"""Undoing a permanent skip by skip_download_script (#354).

A file the script skipped for good (`skip-permanent`, #351) is saved as
downloaded with no file and `medias.skip_permanent = 1`. There are two ways
to undo that:

- the run flag `--retry-permanent-skips` offers those files of the run's
  creators to the script again;
- `ofscraper db --unmark-permanent-skips` sets the selected ones back to not
  downloaded, so the next normal run asks the script again.

Checks, from the issue:

1. Given a permanently skipped file, when a scrape runs with the flag, the
   script is asked again: the file downloads if it says keep, and stays
   permanently skipped if it says `skip-permanent`. A plain skip counts as
   skipped, and the next run asks again.
2. Given the db command with a creator, post or media filter, only the
   matching permanent skips are un-marked, and the next normal run asks the
   script about them again.
3. Given real downloads and rows that aren't permanent skips, neither the
   flag nor the command changes them.
4. Given no flag and no command, permanent skips stay skipped as before.

The download runs use the real Media, download managers and SQLite database
of test_size_limit_skip.py, against a local server.
"""

import asyncio
import contextlib
import logging
import sqlite3
import time
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.commands.db as db_mod
import ofscraper.commands.scraper.actions.download.managers.downloadmanager as dm
import ofscraper.data.api.common.after as after_mod
import ofscraper.utils.settings as settings
from ofscraper.classes.of.media import Media
from ofscraper.classes.of.posts import Post
from ofscraper.db.operations_.media import unmark_permanent_skips
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager
from ofscraper.scripts.skip_download_script import SKIP_PERMANENT
from test_size_limit_skip import (  # noqa: F401  (env is a fixture)
    BODY,
    MODEL_ID,
    USERNAME,
    Server,
    counts,
    env,
    files,
    run_async,
)

OTHER_MODEL = 54321

# ------------------------------------------------------------- helpers


def item(base, media_id=7, post_id=1, model_id=MODEL_ID):
    post = Post(
        {"id": post_id, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""},
        model_id, USERNAME, responsetype="timeline",
    )
    return Media(
        {"id": media_id, "type": "photo", "canView": True,
         "files": {"full": {"url": f"{base}/file{media_id}.jpg"}}},
        0, post,
    )


def state(env, media_id, model_id=MODEL_ID):
    """(downloaded, skip_permanent) of every row of the media, by post."""
    with contextlib.closing(sqlite3.connect(env.db)) as conn:
        return conn.execute(
            "SELECT downloaded, skip_permanent FROM medias"
            " WHERE media_id = ? AND model_id = ? ORDER BY post_id",
            [media_id, model_id],
        ).fetchall()


def all_rows(env):
    with contextlib.closing(sqlite3.connect(env.db)) as conn:
        return conn.execute(
            "SELECT * FROM medias ORDER BY model_id, media_id, post_id"
        ).fetchall()


def runs(env, monkeypatch, plan, ids=(7,)):
    """One download run per (flag, answer) in `plan`: --retry-permanent-skips
    on or off, and the script's answer for every file. Each run has new
    Media for the media in `ids`, as a new scrape makes."""
    asked = []
    answer = {}

    async def script(total, ele):
        asked.append(ele.id)
        return answer["now"]

    monkeypatch.setattr(dm, "skip_download_script", script)
    env.stub.skip_download_script = "a-script"
    results = []

    async def go():
        async with Server() as srv:
            async with sessionManager(
                retries=1, wait_min=0, wait_max=0, log=logging.getLogger("test")
            ) as c:
                for flag, now in plan:
                    env.stub.retry_permanent_skips = flag
                    answer["now"] = now
                    asked.clear()
                    counted, todo = await run_async(
                        env, [item(srv.base, i) for i in ids], c
                    )
                    results.append(SimpleNamespace(
                        counted=counted, todo=sorted(e.id for e in todo),
                        asked=sorted(asked), state={i: state(env, i) for i in ids},
                        files=files(env),
                    ))

    asyncio.run(go())
    return results


PERMANENT = [(1, 1)]
NOT_DOWNLOADED = [(None, None)]
DOWNLOADED = [(1, None)]

# ------------------------------------------------------------- 1. the run flag


def test_flag_asks_again_and_a_kept_file_downloads(env, monkeypatch):
    skip, normal, retry, after = runs(env, monkeypatch, [
        (False, SKIP_PERMANENT), (False, False), (True, False), (False, False),
    ])
    assert skip.state[7] == PERMANENT
    # without the flag it isn't asked about (check 4)
    assert normal.asked == [] and normal.todo == []
    # with it, the script is asked again and now keeps it
    assert retry.asked == [7]
    assert retry.counted == counts(photo_count=1)
    assert retry.state[7] == DOWNLOADED
    assert retry.files == [BODY]
    # a real download now: the next run leaves it alone
    assert after.asked == [] and after.todo == []


def test_flag_and_skip_permanent_again_stays_skipped(env, monkeypatch):
    skip, retry, normal = runs(env, monkeypatch, [
        (False, SKIP_PERMANENT), (True, SKIP_PERMANENT), (False, False),
    ])
    assert retry.asked == [7]
    assert retry.counted == counts(forced_skipped=1)
    assert retry.state[7] == PERMANENT
    assert retry.files == []
    assert normal.asked == [] and normal.todo == []


def test_flag_and_plain_skip_counts_skipped_and_asks_next_run(env, monkeypatch):
    skip, retry, normal = runs(env, monkeypatch, [
        (False, SKIP_PERMANENT), (True, True), (False, False),
    ])
    assert retry.asked == [7]
    assert retry.counted == counts(forced_skipped=1)
    # a skip for this run only: not a permanent skip any more
    assert retry.state[7] == NOT_DOWNLOADED
    assert retry.files == []
    # so the next normal run asks again, and the file downloads
    assert normal.asked == [7]
    assert normal.counted == counts(photo_count=1)
    assert normal.state[7] == DOWNLOADED


def test_flag_turns_on_a_full_scan(monkeypatch):
    # the permanently skipped files can be in posts older than the last scan
    stub = SimpleNamespace(
        after=None, incremental_downloads=True, actions=["download"],
        retry_permanent_skips=False,
    )
    monkeypatch.setattr(settings, "get_settings", lambda *a, **k: stub)
    monkeypatch.setattr(after_mod, "read_full_after_scan_check", lambda *a: False)
    assert after_mod.get_after_pre_checks(MODEL_ID, "timeline") is None
    stub.retry_permanent_skips = True
    assert after_mod.get_after_pre_checks(MODEL_ID, "timeline") == 0


# ------------------------------------------------------------- 3. other rows


def test_flag_leaves_real_downloads_and_other_rows_alone(env, monkeypatch):
    # 7: permanently skipped, 8: downloaded, 9: saved as downloaded with no
    # file but not by the script (a known bad link, say)
    (first,) = runs(env, monkeypatch, [(False, False)], ids=(8,))
    assert first.state[8] == DOWNLOADED
    (skip,) = runs(env, monkeypatch, [(False, SKIP_PERMANENT)], ids=(7,))
    with contextlib.closing(sqlite3.connect(env.db)) as conn:
        conn.execute(
            "INSERT INTO medias (media_id, post_id, api_type, media_type,"
            " downloaded, model_id) VALUES (9, 1, 'Timeline', 'Images', 1, ?)",
            [MODEL_ID],
        )
        conn.commit()
    before = {i: state(env, i) for i in (8, 9)}

    (retry,) = runs(env, monkeypatch, [(True, False)], ids=(7, 8, 9))

    # only the permanent skip is offered to the script again
    assert retry.asked == [7] and retry.todo == [7]
    assert retry.state[7] == DOWNLOADED
    assert {i: retry.state[i] for i in (8, 9)} == before


# ------------------------------------------------------------- 2. the db command


ALL_AREAS = ("Timeline", "Pinned", "Archived", "Messages", "Streams",
             "Highlights", "Stories")


def parse_db(*cli):
    """The args `ofscraper db <cli>` gives the app, from the real parser."""
    from ofscraper.utils.args.main import AutoDotDict
    from ofscraper.utils.args.parse.commands.db import db

    ctx = db.make_context("db", list(cli))
    params, _ = db.invoke(ctx)
    return AutoDotDict(params)


@pytest.fixture
def table(env, monkeypatch):
    """`ofscraper db` over the test database: rows of two creators. The
    table it prints is recorded instead of printed."""
    rows = [
        # (model_id, media_id, post_id, downloaded, skip_permanent, filename)
        (MODEL_ID, 1, 100, 1, 1, None),
        (MODEL_ID, 1, 101, 1, 1, None),  # the same media in a second post
        (MODEL_ID, 2, 100, 1, 1, None),
        (MODEL_ID, 3, 102, 1, 1, None),
        (MODEL_ID, 4, 102, 1, None, "real.jpg"),  # a real download
        (MODEL_ID, 5, 102, 1, None, None),  # downloaded with no file, not by the script
        (MODEL_ID, 6, 102, None, None, None),  # not downloaded
        (OTHER_MODEL, 1, 100, 1, 1, None),  # another creator's permanent skip
    ]
    with contextlib.closing(sqlite3.connect(env.db)) as conn:
        conn.executemany(
            "INSERT INTO medias (model_id, media_id, post_id, downloaded,"
            " skip_permanent, filename, api_type, media_type, link, linked,"
            " preview, unlocked, created_at, posted_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 'Timeline', 'Images', NULL, 0, 0, 1,"
            " '2026-01-02T03:04:05+00:00', '2026-01-02T03:04:05+00:00')",
            rows,
        )
        conn.commit()

    args = {}
    for name, value in {
        "posted_before": None, "posted_after": None, "created_before": None,
        "created_after": None, "mediatypes": ["Audios", "Videos", "Images"],
        "db_asc": False, "db_sort": None, "export": None, "max_post_count": 0,
    }.items():
        setattr(env.stub, name, value)
    monkeypatch.setattr(settings, "get_args", lambda *a, **k: args["now"])
    monkeypatch.setattr(db_mod, "time", SimpleNamespace(
        sleep=lambda s: None, strptime=time.strptime))
    shown = []
    monkeypatch.setattr(
        db_mod.DBManager, "print_dictionary_table",
        lambda self: shown.append(sorted({m["media_id"] for m in self.media})),
    )

    def run(*cli, model_id=MODEL_ID, areas=ALL_AREAS):
        """`ofscraper db <cli>` for one creator: the options are parsed from
        the command line as the app parses them. The areas are picked
        later in the app (select_areas), so they're given here."""
        args["now"] = parse_db(*cli)
        args["now"].download_area = list(areas)
        # the command's database reads run on the current loop: one that's
        # closed afterwards
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            db_mod.DBManager(USERNAME, model_id).print_media()
        finally:
            loop.close()
            asyncio.set_event_loop(None)
        return shown.pop()

    return SimpleNamespace(run=run, rows=rows)


def marked(env):
    with contextlib.closing(sqlite3.connect(env.db)) as conn:
        return conn.execute(
            "SELECT model_id, media_id, post_id FROM medias"
            " WHERE skip_permanent = 1 ORDER BY model_id, media_id, post_id"
        ).fetchall()


def test_db_command_without_the_option_changes_nothing(env, table):
    before = all_rows(env)
    assert table.run() == [1, 2, 3, 4, 5, 6]
    assert all_rows(env) == before


def test_db_command_unmarks_only_the_creators_permanent_skips(env, table):
    before = all_rows(env)
    # the creator's permanent skips are shown, then un-marked
    assert table.run("--unmark-permanent-skips") == [1, 2, 3]
    assert marked(env) == [(OTHER_MODEL, 1, 100)]
    for media_id in (1, 2, 3):
        assert set(state(env, media_id)) == {(None, None)}
    # every other row is as it was (check 3)
    unchanged = [r for r in before if not (r[-1] == 1 and r[-2] == MODEL_ID)]
    after = all_rows(env)
    assert [r for r in after if r in unchanged] == unchanged


@pytest.mark.parametrize("cli", [["--post-id", "100"], ["-pd", "100"]])
def test_db_command_post_filter(env, table, cli):
    # post 100 has media 1 and 2. Media 1's download state is kept on all of
    # its rows, so its row in post 101 is un-marked too
    assert table.run("--unmark-permanent-skips", *cli) == [1, 2]
    assert marked(env) == [(MODEL_ID, 3, 102), (OTHER_MODEL, 1, 100)]


@pytest.mark.parametrize("ids", ["3,4,5,6", "3, 4 5,6"])
def test_db_command_media_filter(env, table, ids):
    assert table.run("--unmark-permanent-skips", "--media-id", ids) == [3]
    assert marked(env) == [
        (MODEL_ID, 1, 100), (MODEL_ID, 1, 101), (MODEL_ID, 2, 100),
        (OTHER_MODEL, 1, 100),
    ]
    assert state(env, 4) == DOWNLOADED and state(env, 5) == DOWNLOADED
    assert state(env, 6) == NOT_DOWNLOADED


def test_db_command_on_a_database_from_before_the_column(env, table):
    with contextlib.closing(sqlite3.connect(env.db)) as conn:
        conn.execute("ALTER TABLE medias DROP COLUMN skip_permanent")
        conn.commit()
    before = all_rows(env)
    # one area: reading all of them at once needs the column already
    assert table.run("--unmark-permanent-skips", areas=["Timeline"]) == []
    assert all_rows(env) == before


# the id filters of plain `ofscraper db` (#363): each value is a whole id, not
# its characters, compared with the stored numbers


@pytest.mark.parametrize("cli, shown", [
    (["--post-id", "102"], [3, 4, 5, 6]),
    (["--post-id", "101"], [1]),
    (["--post-id", "100,102"], [1, 2, 3, 4, 5, 6]),
    (["--media-id", "4"], [4]),
    (["--media-id", "1,6"], [1, 6]),
    (["--post-id", "102", "--media-id", "6"], [6]),
    # "10" isn't post 100 or 101, though its characters are in them
    (["--post-id", "10"], []),
])
def test_db_command_id_filters(env, table, cli, shown):
    before = all_rows(env)
    assert table.run(*cli) == shown
    assert all_rows(env) == before


def test_db_command_id_filters_parse_whole_ids():
    args = parse_db("--post-id", "123", "--media-id", "45, 46")
    assert args.post_id == {123}
    assert args.media_id == {45, 46}
    # not given: no filter
    args = parse_db()
    assert args.post_id is None and args.media_id is None


# values that aren't ids, and values with no id in them: a usage error, never
# "no filter" (with --unmark-permanent-skips that would un-mark every row).
# "²" passes str.isdigit() but int() can't read it; "½" is numeric, not a digit
# "9" * 5000 is past int()'s digit limit (about 4300): isdecimal() takes it,
# int() raises
BAD_IDS = [",", " ", "", " , ", "abc", "4,x", "²", "4,²", "½", "-4", "+4", "1_000",
           "9" * 5000, "4," + "9" * 5000]


@pytest.mark.parametrize("value, ids", [
    ("١٢٣", {123}),  # Arabic-Indic digits
    ("１２", {12}),  # full-width digits
    ("١٢٣,4", {123, 4}),
])
def test_db_command_id_filters_take_decimal_digits_of_any_script(value, ids):
    args = parse_db("--post-id", value, "--media-id", value)
    assert args.post_id == ids and args.media_id == ids


@pytest.mark.parametrize("option", ["--post-id", "--media-id"])
@pytest.mark.parametrize(
    "value", BAD_IDS, ids=lambda v: v if len(v) < 20 else f"{len(v)}-chars"
)
def test_db_command_id_filters_reject_bad_values(option, value):
    import click

    with pytest.raises(click.BadParameter):
        parse_db(option, value)


@pytest.mark.parametrize("option", ["--post-id", "-pd", "--media-id"])
@pytest.mark.parametrize("value", [",", "", "²", "½", "9" * 5000], ids=["comma", "empty", "sup2", "half", "5000-digits"])
def test_unmark_with_a_bad_id_filter_changes_nothing(env, table, option, value):
    import click

    before = all_rows(env)
    with pytest.raises(click.BadParameter):
        table.run("--unmark-permanent-skips", option, value)
    assert all_rows(env) == before


@pytest.mark.parametrize("value, message", [
    (",", "no id given"), ("²", "is not an id"), ("½", "is not an id"),
    ("9" * 5000, "is not an id"),
], ids=["comma", "sup2", "half", "5000-digits"])
def test_bad_id_filter_is_a_usage_error_from_the_command_line(capsys, value, message):
    # run as click runs a command line: a usage error (exit code 2) with the
    # option named, not a traceback
    from ofscraper.utils.args.parse.commands.db import db

    with pytest.raises(SystemExit) as exit_:
        db.main(
            ["--unmark-permanent-skips", "--post-id", value],
            prog_name="ofscraper db", standalone_mode=True,
        )
    assert exit_.value.code == 2
    err = capsys.readouterr().err
    assert "Usage:" in err and "--post-id" in err and message in err
    assert "Traceback" not in err


def test_after_the_db_command_the_next_run_asks_again(env, monkeypatch):
    (skip,) = runs(env, monkeypatch, [(False, SKIP_PERMANENT)])
    assert skip.state[7] == PERMANENT
    # what the db command runs for the rows it selected (the tests above
    # cover the selecting)
    assert asyncio.run(
        unmark_permanent_skips([7], model_id=MODEL_ID, username=USERNAME)
    ) == 1
    assert state(env, 7) == NOT_DOWNLOADED
    (normal,) = runs(env, monkeypatch, [(False, False)])
    assert normal.asked == [7]
    assert normal.state[7] == DOWNLOADED
    assert normal.files == [BODY]


# ------------------------------------------------------------- options


def test_options_parse():
    from ofscraper.utils.args.parse.commands.db import db
    from ofscraper.utils.args.parse.commands.main import program

    ctx = db.make_context("db", ["--unmark-permanent-skips"])
    assert ctx.params["unmark_permanent_skips"] is True
    ctx = db.make_context("db", [])
    assert ctx.params["unmark_permanent_skips"] is False
    ctx = program.make_context("ofscraper", ["--retry-permanent-skips"])
    assert ctx.params["retry_permanent_skips"] is True
    ctx = program.make_context("ofscraper", [])
    assert ctx.params["retry_permanent_skips"] is False
