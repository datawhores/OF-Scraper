"""{my_id} holds the account's numeric id, not its display name (#206)."""

from types import SimpleNamespace

import pytest

import ofscraper.classes.placeholder as placeholder


@pytest.fixture
def base(monkeypatch):
    monkeypatch.setattr(placeholder.profile_data, "get_my_info", lambda: {"id": 12345, "name": "Display Name", "username": "me_user"})
    monkeypatch.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(placeholder.common_paths, "get_save_location", lambda *a, **k: "/data")
    monkeypatch.setattr(placeholder.common_paths, "get_config_home", lambda: "/cfg")
    monkeypatch.setattr(placeholder, "site_save_location", lambda: "/data")


def _variables(monkeypatch, anon):
    fake = SimpleNamespace(anon=anon)
    monkeypatch.setattr(placeholder.settings, "get_settings", lambda: fake)
    monkeypatch.setattr(placeholder.me.settings, "get_settings", lambda: fake)
    p = placeholder.basePlaceholder()
    p.create_variables_base()
    return p._variables


def test_my_id_is_the_account_id(base, monkeypatch):
    v = _variables(monkeypatch, anon=False)
    assert v["my_id"] == 12345
    assert v["my_username"] == "me_user"


def test_my_id_in_anon_mode(base, monkeypatch):
    v = _variables(monkeypatch, anon=True)
    assert v["my_id"] == "anon"
    assert v["my_username"] == "anon"
