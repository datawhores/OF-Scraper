"""A Fansly wall scan that stops early says so.

A wall's pages come from fansly_scrape.label_pages. An error on a later page
ended the scan with only the posts so far, and nothing but the debug
traceback said the wall was incomplete.
"""

import asyncio
from types import SimpleNamespace

import pytest

import ofscraper.data.api.labels as labels

WALL = {"id": "500000000000000001", "name": "Bonus wall"}


@pytest.fixture(autouse=True)
def no_pending_marks():
    labels._finished_labels.clear()
    yield
    labels._finished_labels.clear()


@pytest.fixture
def warnings_logged(monkeypatch):
    logged = []
    log = SimpleNamespace(
        debug=lambda *a, **k: None,
        traceback_=lambda *a, **k: None,
        warning=logged.append,
    )
    monkeypatch.setattr(labels, "log", log)
    # a cut-short scan is reported by incomplete.mark_incomplete
    monkeypatch.setattr(labels.incomplete, "log", log)
    return logged


def serve(monkeypatch, pages, fail_after=None):
    async def label_pages(c, label, model_id):
        for n, page in enumerate(pages):
            if n == fail_after:
                raise RuntimeError("page refused")
            yield [{"id": i} for i in page]

    monkeypatch.setattr(labels.fansly_scrape, "label_pages", label_pages)


def collect(known=None):
    async def run():
        out = []
        async for _, batch in labels.scrape_posts_walls(None, WALL, 1, known=known):
            out.extend(p["id"] for p in batch)
        return out

    return asyncio.run(run())


def test_wall_scan_cut_short_warns_once(monkeypatch, warnings_logged):
    serve(monkeypatch, [[1, 2], [3, 4], [5]], fail_after=1)
    assert collect() == [1, 2]
    assert len(warnings_logged) == 1
    assert "Bonus wall" in warnings_logged[0]
    assert "stopped early" in warnings_logged[0]


def test_complete_scan_of_an_empty_wall_does_not_warn(monkeypatch, warnings_logged):
    serve(monkeypatch, [])
    assert collect() == []
    assert warnings_logged == []


def test_complete_wall_scan_does_not_warn(monkeypatch, warnings_logged):
    serve(monkeypatch, [[1, 2], [3, 4]])
    assert collect() == [1, 2, 3, 4]
    # stopping at posts already recorded is a finished scan too
    assert collect(known={"1", "2"}) == [1, 2]
    assert warnings_logged == []
