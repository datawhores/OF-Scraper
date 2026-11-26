"""Focused unit tests for model price filters (paid/free and min/max bounds)."""

from types import SimpleNamespace

import pytest

import ofscraper.filters.models.price as price_filters


def _model(name, *, current=0, renewal=0, regular=0, promo=0):
    return SimpleNamespace(
        name=name,
        final_current_price=current,
        final_renewal_price=renewal,
        final_regular_price=regular,
        final_promo_price=promo,
    )


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def _patch_settings(monkeypatch, **overrides):
    monkeypatch.setattr(
        price_filters.settings, "get_settings", lambda: _Settings(**overrides)
    )


@pytest.mark.parametrize(
    "setting, attr",
    [
        ("current_price", "current"),
        ("renewal_price", "renewal"),
        ("regular_price", "regular"),
        ("promo_price", "promo"),
    ],
)
def test_paid_and_free_filters(monkeypatch, setting, attr):
    models = [
        _model("free", **{attr: 0}),
        _model("cheap", **{attr: 4.99}),
        _model("expensive", **{attr: 19.99}),
    ]

    _patch_settings(monkeypatch, **{setting: "paid"})
    assert [m.name for m in price_filters.pricePaidFreeFilterHelper(models)] == [
        "cheap",
        "expensive",
    ]

    _patch_settings(monkeypatch, **{setting: "free"})
    assert [m.name for m in price_filters.pricePaidFreeFilterHelper(models)] == ["free"]

    _patch_settings(monkeypatch, **{setting: None})
    assert [m.name for m in price_filters.pricePaidFreeFilterHelper(models)] == [
        "free",
        "cheap",
        "expensive",
    ]


@pytest.mark.parametrize(
    "prefix, attr",
    [
        ("promo_price", "promo"),
        ("regular_price", "regular"),
        ("renewal_price", "renewal"),
        ("current_price", "current"),
    ],
)
def test_min_and_max_bounds_are_inclusive(monkeypatch, prefix, attr):
    models = [
        _model("zero", **{attr: 0}),
        _model("low", **{attr: 5}),
        _model("mid", **{attr: 10}),
        _model("high", **{attr: 20}),
    ]

    _patch_settings(monkeypatch, **{f"{prefix}_min": 5, f"{prefix}_max": 10})
    assert [m.name for m in price_filters.priceMinMaxFilters(models)] == ["low", "mid"]


def test_combined_paid_and_bound_filters(monkeypatch):
    models = [
        _model("free", current=0, renewal=0),
        _model("promo_only", current=5, renewal=15),
        _model("steady", current=10, renewal=10),
        _model("too_high", current=25, renewal=25),
    ]
    _patch_settings(
        monkeypatch,
        current_price="paid",
        current_price_max=15,
        renewal_price_max=12,
    )
    assert [m.name for m in price_filters.pricePaidFreeFilterHelper(models)] == [
        "steady"
    ]
