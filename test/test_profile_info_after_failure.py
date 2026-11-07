import httpx
import pytest

import ofscraper.data.api.me as me
import ofscraper.utils.profiles.data as profile_data


@pytest.fixture
def profile(monkeypatch):
    monkeypatch.setattr(profile_data, "currentProfile", None)
    monkeypatch.setattr(profile_data, "currentData", None)
    monkeypatch.setattr(profile_data, "get_active_profile", lambda: "main_profile")


def test_failed_scrape_is_retried_on_the_next_call(profile, monkeypatch):
    def offline():
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(me, "scrape_user", offline)
    with pytest.raises(httpx.ConnectTimeout):
        profile_data.get_my_info()

    user = {"isAuth": True, "id": 1, "username": "u1", "name": "n1"}
    monkeypatch.setattr(me, "scrape_user", lambda: user)
    assert profile_data.get_my_info() == user


def test_successful_scrape_is_reused(profile, monkeypatch):
    calls = []

    def scrape_user():
        calls.append(1)
        return {"isAuth": True, "id": 1, "username": "u1", "name": "n1"}

    monkeypatch.setattr(me, "scrape_user", scrape_user)
    profile_data.get_my_info()
    profile_data.get_my_info()
    assert len(calls) == 1
