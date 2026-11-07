"""Dynamic rule names in the config menu and the request code (#226).

Given/When/Then:
1. Given no dynamic rule in config.json, when the advanced config menu is
   built, then its choices include the rule the default ("digital") picks,
   and that rule is the one selected.
2. Given an alias such as "dc" in config.json, when the menu is built, then
   the rule it picks is selected.
3. Given "digitalcriminal" in config.json, when it is read, then it is kept
   rather than replaced by the default, as the request code accepts it.
4. Given any name the config accepts, when a request is signed, then the
   rule that name stands for is used.
"""

from types import SimpleNamespace

import pytest

import ofscraper.prompts.prompt_groups.config as config_prompts
import ofscraper.utils.config.data as data
import ofscraper.utils.config.file as config_file


class _Stop(Exception):
    pass


@pytest.fixture
def config(monkeypatch):
    cfg = {}
    monkeypatch.setattr(config_file, "open_config", lambda *a, **k: cfg)
    return cfg


def _dynamic_question(monkeypatch):
    asked = []

    def capture(*questions, **kwargs):
        asked.extend(questions)
        raise _Stop

    monkeypatch.setattr(config_prompts.promptClasses, "batchConverter", capture)
    with pytest.raises(_Stop):
        config_prompts.advanced_config()
    return next(q for q in asked if q.get("name") == "dynamic-mode-default")


# 1. the default is offered and selected


def test_menu_offers_and_selects_the_default_rule(config, monkeypatch):
    question = _dynamic_question(monkeypatch)
    assert question["default"] in question["choices"]
    # listed and saved as "digital", the name a new config.json holds
    assert question["default"] == "digital"


# 2. an alias selects its rule


@pytest.mark.parametrize(
    "alias", ["dc", "digital", "digitals", "digitalcriminal", "digitalcriminals"]
)
def test_menu_selects_the_rule_an_alias_picks(config, monkeypatch, alias):
    config["advanced_options"] = {"dynamic-mode-default": alias}
    question = _dynamic_question(monkeypatch)
    assert question["default"] == "digital"
    # the rule is listed once, by the name the menu saves
    assert question["choices"].count("digital") == 1
    assert "digitalcriminals" not in question["choices"]


def test_menu_choices_have_no_removed_rules(config, monkeypatch):
    question = _dynamic_question(monkeypatch)
    assert not {"dv", "dev", "deviint"} & set(question["choices"])


# 3. digitalcriminal is accepted


def test_get_dynamic_keeps_digitalcriminal():
    cfg = {"advanced_options": {"dynamic-mode-default": "digitalcriminal"}}
    assert data.get_dynamic(config=cfg) == "digitalcriminal"


# 4. every accepted name picks its rule


def test_every_name_get_dynamic_accepts_picks_its_rule(monkeypatch):
    import ofscraper.utils.auth.request as request

    rules = {"datawhores", "xagler", "rafa", "digitalcriminals", "generic"}
    for name in rules:
        monkeypatch.setattr(request, f"get_request_auth_{name}", lambda n=name: n)
    monkeypatch.setattr(
        request, "get_request_auth_dynamic_rule_manual", lambda: "manual"
    )
    real = request.of_env.getattr
    monkeypatch.setattr(
        request.of_env,
        "getattr",
        lambda key, *a, **k: (
            "set"
            if key in {"DYNAMIC_RULE_MANUAL", "DYNAMIC_GENERIC_URL"}
            else real(key, *a, **k)
        ),
    )
    monkeypatch.setattr(request.cache, "set", lambda *a, **k: None)
    expected = {
        "digitalcriminals": "digitalcriminals",
        "dc": "digitalcriminals",
        "digital": "digitalcriminals",
        "digitals": "digitalcriminals",
        "digitalcriminal": "digitalcriminals",
        "datawhores": "datawhores",
        "xagler": "xagler",
        "rafa": "rafa",
        "manual": "manual",
        "generic": "generic",
    }
    picked = {}
    for name in expected:
        cfg = {"advanced_options": {"dynamic-mode-default": name}}
        rule = data.get_dynamic(config=cfg)
        assert rule == name, f"get_dynamic rejected {name!r}"
        monkeypatch.setattr(
            request.settings,
            "get_settings",
            lambda rule=rule: SimpleNamespace(dynamic_rules=rule),
        )
        monkeypatch.setattr(request, "curr_auth", None)
        monkeypatch.setattr(request, "last_check", None)
        picked[name] = request.get_request_auth()
    assert picked == expected
