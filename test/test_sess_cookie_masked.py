"""The OnlyFans session cookie must never reach a log file unmasked (#165)."""

import logging

import pytest

import ofscraper.utils.auth.file as auth_file
import ofscraper.utils.logs.utils.sensitive as sensitive
from ofscraper.utils.logs.classes.classes import DiscordFormatter, LogFileFormatter

# fake value with regex metacharacters, so an unescaped pattern would misbehave
SESS = "fake.sess+value/with?regex*chars"


@pytest.fixture(autouse=True)
def clean_patterns(monkeypatch):
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    monkeypatch.setattr(sensitive.paths, "get_username", lambda: None)


@pytest.fixture
def fake_auth(monkeypatch):
    auth = {"sess": SESS, "auth_id": "1", "auth_uid": "", "user_agent": "ua", "x-bc": "bc"}
    monkeypatch.setattr(auth_file.auth_dict, "get_auth_dict", lambda *a, **k: dict(auth))
    monkeypatch.setattr(auth_file.auth_schema, "auth_schema", lambda a: dict(a))
    monkeypatch.setattr(auth_file.auth_schema, "auth_key_missing", lambda a: False)
    monkeypatch.setattr(auth_file.auth_schema, "auth_key_null", lambda a: False)
    return auth


def formatted(formatter, msg):
    record = logging.LogRecord("shared", logging.DEBUG, __file__, 1, msg, None, None)
    return formatter.format(record)


# the forms the value is logged in: the failed-request header dump in
# sessionmanager (a dict repr holding the cookie header), a cookie dict, JSON
LINES = [
    "requests headers " + str({"cookie": f"sess={SESS}; auth_id=1", "user-agent": "ua"}),
    "cookies " + str({"sess": SESS, "auth_id": "1"}),
    '{"sess": "' + SESS + '"}',
]


@pytest.mark.parametrize("formatter", [LogFileFormatter, DiscordFormatter])
@pytest.mark.parametrize("line", LINES)
def test_sess_is_masked_once_auth_is_read(fake_auth, formatter, line):
    auth_file.read_auth()
    out = formatted(formatter(), line)
    assert SESS not in out
    assert "{sess}" in out
    assert "LOGGING ERROR" not in out


def test_reading_auth_again_does_not_add_patterns(fake_auth):
    # add_cookies() reads auth on every request
    for _ in range(5):
        auth_file.read_auth()
    assert len(sensitive._USER_ADDED_PATTERNS) == 1


@pytest.mark.parametrize("home", ["pi", "root"])
def test_home_folder_name_inside_the_value_doesnt_expose_it(fake_auth, monkeypatch, home):
    # the home-folder rule used to run first and break the value apart
    value = f"k3{home}9xq2m7abcdz0r5t8w1y4ue"
    fake_auth["sess"] = value
    monkeypatch.setattr(sensitive.paths, "get_username", lambda: home)
    auth_file.read_auth()
    out = formatted(LogFileFormatter(), f"requests headers {{'cookie': 'sess={value}; auth_id=1'}}")
    assert "sess={sess}" in out
    assert value[len(home) + 2:] not in out


def test_a_short_value_masks_nothing(fake_auth):
    # a stray short value would otherwise mask ordinary words everywhere
    fake_auth["sess"] = "a"
    auth_file.read_auth()
    assert sensitive._USER_ADDED_PATTERNS == {}
    out = formatted(LogFileFormatter(), "failed: https://onlyfans.com/x")
    assert out.endswith("failed: https://onlyfans.com/x")


def test_a_short_user_id_doesnt_split_an_ip_address(monkeypatch):
    # run-time patterns come after the built-in rules, so the IP rule still
    # sees the whole address
    sensitive.add_sensitive_pattern("15", "userid")
    out = formatted(LogFileFormatter(), "ip 10.15.2.3")
    assert out.endswith("ip {ip_address}")


def test_audio_pssh_with_regex_characters_is_masked():
    import asyncio
    from types import SimpleNamespace

    import ofscraper.classes.of.media as media

    # base64 with "+": as a raw regex "A+" means "one or more A", so the
    # value didn't match itself and was logged in full
    pssh = "AAAAW3Bzc2gAAA+/AAAA=="

    async def run():
        loop = asyncio.get_running_loop()

        def done(value):
            fut = loop.create_future()
            fut.set_result(value)
            return fut

        prot = SimpleNamespace(value=None, pssh=[SimpleNamespace(pssh=pssh)])
        repr_ = SimpleNamespace(base_urls=[SimpleNamespace(base_url_value="a.mp4")])
        fake = SimpleNamespace(
            _audio_adaptation_set=done(SimpleNamespace(content_protections=[prot])),
            selected_audio_representation=done(repr_),
            id=1, post_id=2,
        )
        return await media.Media.mpd_audio_helper(fake)

    assert asyncio.run(run())["pssh"] == pssh
    out = formatted(LogFileFormatter(), f"license request for {pssh}")
    assert pssh not in out and "pssh_code" in out
    assert "LOGGING ERROR" not in out


def me_response(username, name):
    import contextlib
    from types import SimpleNamespace

    data = {"isAuth": True, "id": 123456789, "username": username, "name": name}

    class FakeSession:
        @contextlib.contextmanager
        def requests(self, url):
            yield SimpleNamespace(json_=lambda: data)

    return FakeSession()


@pytest.mark.parametrize("name", ["Jane (VIP)", "A+B", "Jane (VIP", "*Star*", "Plain Name"])
def test_display_name_with_symbols_is_masked(name):
    import ofscraper.data.api.me as me

    me._scraper_user_helper(me_response("plainuser1", name))
    out = formatted(LogFileFormatter(), f"hello {name} and plainuser1 here")
    assert name not in out
    assert "plainuser1" not in out
    assert "LOGGING ERROR" not in out


def test_username_still_masked_only_as_a_whole_word():
    import ofscraper.data.api.me as me

    me._scraper_user_helper(me_response("ann", "Ann Example"))
    out = formatted(LogFileFormatter(), "ann is here; channel stays")
    assert "channel stays" in out  # "ann" inside a longer word is left alone
    assert not out.endswith("ann is here; channel stays")


def test_an_empty_display_name_masks_nothing():
    import ofscraper.data.api.me as me

    me._scraper_user_helper(me_response("plainuser1", ""))
    out = formatted(LogFileFormatter(), "a line with spaces")
    assert out.endswith("a line with spaces")


XBC = "fake.xbc+value/with?regex*chars"


@pytest.mark.parametrize("formatter", [LogFileFormatter, DiscordFormatter])
@pytest.mark.parametrize(
    "line",
    [
        "requests headers " + str({"x-bc": XBC, "user-agent": "ua"}),
        '{"x-bc": "' + XBC + '"}',
    ],
)
def test_xbc_is_masked_once_auth_is_read(fake_auth, formatter, line):
    # x-bc is an auth.json credential sent as a header on every request (#243)
    fake_auth["x-bc"] = XBC
    auth_file.read_auth()
    out = formatted(formatter(), line)
    assert XBC not in out
    assert "{x-bc}" in out
    assert "LOGGING ERROR" not in out


def test_a_short_xbc_masks_nothing(fake_auth):
    fake_auth["x-bc"] = "bc"
    auth_file.read_auth()
    assert list(sensitive._USER_ADDED_PATTERNS.values()) == ["{sess}"]


SIGN = "41:0123456789abcdef0123456789abcdef01234567:1a2:6618"


@pytest.mark.parametrize("formatter", [LogFileFormatter, DiscordFormatter])
@pytest.mark.parametrize(
    "line",
    [
        "requests headers " + str({"sign": SIGN, "time": "1700000000123"}),
        '{"sign": "' + SIGN + '"}',
        "headers " + str({"Sign": SIGN}),
    ],
)
def test_sign_header_is_masked(formatter, line):
    # the signature changes per request, so it's masked by its header name
    out = formatted(formatter(), line)
    assert SIGN not in out
    assert "{sign}" in out
    assert "1700000000123" in out or "time" not in line
    assert "LOGGING ERROR" not in out


def test_sign_rule_leaves_other_text_alone():
    line = "design: 'x' signed in, sign of the times"
    out = formatted(LogFileFormatter(), line)
    assert out.endswith(line)


def test_failed_request_repr_shows_no_credentials(fake_auth):
    # the leak in #243: an aiohttp error's repr holds the request headers
    from aiohttp import ClientResponseError, RequestInfo
    from multidict import CIMultiDict, CIMultiDictProxy
    from yarl import URL

    fake_auth["x-bc"] = XBC
    auth_file.read_auth()
    url = URL("https://example.invalid/api2/v2/posts/paid")
    headers = CIMultiDictProxy(
        CIMultiDict(
            {"x-bc": XBC, "sign": SIGN, "Cookie": f"auth_id=1; sess={SESS}"}
        )
    )
    error = ClientResponseError(
        RequestInfo(url, "GET", headers, url), (), status=429, message="Too Many Requests"
    )
    out = formatted(LogFileFormatter(), f"scan failed: {error!r}")
    for secret in (XBC, SIGN, SESS):
        assert secret not in out
    assert "LOGGING ERROR" not in out


def test_empty_sess_registers_nothing(fake_auth):
    fake_auth["sess"] = ""
    auth_file.read_auth()
    assert sensitive._USER_ADDED_PATTERNS == {}
