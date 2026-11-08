"""Merge DB's "Do another merge" answer is used by the merge loop (#302).

The prompts before the merge and the merge itself are replaced with stubs.
The real confirm_db_continue runs, with only its batchConverter call scripted,
so the test checks the answer it hands back to merge_runner.
"""

import ofscraper.__main__  # noqa: F401  (import order avoids a circular import)

import pytest

import ofscraper.prompts.prompt_groups.merge as merge_prompts
import ofscraper.prompts.prompts as prompts
import ofscraper.utils.merge as merge_utils


def run_merges(monkeypatch, answers):
    """Run merge_runner, answering "Do another merge" with each of answers.

    Returns how many merges ran.
    """
    merges = []
    remaining = list(answers)

    monkeypatch.setattr(prompts, "backup_prompt_db", lambda: True)
    monkeypatch.setattr(prompts, "folder_prompt_db", lambda: "source")
    monkeypatch.setattr(prompts, "new_db_prompt", lambda: "merged")
    monkeypatch.setattr(prompts, "confirm_prompt_db", lambda folder, new_db: True)

    def fake_merge_loop(curr_folder, new_db):
        merges.append((curr_folder, new_db))
        return ["a.db"], [], []

    monkeypatch.setattr(merge_utils, "merge_loop", fake_merge_loop)

    def fake_batch_converter(*questions):
        assert len(questions) == 1
        question = questions[0]
        assert question["message"] == "Do another merge: "
        if not remaining:
            pytest.fail("Do another merge was asked more times than scripted")
        return {question["name"]: remaining.pop(0)}

    monkeypatch.setattr(
        merge_prompts.promptClasses, "batchConverter", fake_batch_converter
    )

    merge_utils.merge_runner()
    assert not remaining, "merge_runner stopped before using every answer"
    return len(merges)


def test_yes_runs_another_merge(monkeypatch):
    assert run_merges(monkeypatch, [True, False]) == 2


def test_no_stops_after_one_merge(monkeypatch):
    assert run_merges(monkeypatch, [False]) == 1


def test_back_to_main_menu_stops_after_one_merge(monkeypatch):
    assert run_merges(monkeypatch, [None]) == 1
