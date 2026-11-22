"""Merge DB's question exits close the merge screen (#304).

merge_runner runs for real. Every prompt it asks is scripted and the merge
itself is a stub, so the tests check which questions are asked and whether a
merge runs.
"""

import io
from pathlib import Path, PureWindowsPath

import ofscraper.__main__  # noqa: F401  (import order avoids a circular import)

import pytest
from rich.console import Console

import ofscraper.db.postgres as postgres
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.merge as merge_utils


def run_screen(monkeypatch, backup, confirm, another=(), target="merged"):
    """Run merge_runner with scripted answers.

    backup, confirm and another are the answers, in order, to "Have you backed
    up your database files?", "Confirm merge" and "Do another merge"; target
    is the answer to "Merge db folder".
    Returns the list of questions asked and the list of merges run.
    """
    asked = []
    merges = []
    scripts = {
        "backup": list(backup),
        "confirm": list(confirm),
        "another": list(another),
    }

    def answer(question):
        asked.append(question)
        if not scripts[question]:
            pytest.fail(f"{question} was asked more times than scripted")
        return scripts[question].pop(0)

    def folder():
        asked.append("folder")
        return "source"

    def new_db():
        asked.append("new_db")
        return target

    def fake_merge_loop(curr_folder, new_db):
        merges.append((curr_folder, new_db))
        return ["a.db"], [], []

    monkeypatch.setattr(prompts, "backup_prompt_db", lambda: answer("backup"))
    monkeypatch.setattr(prompts, "folder_prompt_db", folder)
    monkeypatch.setattr(prompts, "new_db_prompt", new_db)
    monkeypatch.setattr(
        prompts, "confirm_prompt_db", lambda folder, new_db: answer("confirm")
    )
    monkeypatch.setattr(
        prompts,
        "confirm_db_continue",
        lambda completed, skipped, failed: answer("another"),
    )
    monkeypatch.setattr(merge_utils, "merge_loop", fake_merge_loop)

    merge_utils.merge_runner()
    for question, left in scripts.items():
        assert not left, f"merge_runner stopped before answering {question}"
    return asked, merges


def test_backup_no_closes_without_merging(monkeypatch):
    asked, merges = run_screen(monkeypatch, backup=[False], confirm=[])
    assert merges == []
    assert asked == ["backup"]


def test_confirm_back_to_main_menu_closes_without_merging(monkeypatch):
    asked, merges = run_screen(monkeypatch, backup=[True], confirm=[None])
    assert merges == []
    assert asked == ["backup", "folder", "new_db", "confirm"]


def test_confirm_no_asks_the_folder_questions_again(monkeypatch):
    asked, merges = run_screen(
        monkeypatch, backup=[True, True], confirm=[False, None]
    )
    assert merges == []
    assert asked == [
        "backup",
        "folder",
        "new_db",
        "confirm",
        "backup",
        "folder",
        "new_db",
        "confirm",
    ]


def test_confirm_yes_runs_the_merge(monkeypatch):
    asked, merges = run_screen(
        monkeypatch, backup=[True], confirm=[True], another=[False]
    )
    assert merges == [("source", "merged")]
    assert asked == ["backup", "folder", "new_db", "confirm", "another"]


@pytest.fixture
def screen(monkeypatch):
    """What the merge screen prints, in a console wide enough not to wrap."""
    printed = io.StringIO()
    monkeypatch.setattr(merge_utils, "console", Console(file=printed, width=1000))
    return printed


def test_the_screen_says_it_works_on_sqlite_files_while_postgresql_is_on(monkeypatch, screen):
    # not through the environment: the scraper keeps what it read there
    monkeypatch.setattr(postgres, "enabled", lambda: True)
    asked, merges = run_screen(
        monkeypatch, backup=[True], confirm=[True], another=[False]
    )
    # on the screen itself, so that no --output level hides it
    assert screen.getvalue() == (
        "PostgreSQL is on (OFSC_DATABASE_URL is set), but Merge Databases works"
        " on the user_data.db files, not PostgreSQL. It does not see anything"
        " scraped since PostgreSQL was turned on, and what it changes in those"
        " files does not reach PostgreSQL. See POSTGRESQL.md.\n"
        # after the merge, the next step, with the merge folder that was used
        "To bring the merged file into PostgreSQL, run:\n"
        'python -m ofscraper.commands.postgres_import "merged"\n'
        "It only reports what it would do. Then run it again with --apply to"
        " bring the file in.\n"
    )
    # the merge still runs
    assert merges == [("source", "merged")]
    assert asked == ["backup", "folder", "new_db", "confirm", "another"]


def test_the_import_command_is_one_line_with_the_folder_the_merge_used(monkeypatch):
    printed = io.StringIO()
    monkeypatch.setattr(merge_utils, "console", Console(file=printed, width=60))
    monkeypatch.setattr(postgres, "enabled", lambda: True)
    # a file name: the merge writes user_data.db in the folder it is in
    target = str(Path("a [b]", "long merge folder name", "merged.db"))
    run_screen(
        monkeypatch, backup=[True], confirm=[True], another=[False], target=target
    )
    command = (
        "python -m ofscraper.commands.postgres_import"
        f' "{Path("a [b]", "long merge folder name")}"'
    )
    assert len(command) > 60
    assert command in printed.getvalue().splitlines()


def test_a_drive_root_keeps_its_closing_quote(monkeypatch, screen):
    monkeypatch.setattr(postgres, "enabled", lambda: True)

    class AtDriveRoot:
        def get_new_db(self, new_db):
            return PureWindowsPath("D:/user_data.db")

    monkeypatch.setattr(merge_utils.merge, "MergeDatabase", AtDriveRoot)
    run_screen(monkeypatch, backup=[True], confirm=[True], another=[False])
    # "D:\" would read as D:" on Windows; "D:\\" reads as D:\
    assert (
        r'python -m ofscraper.commands.postgres_import "D:\\"'
        in screen.getvalue().splitlines()
    )


def test_the_screen_says_nothing_about_postgresql_while_it_is_off(monkeypatch, screen):
    monkeypatch.setattr(postgres, "enabled", lambda: False)
    asked, merges = run_screen(
        monkeypatch, backup=[True], confirm=[True], another=[False]
    )
    assert screen.getvalue() == ""
    assert merges == [("source", "merged")]
