"""With PostgreSQL on, a tool that still works on user_data.db files says so (#631).

The sentence, and how a tool that is run on its own finds out that PostgreSQL
is on: from the environment it is run in, and nothing else. Each tool's own
test is beside that tool's other tests. No server is needed.
"""

import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

import ofscraper.db.postgres as postgres
from ofscraper.db.operations_.media import mediaCreate

URL = "postgresql://scraper:s3cret-word@db.example:5433/library"
ROOT = Path(__file__).resolve().parents[1]
SENTENCE = (
    "PostgreSQL is on (OFSC_DATABASE_URL is set), but {tool} works on the"
    " user_data.db files, not PostgreSQL. It does not see anything scraped"
    " since PostgreSQL was turned on, and what it changes in those files does"
    " not reach PostgreSQL. See POSTGRESQL.md."
)
# stash_sync can read PostgreSQL (--postgres): given files, it says how
STASH_SYNC = (
    "PostgreSQL is on (OFSC_DATABASE_URL is set), but stash_sync works on the"
    " user_data.db files it was given, not PostgreSQL. They hold nothing"
    " scraped since PostgreSQL was turned on. To read PostgreSQL, give"
    " --postgres in place of the files. See POSTGRESQL.md."
)


# and so can recover_collisions (--postgres --creator)
RECOVER_COLLISIONS = (
    "PostgreSQL is on (OFSC_DATABASE_URL is set), but recover_collisions works"
    " on the user_data.db file it was given, not PostgreSQL. The file holds"
    " nothing scraped since PostgreSQL was turned on, and what is changed in it"
    " does not reach PostgreSQL. To work on PostgreSQL, give --postgres and"
    " --creator in place of the file. See POSTGRESQL.md."
)
OWN_SENTENCE = {"stash_sync": STASH_SYNC, "recover_collisions": RECOVER_COLLISIONS}


def said_by(tool):
    return OWN_SENTENCE.get(tool) or SENTENCE.format(tool=tool)


# each tool as a user starts it, given a folder that holds one empty database.
# stash_sync gets a folder without one, and so has nothing to ask Stash about
# (test_stash_sync has it say so during a real sync)
TOOLS = {
    "stash_sync": lambda folder: [
        sys.executable,
        "-m",
        "ofscraper.commands.stash_sync",
        str(folder / "empty"),
        "--url",
        "http://127.0.0.1:9/graphql",
    ],
    "recover_collisions": lambda folder: [
        sys.executable,
        "-m",
        "ofscraper.commands.recover_collisions",
        str(folder / "1" / "user_data.db"),
    ],
    "creator_names.py": lambda folder: [
        sys.executable,
        str(ROOT / "scripts" / "creator_names.py"),
        "--data-dir",
        str(folder),
    ],
}


@pytest.fixture(autouse=True)
def no_url(monkeypatch):
    monkeypatch.delenv(postgres.URL_KEY, raising=False)


@pytest.fixture
def folder(tmp_path):
    db = tmp_path / "1" / "user_data.db"
    db.parent.mkdir()
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute(mediaCreate)
    (tmp_path / "empty").mkdir()
    return tmp_path


def run_tool(tool, folder, **variables):
    """The tool in a process of its own, with these environment variables
    (None takes one away)."""
    env = {**os.environ, "PYTHONPATH": str(ROOT), **variables}
    env = {key: value for key, value in env.items() if value is not None}
    return subprocess.run(
        TOOLS[tool](folder),
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        cwd=ROOT,
        env=env,
    )


# --- the sentence ---


def test_the_notice_says_what_the_tool_works_on_and_what_that_means():
    assert postgres.sqlite_files_notice("stash_sync") == SENTENCE.format(
        tool="stash_sync"
    )


# --- a tool that is run on its own ---


def test_a_tool_says_so_on_stderr_when_the_url_is_in_its_environment(monkeypatch, capsys):
    monkeypatch.setenv(postgres.URL_KEY, URL)

    postgres.warn_sqlite_files("stash_sync")

    said = capsys.readouterr()
    assert said.err == "warning: " + SENTENCE.format(tool="stash_sync") + "\n"
    assert said.out == ""


@pytest.mark.parametrize("value", [None, "", "   ", "\t"])
def test_a_tool_says_nothing_without_a_url(monkeypatch, capsys, value):
    if value is not None:
        monkeypatch.setenv(postgres.URL_KEY, value)

    postgres.warn_sqlite_files("stash_sync")

    said = capsys.readouterr()
    assert said.err == ""
    assert said.out == ""


def test_the_notice_never_holds_the_address(monkeypatch, capsys):
    monkeypatch.setenv(postgres.URL_KEY, URL)

    postgres.warn_sqlite_files("stash_sync")

    said = capsys.readouterr().err
    assert said
    assert "s3cret-word" not in said
    assert "db.example" not in said


def test_only_the_environment_is_asked(monkeypatch, capsys):
    """Not the scraper's settings, and not the server."""
    monkeypatch.setenv(postgres.URL_KEY, URL)

    def asked(*args, **kwargs):
        raise AssertionError("more than the environment was asked")

    monkeypatch.setattr(postgres.of_env, "getattr", asked)
    monkeypatch.setattr(postgres.POSTGRES, "connect", asked)
    monkeypatch.setattr(postgres.POSTGRES, "check", asked)

    postgres.warn_sqlite_files("stash_sync")

    assert capsys.readouterr().err.startswith("warning: PostgreSQL is on")


def test_the_tool_is_left_as_it_was(monkeypatch, capsys):
    monkeypatch.setenv(postgres.URL_KEY, URL)
    monkeypatch.setattr(sys, "argv", ["tool", "user_data.db", "--apply"])
    argv, environment, path = list(sys.argv), dict(os.environ), list(sys.path)

    postgres.warn_sqlite_files("stash_sync")

    assert capsys.readouterr().err
    assert sys.argv == argv
    assert dict(os.environ) == environment
    assert sys.path == path


@pytest.mark.parametrize("tool", TOOLS)
def test_each_tool_says_so_and_still_runs(folder, tool):
    off = run_tool(tool, folder, **{postgres.URL_KEY: None})
    on = run_tool(tool, folder, **{postgres.URL_KEY: URL})

    assert off.returncode == 0, off.stderr
    assert off.stderr == ""
    assert on.returncode == 0, on.stderr
    assert on.stderr == "warning: " + said_by(tool) + "\n"
    # what the tool reports is the same, and only that is on stdout
    assert on.stdout == off.stdout != ""


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("url", [None, URL])
def test_a_setting_the_scraper_cant_read_doesnt_stop_a_tool(folder, tool, url):
    """The scraper stops on a number it can't read; these tools don't read
    the scraper's settings."""
    result = run_tool(
        tool, folder, OFSC_DOWNLOAD_SEM_DEFAULT="many", **{postgres.URL_KEY: url}
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout
    assert result.stderr == ("warning: " + said_by(tool) + "\n" if url else "")


def test_the_tools_dont_load_the_scraper(folder):
    """Its settings and console change what a process does (the environment,
    how stdout is written), and take most of a second to load."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys\n"
            "import ofscraper.commands.recover_collisions\n"
            "import ofscraper.commands.stash_sync\n"
            "import ofscraper.db.postgres as postgres\n"
            "postgres.warn_sqlite_files('a tool')\n"
            "print(sorted(name for name in sys.modules if name.split('.')[0]"
            " in ('rich', 'dotenv', 'aiohttp')"
            " or name.startswith(('ofscraper.utils.settings',"
            " 'ofscraper.utils.console', 'ofscraper.utils.config'))))",
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT), postgres.URL_KEY: URL},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"
    assert result.stderr.startswith("warning: PostgreSQL is on")
