"""Merge DB's summary counts and lists the databases that failed (#305).

merge_runner and confirm_db_continue run for real. The prompts before the
merge and the merge itself are stubs, and only the "Do another merge"
answer is scripted: the fake batchConverter runs the question's "call"
summary the way the real prompt does, and the console output is captured.
"""

import ofscraper.__main__  # noqa: F401  (import order avoids a circular import)

import io
import sqlite3

import pytest
from rich.console import Console

import ofscraper.prompts.prompt_groups.merge as merge_prompts
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.merge as merge_utils

BRACKETED = r"C:\data\[old]\user_data.db"


def run_merges(monkeypatch, failed, answers):
    """Run merge_runner; each merge returns one merged db and the given failures.

    answers are the "Do another merge" answers, in order.
    Returns the captured console output and how many merges ran.
    """
    merges = []
    remaining = list(answers)
    out = io.StringIO()
    captured = Console(file=out, width=1000, color_system=None, markup=True)

    monkeypatch.setattr(prompts, "backup_prompt_db", lambda: True)
    monkeypatch.setattr(prompts, "folder_prompt_db", lambda: "source")
    monkeypatch.setattr(prompts, "new_db_prompt", lambda: "merged")
    monkeypatch.setattr(prompts, "confirm_prompt_db", lambda folder, new_db: True)
    monkeypatch.setattr(merge_prompts.console, "get_console", lambda: captured)

    def fake_merge_loop(curr_folder, new_db):
        merges.append((curr_folder, new_db))
        return [(1, {"path": "a.db"})], [], list(failed)

    monkeypatch.setattr(merge_utils, "merge_loop", fake_merge_loop)

    def fake_batch_converter(*questions):
        assert len(questions) == 1
        question = questions[0]
        assert question["message"] == "Do another merge: "
        if not remaining:
            pytest.fail("Do another merge was asked more times than scripted")
        question["call"]()
        return {question["name"]: remaining.pop(0)}

    monkeypatch.setattr(
        merge_prompts.promptClasses, "batchConverter", fake_batch_converter
    )

    merge_utils.merge_runner()
    assert not remaining, "merge_runner stopped before using every answer"
    return out.getvalue(), len(merges)


SUMMARY_NO_FAILURES = "Merged: 1 db files\nSkipped: 0 db files\nFailed: 0 db files\n"


def test_failure_is_counted_and_listed_with_its_reason(monkeypatch):
    failed = [
        (
            BRACKETED,
            {
                "path": BRACKETED,
                "reason": sqlite3.DatabaseError("file is not a database"),
            },
        )
    ]
    output, merges = run_merges(monkeypatch, failed, [False])
    assert merges == 1
    assert output == (
        "Merged: 1 db files\n"
        "Skipped: 0 db files\n"
        "Failed: 1 db files\n"
        f"  {BRACKETED}: file is not a database\n"
    )


def test_reason_with_markup_prints_literally(monkeypatch):
    reason = "bad [/] tag [bold]x[/bold]"
    failed = [("a.db", {"path": "a.db", "reason": Exception(reason)})]
    output, _ = run_merges(monkeypatch, failed, [False])
    assert output.endswith(f"Failed: 1 db files\n  a.db: {reason}\n")


def test_reason_without_a_message_shows_the_error_type(monkeypatch):
    failed = [("a.db", {"path": "a.db", "reason": sqlite3.DatabaseError()})]
    output, _ = run_merges(monkeypatch, failed, [False])
    assert output.endswith("Failed: 1 db files\n  a.db: DatabaseError\n")


def test_no_failures_shows_failed_zero_and_nothing_else(monkeypatch):
    output, merges = run_merges(monkeypatch, [], [False])
    assert merges == 1
    assert output == SUMMARY_NO_FAILURES


def test_yes_still_runs_another_merge_with_the_summary(monkeypatch):
    output, merges = run_merges(monkeypatch, [], [True, False])
    assert merges == 2
    assert output == SUMMARY_NO_FAILURES * 2


@pytest.mark.parametrize("answer", [False, None])
def test_no_and_back_still_stop_after_one_merge(monkeypatch, answer):
    output, merges = run_merges(monkeypatch, [], [answer])
    assert merges == 1
    assert output == SUMMARY_NO_FAILURES
