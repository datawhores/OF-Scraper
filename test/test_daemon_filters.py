"""--daemon -u runs the model filters, --excluded-username included (#285).

The daemon branch picked the -u creators straight from every subscription, so
`--daemon -u a,b -eu b` still scraped b. It now filters like an interactive
run, but never opens the "filtered the user list to zero" prompt.
"""

from types import SimpleNamespace

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.filters.models.other as other
from ofscraper.classes.of.models import Model
from ofscraper.managers import model as model_manager
from ofscraper.utils.args.callbacks.parse.username import UsernameParse


def _parsed(*values):
    # what the -u / --excluded-username callback hands to settings
    return UsernameParse(None, None, values)


@pytest.fixture
def warnings(monkeypatch):
    found = []
    monkeypatch.setattr(
        model_manager.log, "warning", lambda msg, *a, **k: found.append(msg)
    )
    return found


@pytest.fixture
def no_prompts(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("a prompt opened")

    for name in ("decide_filters_menu", "model_selector", "retry_user_scan"):
        monkeypatch.setattr(model_manager.prompts, name, fail)
    monkeypatch.setattr(model_manager.retriver, "get_selected_model", fail)


def _daemon(monkeypatch, usernames, excluded=(), daemon=5, drop=()):
    """
    A manager holding creators a and b, run with -u ``usernames`` and
    -eu ``excluded``. The other filters pass everyone, except that the price
    filter removes the names in ``drop``.
    """
    mm = model_manager.ModelManager()
    mm._update_all_subs(
        [Model({"id": 1, "username": "a"}), Model({"id": 2, "username": "b"})]
    )
    monkeypatch.setattr(
        model_manager.settings,
        "get_settings",
        lambda: SimpleNamespace(
            usernames=_parsed(usernames),
            daemon=daemon,
            excluded_username=_parsed(*excluded) if excluded else [],
        ),
    )
    keep = lambda models: models  # noqa: E731
    monkeypatch.setattr(model_manager.subtype, "subType", keep)
    monkeypatch.setattr(
        model_manager.price,
        "pricePaidFreeFilterHelper",
        lambda models: [m for m in models if m.name not in drop],
    )
    monkeypatch.setattr(model_manager.flags, "promoFilterHelper", keep)
    monkeypatch.setattr(model_manager.date_, "dateFilters", keep)
    monkeypatch.setattr(model_manager.sort, "sort_models_helper", keep)
    monkeypatch.setattr(other, "trace_log_user", lambda *a, **k: None)
    return mm


def _names(models):
    return [m.name for m in models]


def test_excluded_username_applies_in_daemon_mode(monkeypatch, no_prompts, warnings):
    mm = _daemon(monkeypatch, "a,b", excluded=["b"])
    assert _names(mm._select_models_scraper()) == ["a"]
    assert len(warnings) == 1 and "Not selected: b." in warnings[0]


def test_filter_removing_the_only_creator_logs_instead_of_prompting(
    monkeypatch, no_prompts, warnings
):
    mm = _daemon(monkeypatch, "a", drop={"a"})
    assert mm._select_models_scraper() == []
    assert len(warnings) == 1
    assert "Not selected: a." in warnings[0]
    assert "filter" in warnings[0]


def test_daemon_without_filters_is_unchanged(monkeypatch, no_prompts, warnings):
    mm = _daemon(monkeypatch, "a")
    assert _names(mm._select_models_scraper()) == ["a"]
    assert warnings == []


def test_daemon_all_runs_the_filters_without_prompting(monkeypatch, no_prompts, warnings):
    mm = _daemon(monkeypatch, "ALL", excluded=["b"])
    assert _names(mm._select_models_scraper()) == ["a"]


def test_daemon_all_filtered_to_zero_logs_instead_of_prompting(
    monkeypatch, no_prompts, warnings
):
    mm = _daemon(monkeypatch, "ALL", drop={"a", "b"})
    assert mm._select_models_scraper() == []
    assert len(warnings) == 1 and "filters removed every creator" in warnings[0]


def test_interactive_run_still_offers_the_filter_menu(monkeypatch, warnings):
    # without --daemon, filtering everyone out still opens the filter menu
    mm = _daemon(monkeypatch, "a", daemon=None, drop={"a", "b"})

    class _Opened(Exception):
        pass

    def setfilter():
        raise _Opened

    monkeypatch.setattr(mm, "setfilter", setfilter)
    monkeypatch.setattr(
        model_manager.console,
        "get_console",
        lambda: SimpleNamespace(print=lambda *a, **k: None),
    )
    with pytest.raises(_Opened):
        mm._select_models_scraper()


def test_interactive_and_daemon_select_the_same(monkeypatch, no_prompts, warnings):
    picked = {}
    for daemon in (None, 5):
        mm = _daemon(monkeypatch, "a,b", excluded=["b"], daemon=daemon)
        picked[daemon] = _names(mm._select_models_scraper())
    assert picked[None] == picked[5] == ["a"]
