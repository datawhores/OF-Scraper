"""No part of the PostgreSQL password in a message, whatever it is made of
(#647). The addresses and passwords here are made up."""

import re
import sys
import urllib.parse

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.db.postgres as postgres
import ofscraper.utils.logs.utils.sensitive as sensitive

UNREAD = "the configured database"

# addresses PostgreSQL reads as they were meant: (address, password)
READABLE = [
    ("postgresql://scraper:12345?xyz@db.example:5432/library", "12345?xyz"),
    ("postgresql://scraper:Kq#Wz8@db.example:5432/library", "Kq#Wz8"),
    ("postgresql://scraper:Ab:Cd9@db.example/library", "Ab:Cd9"),
    ("postgresql://scraper:Zq@db.example/library", "Zq"),
    # a word the driver's own message has
    ("postgresql://scraper:failed@db.example/library", "failed"),
    ("postgresql://scraper:Mn%40Rt%3Fu%23v@db.example/library", "Mn@Rt?u#v"),
    ("postgresql://scraper@db.example/library?password=hunter2", "hunter2"),
    ("host=db.example dbname=library user=scraper password=Hg@Lm?k#9", "Hg@Lm?k#9"),
    ("host=db.example dbname=library password='Rf Yt@Ou'", "Rf Yt@Ou"),
    # a quoted password with a space, followed by another setting (#654)
    ("password='a b' host=db.example dbname=library", "a b"),
    ("password=s3cret host=db.example dbname=library", "s3cret"),
]

# addresses it can't read, or reads another way than meant
UNREADABLE = [
    # what follows the first @ is taken for the server
    ("postgresql://scraper:p@ssw@rd@db.example/library", "p@ssw@rd"),
    # the / ends the login part before the @
    ("postgresql://scraper:Xy/Zw42@db.example/library", "Xy/Zw42"),
    # a space in a URL
    ("postgresql://scraper:Qj Vwx@db.example/library", "Qj Vwx"),
    # PostgreSQL decodes %70assword: host scraper, port Secret
    ("postgresql://scraper:Secret/Pw?%70assword=1@db.example/library", "Secret/Pw?%70assword=1"),
    ("postgresql://scraper:Secret/Pw?sslmode=disable&%70assword=1@db.example/library", "Secret/Pw?sslmode=disable&%70assword=1"),
    ("postgresql://scraper:Secret/Pw?password=1@db.example/library", "Secret/Pw?password=1"),
    # read as host Cd, database Ef, and the password after the ?
    ("postgresql://scraper:Ab@Cd/Ef?password=x@db.example/library", "Ab@Cd/Ef?password=x"),
    # where PostgreSQL stops reading
    ("postgresql://scraper:hunter2\x00@db.example/library", "hunter2"),
    # %-escapes that aren't UTF-8, or aren't escapes
    ("postgresql://scraper:YD%BDS@127.0.0.1:5432/library", "YD%BDS"),
    ("postgresql://scraper:k%aCs@127.0.0.1:5432/library", "k%aCs"),
    ("postgresql://scraper:%f01w@127.0.0.1:5432/library", "%f01w"),
    ("postgresql://scraper:98%B3X@127.0.0.1:5432/library", "98%B3X"),
    ("postgresql://scraper:Ab%zz@127.0.0.1:5432/library", "Ab%zz"),
    # a mistyped scheme
    ("postgresql:/scraper:SECRETpw@db.example/library", "SECRETpw"),
]


@pytest.fixture
def psycopg():
    return pytest.importorskip("psycopg")


@pytest.fixture
def no_driver(monkeypatch):
    monkeypatch.setitem(sys.modules, "psycopg", None)
    monkeypatch.setitem(sys.modules, "psycopg.conninfo", None)


@pytest.mark.parametrize("address, password", READABLE)
def test_a_readable_address_names_its_server_and_hides_its_password(psycopg, address, password):
    # the host=... spelling isn't described, as before
    shown = postgres.describe(address)
    assert shown.startswith("db.example") if "://" in address else shown == UNREAD
    quoted = urllib.parse.quote(password, safe="")
    for said in (
        f"authentication failed (given {password})",
        f"given {quoted}",
        f"connection to {address} failed",
    ):
        shown = postgres.masked(said, address)
        assert password not in shown and quoted not in shown


@pytest.mark.parametrize("address, password", UNREADABLE)
def test_an_unreadable_address_is_one_sentence_naming_nothing(psycopg, monkeypatch, address, password):
    assert postgres.describe(address) == UNREAD

    def quotes_it(*args, **kwargs):
        raise psycopg.ProgrammingError(f'missing "=" after "{address}" in connection info string')

    monkeypatch.setattr(psycopg, "connect", quotes_it)
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    monkeypatch.setattr(postgres, "url", lambda: address)
    for start in (lambda: postgres.Reader(address), lambda: postgres.POSTGRES._open_pool("onlyfans", 30)):
        with pytest.raises(postgres.Unreadable) as raised:
            start()
        # the one sentence, the same for every address
        assert str(raised.value) == str(postgres.Unreadable())
        # and the driver's error, which quotes the address, isn't kept
        assert raised.value.__cause__ is None and raised.value.__suppress_context__


def test_the_driver_error_of_an_unreadable_address_is_not_shown(psycopg):
    address = "postgresql://scraper:Xy/Zw42@db.example/library"
    error = psycopg.OperationalError('invalid integer value "Xy" for connection option "port"')
    assert str(postgres.POSTGRES._unavailable(error, address)) == str(postgres.Unreadable())


@pytest.mark.parametrize("address, password", READABLE + UNREADABLE)
def test_without_the_driver_no_address_is_described(no_driver, address, password):
    assert postgres.describe(address) == UNREAD
    assert postgres.describe("postgresql://scraper:s3cret@db.example:5433/library") == UNREAD


def test_a_normal_address_still_names_the_server(psycopg):
    address = "postgresql://scraper:s3cret@db.example:5433/library"
    assert postgres.describe(address) == "db.example:5433/library"
    masked = postgres.masked(f"could not reach db.example:5433 (s3cret, {address})", address)
    assert masked == "could not reach db.example:5433 ({hidden}, {hidden})"


def test_the_password_is_hidden_where_it_is_not_part_of_a_longer_word(psycopg):
    address = "postgresql://scraper:Zq@db.example/library"
    assert postgres.masked("Zqx given Zq.", address) == "Zqx given {hidden}."
    address = "postgresql://scraper:word@db.example/library"
    said = 'FATAL: password authentication failed for user "scraper" (word)'
    assert postgres.masked(said, address) == said.replace("(word)", "({hidden})")


@pytest.mark.parametrize("password", ["only-for-this-job", "not-the-password", "only-for-this-test"])
def test_the_words_around_the_password_stay(psycopg, password):
    address = f"postgresql://scraper:{urllib.parse.quote(password, safe='')}@db.example:5432/library"
    said = (
        'connection to server at "db.example", port 5432 failed: FATAL: password'
        f' authentication failed for user "scraper" (given {password} for the test);'
        " cannot execute INSERT in a read-only transaction; this is only for the test"
    )
    shown = postgres.masked(said, address)
    assert password not in shown
    assert "(given {hidden} for the test)" in shown
    for word in ("only", "for", "this", "the", "password", "read-only"):
        assert word in shown
    assert postgres.describe(address) == "db.example:5432/library"


# #654: an unquoted password ends at the space, and the rest is read as
# another setting, which the driver's errors quote: every value is hidden
@pytest.mark.parametrize("setting", ["host", "hostaddr", "sslmode", "dbname", "user"])
def test_every_value_of_a_keyword_address_is_hidden(psycopg, setting):
    address = f"host=db.example dbname=library user=scraper password=Xy7 {setting}=Zebra9"
    said = f'connection to server failed: invalid {setting} value: "Zebra9" (given Xy7)'
    shown = postgres.masked(said, address)
    assert "Xy7" not in shown and "Zebra9" not in shown
    assert shown == f'connection to server failed: invalid {setting} value: "{{hidden}}" (given {{hidden}})'


SPLIT = "host=db.example user=scraper password=Xy7"


@pytest.mark.parametrize(
    "address, host",
    [
        # each host of a list is quoted on its own
        (f"{SPLIT} host=Qw8Secret.invalid,Zebra9Secret.invalid", "Qw8Secret.invalid"),
        (f"{SPLIT} host=Qw8Secret.invalid,Zebra9Secret.invalid", "Zebra9Secret.invalid"),
        # a :// that isn't at the start doesn't make it a URL
        (f"{SPLIT} host=Zebra9Secret.invalid application_name=a://b", "Zebra9Secret.invalid"),
        (f"{SPLIT}://Zebra9Secret.invalid host=Zebra9Secret.invalid", "Zebra9Secret.invalid"),
    ],
)
def test_a_keyword_host_is_hidden_in_a_list_or_beside_a_url(psycopg, address, host):
    said = f"connection failed: failed to resolve host '{host}': No such host is known."
    assert postgres.masked(said, address) == said.replace(host, "{hidden}")


def test_a_one_character_keyword_value_is_not_hidden(psycopg):
    address = f"{SPLIT} host=Zebra9 connect_timeout=1"
    said = "match 1 host (Zebra9, Xy7)"
    assert postgres.masked(said, address) == "match 1 host ({hidden}, {hidden})"


def test_the_values_of_a_keyword_address_are_hidden_from_messages_only(psycopg, monkeypatch):
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    address = "host=db.example sslmode=require user=scraper password=Xy7 host=Zebra9"
    postgres.POSTGRES._hide_password(address)
    line = "sslmode is require (Xy7)"
    for pattern, replacement in sensitive._USER_ADDED_PATTERNS.items():
        line = re.sub(pattern, replacement, line)
    assert line == "sslmode is require ({hidden})"
    assert postgres.masked('could not translate host name "Zebra9"', address) == (
        'could not translate host name "{hidden}"'
    )


def test_a_one_character_password_is_not_hidden_from_every_log_line(psycopg, monkeypatch):
    monkeypatch.setattr(sensitive, "_USER_ADDED_PATTERNS", {})
    address = "postgresql://scraper:!@db.example/library"
    postgres.POSTGRES._hide_password(address)
    assert re.escape("!") not in sensitive._USER_ADDED_PATTERNS
    assert "!" not in sensitive._USER_ADDED_PATTERNS
    # a message still hides it
    assert postgres.masked("given !", address) == "given {hidden}"
