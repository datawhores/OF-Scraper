"""The "Do you want to reset username info" prompt and the creator picker.

When a previous run's creators are still queued, the picker opens with them
checked. "Yes Update Selection" (with or without a data fetch) should open it
with nothing checked; "Print Selection" followed by "No" keeps the queue.
"""

from types import SimpleNamespace

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.managers.model as model
import ofscraper.utils.settings as settings


def _manager(monkeypatch, answers):
    mm = model.ModelManager()
    creators = {name: SimpleNamespace(name=name) for name in ("old_one", "old_two", "new_one")}
    mm._all_subs_dict = dict(creators)
    queued = ["old_one", "old_two"]
    monkeypatch.setattr(mm, "_get_activities", lambda actions: [])
    monkeypatch.setattr(mm, "_load_all_subs_if_needed", lambda: None)
    monkeypatch.setattr(mm, "_fetch_all_subs", lambda **kwargs: None)
    monkeypatch.setattr(
        mm, "get_scrape_selected_models", lambda: [creators[n] for n in queued]
    )
    monkeypatch.setattr(mm, "_filter_and_prompt_for_selection", lambda: creators)
    monkeypatch.setattr(settings, "resetUserSelect", lambda: None)
    real = settings.get_settings
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(
            **{**vars(real()), "actions": [], "command": None, "usernames": [], "daemon": False}
        ),
    )
    answers = iter(answers)
    monkeypatch.setattr(model.prompts, "reset_username_prompt", lambda: next(answers))
    monkeypatch.setattr(model.prompts, "press_enter_to_continue", lambda: None)
    picked = {}

    def picker(choices, existing):
        picked["checked"] = [m.name for m in existing]
        return [creators["new_one"]]

    monkeypatch.setattr(model.retriver, "get_selected_model", picker)
    return mm, picked


@pytest.mark.parametrize("answer", ["Selection", "Selection_Strict"])
def test_update_selection_opens_the_picker_with_nothing_checked(monkeypatch, answer):
    mm, picked = _manager(monkeypatch, [answer])

    selection = mm.prepare_scraper_activity()

    assert picked["checked"] == []
    assert [m.name for m in selection] == ["new_one"]


def test_no_keeps_the_queued_creators_without_the_picker(monkeypatch):
    mm, picked = _manager(monkeypatch, [None, "No"])  # Print Selection, then No

    selection = mm.prepare_scraper_activity()

    assert picked == {}
    assert [m.name for m in selection] == ["old_one", "old_two"]


def test_first_selection_still_checks_the_queued_creators(monkeypatch):
    # without the reset prompt (e.g. the filter menu reopening the picker) the
    # previous selection stays checked, as before
    mm, picked = _manager(monkeypatch, [])

    mm._select_models_scraper()

    assert picked["checked"] == ["old_one", "old_two"]
