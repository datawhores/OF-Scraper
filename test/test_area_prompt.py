from types import SimpleNamespace

import pytest

import ofscraper.prompts.prompt_groups.area as area


@pytest.fixture
def prompt(monkeypatch):
    shown = {}

    def batch(*questions):
        shown.update(questions[0])
        return {"value": ["Timeline"]}

    def run(actions):
        args = SimpleNamespace(actions=actions, like_area=[], command="OF-Scraper")
        monkeypatch.setattr(area.settings, "get_args", lambda: args)
        monkeypatch.setattr(area.settings, "get_settings", lambda: args)
        monkeypatch.setattr(area.promptClasses, "batchConverter", batch)
        monkeypatch.setattr(area, "scrape_labels_prompt", lambda: None)
        area.areas_prompt()
        return shown

    return run


@pytest.mark.parametrize("action", ["like", "unlike"])
def test_like_and_unlike_get_the_area_hint(prompt, action):
    assert "You must select one or more" in prompt([action])["more_instruction"]


def test_download_gets_no_hint(prompt):
    assert prompt(["download"])["more_instruction"] == ""


def test_the_prompt_prints_nothing_itself(prompt, capsys):
    prompt(["download"])
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "fansly, expected",
    [
        (False, ["Profile", "Timeline", "Pinned", "Archived", "Streams"]),
        (True, ["Timeline", "Messages", "Purchased"]),
    ],
)
def test_metadata_anon_areas_prompt_is_site_aware(monkeypatch, fansly, expected):
    shown = {}

    def batch(*questions):
        shown.update(questions[0])
        return {"areas": ["Timeline"]}

    monkeypatch.setattr(area.sites, "is_fansly", lambda: fansly)
    monkeypatch.setattr(area.promptClasses, "batchConverter", batch)
    monkeypatch.setattr(area, "scrape_labels_prompt", lambda: None)

    area.metadata_anon_areas_prompt()
    assert [c.value for c in shown["choices"]] == expected


@pytest.mark.parametrize(
    "usernames, expected",
    [
        (["ALL"], "Users: ALL from CLI"),
        (["all"], "Users: ALL from CLI"),
        (["alice", "bob"], "Users: 2 from CLI"),
        ([], "Users: Prompt on run"),
    ],
)
def test_main_menu_status_handles_all_cli_users(monkeypatch, usernames, expected):
    import ofscraper.managers.manager as manager
    import ofscraper.prompts.prompt_groups.menu as menu_prompt
    import ofscraper.utils.args.accessors.areas as areas_accessor
    import ofscraper.utils.profiles.data as profile_data
    import ofscraper.utils.settings as settings

    monkeypatch.setattr(areas_accessor, "get_download_area", lambda: [])
    monkeypatch.setattr(areas_accessor, "get_like_area", lambda: [])
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(scrape_paid=False, usernames=usernames),
    )
    monkeypatch.setattr(manager, "Manager", SimpleNamespace(current_model_manager=None))
    monkeypatch.setattr(profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(menu_prompt.sites, "site_name", lambda: "OnlyFans")
    monkeypatch.setattr(menu_prompt.postgres, "enabled", lambda: False)

    assert expected in menu_prompt._main_menu_status()
