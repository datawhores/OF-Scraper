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
