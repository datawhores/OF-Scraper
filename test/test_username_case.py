"""-u and --excluded-username match creator names without regard to case (#282).

The option callback lowercases every name, but Fansly keeps a creator's
capitals, so an exact comparison never matched "SomeCreator".
"""

from types import SimpleNamespace

import pytest

import ofscraper.filters.models.other as other
from ofscraper.classes.of.models import Model
from ofscraper.managers import model as model_manager
from ofscraper.utils.args.callbacks.parse.username import UsernameParse


def _parsed(*values):
    # what the -u / --excluded-username callback hands to settings
    return UsernameParse(None, None, values)


def _manager(monkeypatch, usernames, daemon, models):
    mm = model_manager.ModelManager()
    mm._update_all_subs(models)
    monkeypatch.setattr(
        model_manager.settings,
        "get_settings",
        lambda: SimpleNamespace(usernames=usernames, daemon=daemon),
    )
    monkeypatch.setattr(
        mm, "_filter_and_prompt_for_selection", lambda: {m.name: m for m in models}
    )
    return mm


def _fansly_models():
    return [
        Model({"id": 111, "username": "SomeCreator"}),
        Model({"id": 222, "username": "OtherCreator"}),
    ]


@pytest.mark.parametrize("daemon", [False, True], ids=["interactive", "daemon"])
@pytest.mark.parametrize("typed", ["somecreator", "SomeCreator", "SOMECREATOR"])
def test_mixed_case_creator_is_selected(monkeypatch, daemon, typed):
    mm = _manager(monkeypatch, _parsed(typed), daemon, _fansly_models())
    assert [m.name for m in mm._select_models_scraper()] == ["SomeCreator"]


@pytest.mark.parametrize("daemon", [False, True], ids=["interactive", "daemon"])
def test_account_id_still_selects(monkeypatch, daemon):
    mm = _manager(monkeypatch, _parsed("111"), daemon, _fansly_models())
    assert [m.name for m in mm._select_models_scraper()] == ["SomeCreator"]


@pytest.mark.parametrize("daemon", [False, True], ids=["interactive", "daemon"])
def test_onlyfans_lowercase_name_unchanged(monkeypatch, daemon):
    models = [
        Model({"id": 1, "username": "somecreator"}),
        Model({"id": 2, "username": "othercreator"}),
    ]
    mm = _manager(monkeypatch, _parsed("somecreator"), daemon, models)
    assert [m.name for m in mm._select_models_scraper()] == ["somecreator"]


@pytest.mark.parametrize("daemon", [False, True], ids=["interactive", "daemon"])
def test_unmatched_name_is_reported(monkeypatch, daemon):
    warnings = []
    monkeypatch.setattr(model_manager.log, "warning", lambda msg, *a, **k: warnings.append(msg))
    mm = _manager(monkeypatch, _parsed("somecreator,nosuchcreator"), daemon, _fansly_models())

    assert [m.name for m in mm._select_models_scraper()] == ["SomeCreator"]
    assert len(warnings) == 1
    assert "nosuchcreator" in warnings[0]
    assert "somecreator" not in warnings[0]


def test_daemon_warning_does_not_blame_filters(monkeypatch):
    # no filters run before the daemon selection
    warnings = []
    monkeypatch.setattr(model_manager.log, "warning", lambda msg, *a, **k: warnings.append(msg))
    mm = _manager(monkeypatch, _parsed("nosuchcreator"), True, _fansly_models())

    assert mm._select_models_scraper() == []
    assert warnings == ["Not selected: nosuchcreator. No creator has that name or id."]


def test_interactive_warning_allows_for_exclusion(monkeypatch):
    # -u SomeCreator -eu SomeCreator: found, then removed by the filters
    warnings = []
    monkeypatch.setattr(model_manager.log, "warning", lambda msg, *a, **k: warnings.append(msg))
    models = _fansly_models()
    mm = _manager(monkeypatch, _parsed("SomeCreator"), False, models)
    monkeypatch.setattr(
        mm, "_filter_and_prompt_for_selection", lambda: {m.name: m for m in models[1:]}
    )

    assert mm._select_models_scraper() == []
    assert warnings == [
        "Not selected: somecreator. The name or id wasn't found, "
        "or a filter or --excluded-username removed it."
    ]


def test_no_warning_when_every_name_matches(monkeypatch):
    warnings = []
    monkeypatch.setattr(model_manager.log, "warning", lambda msg, *a, **k: warnings.append(msg))
    mm = _manager(monkeypatch, _parsed("SomeCreator,222"), True, _fansly_models())

    assert [m.name for m in mm._select_models_scraper()] == ["SomeCreator", "OtherCreator"]
    assert warnings == []


def test_excluded_username_drops_mixed_case_creator(monkeypatch):
    monkeypatch.setattr(
        other.settings,
        "get_settings",
        lambda: SimpleNamespace(excluded_username=_parsed("SomeCreator")),
    )
    monkeypatch.setattr(other, "trace_log_user", lambda *a, **k: None)
    assert [m.name for m in other.otherFilters(_fansly_models())] == ["OtherCreator"]
    assert other.is_excluded_username("SomeCreator")


def test_excluded_account_id_drops_creator(monkeypatch):
    # -u takes account ids, so -eu does too
    monkeypatch.setattr(
        other.settings,
        "get_settings",
        lambda: SimpleNamespace(excluded_username=_parsed("111")),
    )
    monkeypatch.setattr(other, "trace_log_user", lambda *a, **k: None)
    assert [m.name for m in other.otherFilters(_fansly_models())] == ["OtherCreator"]
    assert other.is_excluded_username("SomeCreator", 111)
    assert not other.is_excluded_username("SomeCreator", 222)
    assert not other.is_excluded_username("SomeCreator")
