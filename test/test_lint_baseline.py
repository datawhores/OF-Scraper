"""The blind-except baseline in scripts/lint only lets counts go down."""

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def check():
    spec = importlib.util.spec_from_file_location(
        "check_blind_except", ROOT / "scripts" / "lint" / "check_blind_except.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finding(path, code):
    return {"filename": str(ROOT / path), "code": code}


def test_count_groups_by_file_and_rule(check):
    findings = [
        finding("ofscraper/db/a.py", "BLE001"),
        finding("ofscraper/db/a.py", "BLE001"),
        finding("ofscraper/db/a.py", "S110"),
        finding("ofscraper/data/api/b.py", "BLE001"),
    ]
    assert check.count(findings) == {
        "ofscraper/data/api/b.py:BLE001": 1,
        "ofscraper/db/a.py:BLE001": 2,
        "ofscraper/db/a.py:S110": 1,
    }


def test_matching_baseline_passes(check):
    assert check.compare({"a.py:BLE001": 2}, {"a.py:BLE001": 2}) == ([], [])


def test_new_finding_in_baselined_file_fails(check):
    more, fewer = check.compare({"a.py:BLE001": 2}, {"a.py:BLE001": 3})
    assert (more, fewer) == (["a.py:BLE001"], [])


def test_new_file_or_rule_fails(check):
    more, _ = check.compare(
        {"a.py:BLE001": 1}, {"a.py:BLE001": 1, "a.py:S110": 1, "b.py:BLE001": 1}
    )
    assert more == ["a.py:S110", "b.py:BLE001"]


def test_fixed_finding_asks_for_lower_baseline(check):
    more, fewer = check.compare({"a.py:BLE001": 2, "b.py:S110": 1}, {"a.py:BLE001": 1})
    assert (more, fewer) == ([], ["a.py:BLE001", "b.py:S110"])
