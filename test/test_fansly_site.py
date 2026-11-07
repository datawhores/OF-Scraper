"""Fansly profiles: site selection, auth file, and the headers each request gets."""

import base64
import json
from types import SimpleNamespace

import pytest

import ofscraper.sites as sites
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.config.data as config_data
import ofscraper.utils.paths.common as common_paths
import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager import ofsession
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager
from ofscraper.sites.fansly import auth as fansly_auth
from ofscraper.sites.fansly import constants, signing
from ofscraper.sites.fansly import headers as fansly_headers
from ofscraper.sites.fansly import me as fansly_me

SESSION_ID = "100000000000000777"
TOKEN = base64.b64encode(f"{SESSION_ID}:1:2:{'ab12' * 16}".encode()).decode()
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/140.0"
DEVICE_ID = "100000000000000555"
API_URL = constants.api_url("timelinenew/100000000000000002?before=0&after=0&wallId=&contentSearch=")
CDN_URL = "https://cdn3.fansly.com/100000000000000002/100000000000000019.mp4"
OF_ONLY = {"app-token", "sign", "time", "x-bc", "user-id", "referer", "user-agent", "accept", "cookie"}


@pytest.fixture
def fansly_profile(monkeypatch, tmp_path):
    real = settings.get_settings()
    stub = SimpleNamespace(**{**dict(real), "site": "fansly", "anon": False, "auth_fail": False})
    monkeypatch.setattr(settings, "get_settings", lambda: stub)
    path = tmp_path / constants.AUTH_FILE
    fansly_auth.write_auth(
        {"authorization_token": TOKEN, "user_agent": UA, "check_key": "test-check-key1",
         "device_id": DEVICE_ID, "device_id_fetched_at": 1}, path)
    monkeypatch.setattr(fansly_auth, "auth_path", lambda: path)
    monkeypatch.setattr(signing, "client_ts", signing.ClientClock(now=lambda: 1760000000.5))
    monkeypatch.setattr(fansly_headers.signing, "client_ts", signing.client_ts)
    return path


# ------------------------------------------------------------------ signing

@pytest.mark.parametrize(
    "text,expected",
    [("", "bdcb81aee8d83"), ("a", "1c2ba782c97901"), ("hello world", "b9417d15d1014")],
)
def test_cyrb53_matches_the_published_javascript(text, expected):
    # expected values computed by the published JavaScript cyrb53 in node
    assert format(signing.cyrb53(text), "x") == expected


def test_client_check_uses_the_path_only():
    a = signing.client_check("https://apiv3.fansly.com/api/v1/account/me?ngsw-bypass=true", "k-e-y", "1")
    b = signing.client_check("https://elsewhere.example/api/v1/account/me", "k-e-y", "1")
    assert a == b == format(signing.cyrb53("k-e-y_/api/v1/account/me_1"), "x")


def test_client_ts_never_goes_backwards():
    times = iter([10.0, 9.0, 11.0])
    clock = signing.ClientClock(now=lambda: next(times))
    assert [clock(), clock(), clock()] == [10000, 10000, 11000]


# ------------------------------------------------------------------ DoD 2

@pytest.mark.parametrize("cls", [sessionManager, ofsession.OFSessionManager,
                                 ofsession.SubscriptionSessionManager])
def test_fansly_api_request_has_the_signed_headers(fansly_profile, cls):
    m = cls.__new__(cls)
    headers = m._create_headers(None, API_URL, True, False)
    assert headers == {
        "User-Agent": UA,
        "Origin": "https://fansly.com",
        "Referer": "https://fansly.com/",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "application/json, text/plain, */*",
        "authorization": TOKEN,
        "fansly-client-id": DEVICE_ID,
        "fansly-client-ts": "1760000000500",
        "fansly-client-check": format(
            signing.cyrb53(f"test-check-key1_/api/v1/timelinenew/100000000000000002_{DEVICE_ID}"), "x"),
        "fansly-session-id": SESSION_ID,
    }
    assert not OF_ONLY & set(headers)
    assert m._create_cookies() is None


def test_default_check_key_is_used_when_none_is_stored(fansly_profile):
    auth = fansly_auth.read_auth()
    auth["check_key"] = ""
    fansly_auth.write_auth(auth, fansly_profile)
    headers = fansly_headers.make_headers(API_URL)
    assert headers["fansly-client-check"] == signing.client_check(
        API_URL, constants.DEFAULT_CHECK_KEY, DEVICE_ID)


# ------------------------------------------------------------------ DoD 3

@pytest.mark.parametrize("cls", [ofsession.download_session, ofsession.metadata_session,
                                 sessionManager])
@pytest.mark.parametrize("url", [CDN_URL, "https://cdn3.fansly.com/new/1/2/media-1/stream.m3u8"])
def test_fansly_cdn_request_has_no_token_or_signing(fansly_profile, cls, url):
    m = cls.__new__(cls)
    headers = m._create_headers({"Range": "bytes=0-"}, url, True, False)
    assert headers == {
        "Range": "bytes=0-",
        "User-Agent": UA,
        "Origin": "https://fansly.com",
        "Referer": "https://fansly.com/",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "application/json, text/plain, */*",
    }
    assert m._create_cookies() is None


# ------------------------------------------------------------------ DoD 4

@pytest.fixture
def profiles(monkeypatch, tmp_path):
    monkeypatch.setattr(common_paths, "get_config_home", lambda: tmp_path)
    monkeypatch.setattr(config_data, "get_main_profile", lambda *a, **k: "main_profile")
    (tmp_path / "main_profile").mkdir()
    return tmp_path


def _merged(monkeypatch, **overrides):
    args = settings.get_args(copy=True)
    args.update(overrides)
    monkeypatch.setattr(read_args, "retriveArgs", lambda: args)
    return settings.merged_settings()


def test_site_defaults_to_onlyfans(profiles, monkeypatch):
    assert _merged(monkeypatch, site=None, profile=None).site == "onlyfans"


def test_site_override_applies_to_that_run_only(profiles, monkeypatch):
    assert _merged(monkeypatch, site="fansly", profile=None).site == "fansly"
    assert _merged(monkeypatch, site=None, profile=None).site == "onlyfans"
    assert not (profiles / "main_profile" / sites.SITE_FILE).exists()


def test_profile_site_file_is_used(profiles, monkeypatch):
    (profiles / "fans_profile").mkdir()
    sites.write_profile_site(profiles / "fans_profile", "fansly")
    assert _merged(monkeypatch, site=None, profile="fans_profile").site == "fansly"
    assert _merged(monkeypatch, site="onlyfans", profile="fans_profile").site == "onlyfans"
    assert _merged(monkeypatch, site=None, profile=None).site == "onlyfans"


def test_site_option_is_parsed():
    import ofscraper.utils.args.parse.commands.main as main

    params, _ = main.program.main(["--site", "Fansly"], standalone_mode=False)
    assert params["site"] == "fansly"
    params, _ = main.program.main([], standalone_mode=False)
    assert params["site"] is None


# ------------------------------------------------------------------ auth file and token check

def test_auth_file_round_trip_and_validation(tmp_path):
    path = tmp_path / "fansly_auth.json"
    assert fansly_auth.read_auth(path) == fansly_auth.empty()
    assert fansly_auth.problems(fansly_auth.empty())
    fansly_auth.write_auth({"authorization_token": f"Bearer {TOKEN}", "user_agent": UA}, path)
    auth = fansly_auth.read_auth(path)
    assert auth["authorization_token"] == TOKEN
    assert fansly_auth.problems(auth) == []
    assert set(json.loads(path.read_text())) == set(fansly_auth.FIELDS)
    assert fansly_auth.problems({**auth, "authorization_token": "ReplaceMe"})


def test_session_id_comes_from_the_token():
    assert fansly_auth.session_id(TOKEN) == SESSION_ID
    assert fansly_auth.session_id("not base64 !!") is None


def test_device_id_freshness():
    auth = {"device_id": "1", "device_id_fetched_at": 1000}
    assert fansly_auth.device_id_is_fresh(auth, now=1000 + 60)
    assert not fansly_auth.device_id_is_fresh(auth, now=1000 + 181 * 60)
    assert not fansly_auth.device_id_is_fresh({"device_id": ""}, now=0)


class _FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status

    def json_(self):
        return self._data


class _FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def requests(self, url, **kwargs):
        import contextlib

        self.calls.append((url, kwargs))

        @contextlib.contextmanager
        def ctx():
            yield _FakeResponse(self.routes[url.split("?")[0]])

        return ctx()


def test_token_check_fetches_device_id_then_account_me(fansly_profile):
    auth = fansly_auth.read_auth(fansly_profile)
    auth["device_id"] = ""
    fansly_auth.write_auth(auth, fansly_profile)
    me_body = {"success": True, "response": {"account": {
        "id": "100000000000000147", "username": "samplecreator4", "displayName": None}}}
    c = _FakeSession({
        constants.DEVICE_ID_URL.split("?")[0]: {"success": True, "response": "100000000000000999"},
        constants.ME_URL.split("?")[0]: me_body,
    })
    data = fansly_me.scrape_user(c)
    assert data == {"id": "100000000000000147", "username": "samplecreator4",
                    "name": "samplecreator4", "isAuth": True}
    (dev_url, dev_kw), (me_url, me_kw) = c.calls
    assert dev_url == constants.DEVICE_ID_URL and dev_kw["actions"] == []
    assert "authorization" not in dev_kw["headers"]
    assert me_url == constants.ME_URL
    assert fansly_auth.read_auth(fansly_profile)["device_id"] == "100000000000000999"


def test_token_check_fails_without_a_username():
    with pytest.raises(fansly_me.FanslyAuthError):
        fansly_me.parse_me({"success": True, "response": {"account": {}}})
    with pytest.raises(fansly_me.FanslyAuthError):
        fansly_me.parse_me({"success": False})


def test_me_api_routes_to_fansly(fansly_profile, monkeypatch):
    import ofscraper.data.api.me as me_api

    monkeypatch.setattr(fansly_me, "scrape_user", lambda: {"username": "routed"})
    assert me_api.scrape_user() == {"username": "routed"}


def test_check_cdm_is_skipped_for_fansly(fansly_profile, monkeypatch):
    import ofscraper.utils.system.network as network

    monkeypatch.setattr(settings.get_settings(), "key_mode", "cdrm")
    monkeypatch.setattr(network.sessionManager, "sessionManager",
                        lambda *a, **k: pytest.fail("no CDM request for Fansly"))
    assert network.check_cdm() is True


def test_site_name_placeholder(fansly_profile, monkeypatch):
    import ofscraper.classes.placeholder as placeholder

    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    monkeypatch.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(placeholder.common_paths, "get_save_location", lambda *a, **k: "/data")
    monkeypatch.setattr(placeholder.common_paths, "get_config_home", lambda: "/cfg")
    p = placeholder.basePlaceholder()
    p.create_variables_base()
    assert p._variables["site_name"] == "Fansly"
    monkeypatch.setattr(settings.get_settings(), "site", "onlyfans")
    p.create_variables_base()
    assert p._variables["site_name"] == "Onlyfans"
