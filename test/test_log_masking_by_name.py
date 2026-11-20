"""Auth values are masked in logs by name, not only when auth.json holds them,
and the home folder name is masked only as a whole name."""

import logging
from http.cookies import SimpleCookie

import pytest

import ofscraper.managers.sessionmanager.cert as cert
import ofscraper.utils.logs.utils.sensitive as sensitive
from ofscraper.utils.logs.classes.classes import DiscordFormatter, LogFileFormatter

# values auth.json doesn't hold, so masking by value can't catch them
NEW_SESS = "NewSessionFromSetCookie0123456789abcdef"
AUTH_ID = "246813579"
AUTH_UID = "uid_0123456789abcdef"
XBC = "UnknownXbcValue0123456789abcdef"
FP = "fingerprint0123456789abcdef"
ST = "stValue0123456789abcdef"
CSRF = "csrfToken0123456789"
HASH = "authHash0123456789"
CF_POLICY = "eyJTdGF0ZW1lbnQiOiJtYWRlLXVwIn0_"
CF_SIG = "MadeUpSignature0123~abc"
CF_KEY = "KMADEUPKEYPAIR0"
DEVICE_ID = "987654321012345678"
SESSION_ID = "876543210123456789"


def _simple_cookie():
    jar = SimpleCookie()
    for name, value in [
        ("sess", NEW_SESS), ("auth_id", AUTH_ID), (f"auth_uid_{AUTH_ID}", AUTH_UID),
        ("fp", FP), ("st", ST), ("csrf", CSRF), ("auth_hash", HASH),
        ("CloudFront-Policy", CF_POLICY), ("CloudFront-Signature", CF_SIG),
        ("CloudFront-Key-Pair-Id", CF_KEY),
    ]:
        jar[name] = value
    return jar


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
    # cookies OnlyFans sets, which the cookie jar sends back
    (
        f"set-cookie: fp={FP}; path=/ set-cookie: st={ST}; path=/ "
        + str({"cookie": f"sess={NEW_SESS}; fp={FP}; st={ST}; csrf={CSRF}; auth_hash={HASH}"}),
        [NEW_SESS, FP, ST, CSRF, HASH],
        ["fp={hidden}", "st={hidden}", "csrf={hidden}", "auth_hash={hidden}"],
    ),
    (
        "cookies " + str({"fp": FP, "st": ST, "csrf": CSRF}) + ' {"auth_hash":"' + HASH + '"}',
        [FP, ST, CSRF, HASH],
        ["'fp': '{hidden}'", "'st': '{hidden}'", "'csrf': '{hidden}'", '"auth_hash":"{hidden}"'],
    ),
    # the CloudFront cookies of a signed stream: a Cookie header and a dict
    (
        f"Cookie: CloudFront-Policy={CF_POLICY}; CloudFront-Signature={CF_SIG}; "
        f"CloudFront-Key-Pair-Id={CF_KEY}",
        [CF_POLICY, CF_SIG, CF_KEY],
        ["CloudFront-Policy={hidden}", "CloudFront-Signature={hidden}", "CloudFront-Key-Pair-Id={hidden}"],
    ),
    (
        "cookies "
        + str({"CloudFront-Policy": CF_POLICY, "CloudFront-Signature": CF_SIG, "CloudFront-Key-Pair-Id": CF_KEY}),
        [CF_POLICY, CF_SIG, CF_KEY],
        ["'CloudFront-Policy': '{hidden}'", "'CloudFront-Key-Pair-Id': '{hidden}'"],
    ),
    # a SimpleCookie repr (aiohttp's response.cookies): name='value'
    (
        "response cookies " + repr(_simple_cookie()),
        [NEW_SESS, AUTH_ID, AUTH_UID, FP, ST, CSRF, HASH, CF_POLICY, CF_SIG, CF_KEY],
        ["sess='{sess}'", "auth_id='{hidden}'", "auth_uid='{hidden}'", "fp='{hidden}'",
         "st='{hidden}'", "csrf='{hidden}'", "auth_hash='{hidden}'", "CloudFront-Signature='{hidden}'"],
    ),
    # Fansly's device and session IDs: header dict, JSON, header line, query
    (
        "requests headers " + str({"fansly-client-id": DEVICE_ID, "fansly-session-id": SESSION_ID}),
        [DEVICE_ID, SESSION_ID],
        ["'fansly-client-id': '{hidden}'", "'fansly-session-id': '{hidden}'"],
    ),
    (
        '{"fansly-client-id":"' + DEVICE_ID + '","fansly-session-id":' + SESSION_ID + "}",
        [DEVICE_ID, SESSION_ID],
        ['"fansly-client-id":"{hidden}"', '"fansly-session-id":{hidden}'],
    ),
    (
        f"Fansly-Client-Id: {DEVICE_ID}\nfansly-session-id: {SESSION_ID} "
        f"?fansly-client-id={DEVICE_ID}&x=1",
        [DEVICE_ID, SESSION_ID],
        ["Fansly-Client-Id: {hidden}", "fansly-session-id: {hidden}", "fansly-client-id={hidden}&x=1"],
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
        "first=1, test=2, fps=30, list='st'",
        "no fansly-client-id header yet, the fansly-session-id is unknown",
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


@pytest.mark.parametrize(
    "line, expected",
    [
        ("wrote /Users/Dan/log.txt", "wrote /Users/{home_directory}/log.txt"),
        ("wrote /home/DAN", "wrote /home/{home_directory}"),
        (r"wrote C:\Users\DAN\log.txt", r"wrote C:\Users\{home_directory}\log.txt"),
        # a Windows path in a repr has its backslashes doubled
        (r"'C:\\Users\\Dan\\x'", r"'C:\\Users\\{home_directory}\\x'"),
        (r"C:\Users\DaN_old\x", r"C:\Users\{home_directory}_old\x"),
        # not part of a longer name, and not outside a path
        ("/Users/Danielle/x and Dan said", "/Users/Danielle/x and Dan said"),
    ],
)
def test_home_folder_in_a_path_is_masked_whatever_its_case(monkeypatch, line, expected):
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
