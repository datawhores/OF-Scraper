"""-u and --excluded-username match creator names without regard to case (#282).

The option callback lowercases every name, but Fansly keeps a creator's
capitals, so an exact comparison never matched "SomeCreator".
"""

import asyncio
import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import ofscraper.data.api.subscriptions.individual as individual
import ofscraper.data.models.utils.retriver as retriver
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
    # the daemon filters without the prompt (#285)
    monkeypatch.setattr(mm, "_filtered_models", lambda: {m.name: m for m in models})
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


def test_daemon_warning_allows_for_exclusion(monkeypatch):
    # the daemon runs the filters too (#285), so its warning says the same
    warnings = []
    monkeypatch.setattr(model_manager.log, "warning", lambda msg, *a, **k: warnings.append(msg))
    mm = _manager(monkeypatch, _parsed("nosuchcreator"), True, _fansly_models())

    assert mm._select_models_scraper() == []
    assert warnings == [
        "Not selected: nosuchcreator. The name or id wasn't found, "
        "or a filter or --excluded-username removed it."
    ]


@pytest.mark.parametrize("daemon", [False, True], ids=["interactive", "daemon"])
def test_creator_not_found_exits_usage(monkeypatch, daemon):
    # -u names a creator that isn't there: the run exits 2, not 0
    import ofscraper.main.close.exit_status as exit_status
    import ofscraper.main.open.run as run

    mm = _manager(monkeypatch, _parsed("somecreator,nosuchcreator"), daemon, _fansly_models())
    monkeypatch.setattr(run, "check_database", lambda: None)
    monkeypatch.setattr(run, "start_manager", mm._select_models_scraper)

    with pytest.raises(SystemExit) as exc:
        run.main()

    assert exc.value.code == exit_status.USAGE


def test_creator_not_found_does_not_hide_a_failed_creator(monkeypatch):
    # -u gone,real where real's scan fails: the run outcome (4) wins over
    # the not-found usage error, which is still logged
    import ofscraper.commands.utils.command as command_mod
    import ofscraper.main.close.exit_status as exit_status
    import ofscraper.main.open.run as run

    warnings = []
    monkeypatch.setattr(model_manager.log, "warning", lambda msg, *a, **k: warnings.append(msg))
    mm = _manager(monkeypatch, _parsed("nosuchcreator,somecreator"), True, _fansly_models())

    def start_manager():
        for model in mm._select_models_scraper():
            command_mod.log_user_failure(model.name, RuntimeError("scan failed"))

    monkeypatch.setattr(run, "check_database", lambda: None)
    monkeypatch.setattr(run, "start_manager", start_manager)

    with pytest.raises(SystemExit) as exc:
        run.main()

    assert exc.value.code == exit_status.PARTIAL
    assert any("nosuchcreator" in w for w in warnings)


def test_creator_removed_by_a_filter_is_not_a_usage_error(monkeypatch):
    # -u SomeCreator -eu SomeCreator: found, then deliberately left out
    import ofscraper.main.close.exit_status as exit_status
    import ofscraper.main.open.run as run

    models = _fansly_models()
    mm = _manager(monkeypatch, _parsed("SomeCreator"), False, models)
    monkeypatch.setattr(
        mm, "_filter_and_prompt_for_selection", lambda: {m.name: m for m in models[1:]}
    )
    monkeypatch.setattr(run, "check_database", lambda: None)
    monkeypatch.setattr(run, "start_manager", mm._select_models_scraper)

    with pytest.raises(SystemExit) as exc:
        run.main()

    assert exc.value.code == exit_status.OK


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


def _renamed_creator(monkeypatch):
    """OnlyFans answers a creator's old name with the current one (#662).
    Returns the names looked up one by one."""
    looked_up = []

    async def profile(c, account):
        looked_up.append(account)
        if account in ("oldname", "newname"):
            return {"id": 111, "username": "newname"}

    monkeypatch.setattr(individual.profile, "scrape_profile_helper_async", profile)
    session = SimpleNamespace(aget_subscription_session=lambda **k: contextlib.nullcontext())
    monkeypatch.setattr(individual.manager, "Manager", SimpleNamespace(session=session))
    monkeypatch.setattr(individual.progress_utils, "userlist", MagicMock())
    return looked_up


def _looked_up(names):
    async def lookup():
        return await individual.get_subscription(names)

    return [Model(x) for x in asyncio.run(lookup())]


def _select_warnings(monkeypatch, usernames, daemon, models):
    warnings = []
    monkeypatch.setattr(model_manager.log, "warning", lambda msg, *a, **k: warnings.append(msg))
    mm = _manager(monkeypatch, _parsed(usernames), daemon, models)
    return [m.name for m in mm._select_models_scraper()], warnings


@pytest.mark.parametrize("daemon", [False, True], ids=["interactive", "daemon"])
def test_old_name_selects_the_account_it_leads_to(monkeypatch, daemon):
    _renamed_creator(monkeypatch)
    found = _looked_up(["oldname", "nosuchcreator"])
    selected, warnings = _select_warnings(
        monkeypatch, "oldname,nosuchcreator", daemon, found
    )

    assert selected == ["newname"]
    assert len(warnings) == 1
    assert "nosuchcreator" in warnings[0]
    assert "oldname" not in warnings[0]


@pytest.mark.parametrize("daemon", [False, True], ids=["interactive", "daemon"])
def test_old_and_new_name_both_select_the_account(monkeypatch, daemon):
    _renamed_creator(monkeypatch)
    found = _looked_up(["oldname", "newname"])
    selected, warnings = _select_warnings(monkeypatch, "oldname,newname", daemon, found)

    assert selected == ["newname"]
    assert warnings == []


def _subscription_list(monkeypatch, usernames, black_list=()):
    async def subs(count, account="active"):
        return [{"id": 111, "username": "newname"}] if account == "active" else []

    async def none():
        return []

    async def blacklist():
        return black_list

    monkeypatch.setattr(retriver.subscriptions, "get_subscriptions", subs)
    monkeypatch.setattr(retriver.lists, "get_otherlist", none)
    monkeypatch.setattr(retriver.lists, "get_blacklist", blacklist)
    monkeypatch.setattr(retriver.console, "get_shared_console", MagicMock)
    monkeypatch.setattr(
        retriver.settings,
        "get_settings",
        lambda: SimpleNamespace(usernames=_parsed(usernames)),
    )
    return asyncio.run(retriver.get_via_list([1, 0]))


@pytest.mark.parametrize("daemon", [False, True], ids=["interactive", "daemon"])
def test_old_name_not_in_the_list_is_looked_up(monkeypatch, daemon):
    looked_up = _renamed_creator(monkeypatch)
    found = _subscription_list(monkeypatch, "oldname")
    selected, warnings = _select_warnings(monkeypatch, "oldname", daemon, found)

    assert looked_up == ["oldname"]
    # the listed account takes the old name, no second copy
    assert [(m.name, m.id) for m in found] == [("newname", 111)]
    assert selected == ["newname"]
    assert warnings == []


@pytest.mark.parametrize(
    "usernames, looked_up_names",
    [("newname", []), ("oldname", ["oldname"])],
    ids=["current name", "old name"],
)
def test_blacklisted_account_stays_out(monkeypatch, usernames, looked_up_names):
    looked_up = _renamed_creator(monkeypatch)
    found = _subscription_list(monkeypatch, usernames, black_list={111})

    assert looked_up == looked_up_names
    assert found == []


@pytest.mark.parametrize("usernames", ["newname", "111", "ALL"])
def test_names_in_the_list_are_not_looked_up(monkeypatch, usernames):
    looked_up = _renamed_creator(monkeypatch)
    found = _subscription_list(monkeypatch, usernames)

    assert looked_up == []
    assert [m.name for m in found] == ["newname"]
