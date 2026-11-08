"""Merge DB's question exits close the merge screen (#304).

merge_runner runs for real. Every prompt it asks is scripted and the merge
itself is a stub, so the tests check which questions are asked and whether a
merge runs.
"""

import ofscraper.__main__  # noqa: F401  (import order avoids a circular import)

import pytest

import ofscraper.prompts.prompts as prompts
import ofscraper.utils.merge as merge_utils


def run_screen(monkeypatch, backup, confirm, another=()):
    """Run merge_runner with scripted answers.

    backup, confirm and another are the answers, in order, to "Have you backed
    up your database files?", "Confirm merge" and "Do another merge".
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
        return "merged"

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
