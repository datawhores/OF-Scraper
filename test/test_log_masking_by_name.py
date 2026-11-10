"""Auth values are masked in logs by name, not only when auth.json holds them,
and the home folder name is masked only as a whole name."""

import logging

import pytest

import ofscraper.managers.sessionmanager.cert as cert
import ofscraper.utils.logs.utils.sensitive as sensitive
from ofscraper.utils.logs.classes.classes import DiscordFormatter, LogFileFormatter

# values auth.json doesn't hold, so masking by value can't catch them
NEW_SESS = "NewSessionFromSetCookie0123456789abcdef"
AUTH_ID = "246813579"
AUTH_UID = "uid_0123456789abcdef"
XBC = "UnknownXbcValue0123456789abcdef"


@pytest.fixture(autouse=True)
def clean_patterns(monkeypatch):
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    monkeypatch.setattr(sensitive.paths, "get_username", lambda: None)


def formatted(formatter, msg):
    record = logging.LogRecord("shared", logging.DEBUG, __file__, 1, msg, None, None)
    return formatter.format(record)


# (log line, the secrets in it, the labels that must replace them)
LEAKS = [
    # a new session cookie OnlyFans sends back
    (f"set-cookie: sess={NEW_SESS}; path=/; secure", [NEW_SESS], ["sess={sess}"]),
    # the cookie header of a failed request, as the header dump logs it
    (
        "requests headers "
        + str({"cookie": f"sess={NEW_SESS}; auth_id={AUTH_ID}; auth_uid_{AUTH_ID}={AUTH_UID}"}),
        [NEW_SESS, AUTH_ID, AUTH_UID],
        ["sess={sess}", "auth_id={hidden}", "auth_uid={hidden}"],
    ),
    # header and cookie dicts
    (
        "requests headers " + str({"x-bc": XBC, "user-id": AUTH_ID, "user-agent": "ua"}),
        [XBC, AUTH_ID],
        ["'x-bc': '{x-bc}'", "'user-id': '{hidden}'", "'user-agent': 'ua'"],
    ),
    (
        "cookies " + str({"sess": NEW_SESS, "auth_id": int(AUTH_ID), f"auth_uid_{AUTH_ID}": AUTH_UID}),
        [NEW_SESS, AUTH_ID, AUTH_UID],
        ["'sess': '{sess}'", "'auth_id': {hidden}", "'auth_uid': '{hidden}'"],
    ),
    # JSON
    ('{"sess":"' + NEW_SESS + '","auth_id":"' + AUTH_ID + '"}', [NEW_SESS, AUTH_ID], ['"sess":"{sess}"']),
    # a header line, and the equals form of a query string
    (f"x-bc: {XBC}\nUser-Id: {AUTH_ID}", [XBC, AUTH_ID], ["x-bc: {x-bc}", "User-Id: {hidden}"]),
    (f"?x-bc={XBC}&user-id={AUTH_ID}", [XBC, AUTH_ID], ["x-bc={x-bc}", "user-id={hidden}"]),
    # the auth_uniq_<user id> cookie, set-cookie and dict form
    (
        f"set-cookie: auth_uniq_{AUTH_ID}={AUTH_UID}; path=/ "
        + str({f"auth_uniq_{AUTH_ID}": AUTH_UID}),
        [AUTH_ID, AUTH_UID],
        ["auth_uniq={hidden}", "'auth_uniq': '{hidden}'"],
    ),
]


@pytest.mark.parametrize("formatter", [LogFileFormatter, DiscordFormatter])
@pytest.mark.parametrize("line, secrets, labels", LEAKS)
def test_auth_values_are_masked_by_name(formatter, line, secrets, labels):
    out = formatted(formatter(), line)
    for secret in secrets:
        assert secret not in out
    for label in labels:
        assert label in out
    assert "LOGGING ERROR" not in out


@pytest.mark.parametrize(
    "line",
    [
        "assess=3 sessions remaining, session=ok",
        "the user-id is checked; x-bc header set",
        "the user-id: header is missing",
        "posted by a creator: 'subscribers': 12",
    ],
)
def test_ordinary_text_is_left_alone(line):
    assert formatted(LogFileFormatter(), line) == line


@pytest.mark.parametrize(
    "line, expected",
    [
        ("danger: wrote /home/dan/log.txt", "danger: wrote /home/{home_directory}/log.txt"),
        ("saved dan_log.txt for Dan", "saved {home_directory}_log.txt for Dan"),
        ("dan", "{home_directory}"),
        ("Jordan and dana", "Jordan and dana"),
    ],
)
def test_home_folder_name_is_masked_only_as_a_whole_name(monkeypatch, line, expected):
    monkeypatch.setattr(sensitive.paths, "get_username", lambda: "dan")
    assert formatted(LogFileFormatter(), line) == expected


def test_tls_seed_is_not_logged(monkeypatch, caplog):
    """The cipher order is seeded with the auth_id (or the username or OS
    user name); the debug line about it must not show it."""
    monkeypatch.setattr(cert, "_CONFIG_CACHE", {})
    monkeypatch.setattr(cert, "_fansly_seed", lambda: None)
    monkeypatch.setattr(
        cert.auth_requests.auth_file, "read_auth", lambda: {"auth_id": AUTH_ID}
    )
    with caplog.at_level(logging.DEBUG, logger="shared"):
        cert.create_custom_ssl_context()
    assert "stable TLS fingerprint" in caplog.text
    assert AUTH_ID[:10] not in caplog.text
