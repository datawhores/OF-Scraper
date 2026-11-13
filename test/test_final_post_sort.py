from types import SimpleNamespace

import ofscraper.filters.media.filters as filters


def _settings(monkeypatch, **kw):
    ns = SimpleNamespace(**{"post_sort": "date", "post_desc": False, **kw})
    monkeypatch.setattr(filters.settings, "get_settings", lambda: ns)


def test_date_desc_reverses_posts(monkeypatch):
    _settings(monkeypatch, post_sort="date", post_desc=True)
    assert filters.final_post_sort([1, 2, 3, 4]) == [4, 3, 2, 1]


def test_date_without_desc_keeps_order(monkeypatch):
    _settings(monkeypatch, post_sort="date", post_desc=False)
    assert filters.final_post_sort([1, 2, 3, 4]) == [1, 2, 3, 4]


def test_random_shuffles_same_posts(monkeypatch):
    _settings(monkeypatch, post_sort="random", post_desc=False)
    posts = list(range(20))
    result = filters.final_post_sort(list(posts))
    assert sorted(result) == posts
