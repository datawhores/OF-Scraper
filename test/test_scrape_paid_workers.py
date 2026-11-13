import asyncio

import pytest

import ofscraper.data.api.paid as paid


@pytest.fixture
def cached(monkeypatch):
    monkeypatch.setattr(paid.progress_utils.api, "add_overall_task", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(paid.progress_utils.api, "update_overall_task", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(paid.progress_utils.api, "remove_overall_task", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(paid, "trace_progress_log", lambda *a, **k: None)
    monkeypatch.setattr(paid, "trace_log_raw", lambda *a, **k: None)
    monkeypatch.setattr(paid.log, "traceback_", lambda *a, **k: None, raising=False)
    store = {}
    monkeypatch.setattr(paid.cache, "set", lambda key, value, **k: store.__setitem__(key, value))
    return store


async def _pages(*pages):
    for page in pages:
        yield page


async def _failing():
    yield [{"id": 9}]
    raise OSError("connection reset")


def test_collects_every_worker(cached):
    gens = [_pages([{"id": 1}], [{"id": 2}]), _pages([], [{"id": 3}])]
    output = asyncio.run(paid.process_tasks_all_paid(gens))

    assert sorted(item["id"] for item in output) == [1, 2, 3]
    assert sorted(cached["purchased_all"]) == [1, 2, 3]


def test_failing_worker_does_not_stop_the_others(cached):
    gens = [_failing(), _pages([{"id": 1}])]
    output = asyncio.run(paid.process_tasks_all_paid(gens))

    assert sorted(item["id"] for item in output) == [1, 9]


def test_no_workers(cached):
    assert asyncio.run(paid.process_tasks_all_paid([])) == []
