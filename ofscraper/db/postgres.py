"""The optional PostgreSQL engine (#608).

SQLite keeps one file per creator. PostgreSQL keeps one set of tables per
site (a schema named after the site), shared by every creator, with each row
carrying its creator's model_id. The table modules run the same SQL on both;
this module is everything that differs:

- the tables, with PostgreSQL's own types, made at the current layout
- the connection pool, and a cursor that takes the `?` placeholders
- values going in and coming out, so the callers see what SQLite gave them
- which errors a retry can fix

The driver (psycopg) is an optional install, imported only when a database
URL is set.
"""

import atexit
import functools
import logging
import os
import re
import sys
import threading
import urllib.parse

import ofscraper.utils.of_env.of_env as of_env

log = logging.getLogger("shared")

URL_KEY = "OFSC_DATABASE_URL"
# the oldest release still supported by PostgreSQL when this was written
MIN_SERVER = 15
INSTALL_HINT = 'pip install "{dist}[postgres]"'
# async operations run one at a time; the rest are reads from other threads
POOL_SIZE = 4
# the longest wait for a connection from the pool, in seconds
CHECKOUT_TIMEOUT = 30
# the errors a retry can fix: two writers in each other's way (40001,
# 40P01), a lock not freed in time (55P03), the server restarting (57P01 to
# 57P03). Class 08, a lost connection, is one too. Not a full disk, a server
# out of memory or connections, or a cancelled query
RETRY_STATES = frozenset({"40001", "40P01", "55P03", "57P01", "57P02", "57P03"})
CONNECT_TIMEOUT = 15
# the longest one read on a tool's own connection (Reader) may take, in
# seconds: what the scraper's database timeout is unless it is changed
READ_TIMEOUT = 300

# Made at the current layout: the steps that upgrade an old SQLite file never
# run here. test_db_postgres compares these with SQLite's tables, column by
# column. Ids are 64-bit, yes/no columns are booleans and dates are
# timestamps, so that other tools can query the database sensibly.
#
# Three ids are text, because they aren't always numbers: a profile picture
# is saved as media whose media_id and post_id are hashes, and a label's id
# can be a word ("archived"). SQLite's INTEGER columns take those as they
# come; here the columns are TEXT, and a whole number in one is read back as
# a number (see LOOSE_IDS), as SQLite gives it.
TABLES = {
    "medias": """
CREATE TABLE IF NOT EXISTS medias (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    media_id TEXT,
    post_id TEXT NOT NULL,
    link TEXT,
    directory TEXT,
    filename TEXT,
    size BIGINT,
    api_type TEXT,
    media_type TEXT,
    preview BOOLEAN,
    linked BOOLEAN,
    downloaded BOOLEAN,
    created_at TIMESTAMPTZ,
    posted_at TIMESTAMPTZ,
    duration TEXT,
    unlocked BOOLEAN,
    hash TEXT,
    model_id BIGINT NOT NULL,
    skip_permanent BOOLEAN,
    UNIQUE (media_id, model_id, post_id)
)""",
    "posts": """
CREATE TABLE IF NOT EXISTS posts (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    post_id BIGINT NOT NULL,
    text TEXT,
    price NUMERIC,
    paid BOOLEAN,
    archived BOOLEAN,
    pinned BOOLEAN,
    stream BOOLEAN,
    opened BOOLEAN,
    created_at TIMESTAMPTZ,
    model_id BIGINT NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE,
    purchase_type TEXT,
    mentions TEXT,
    UNIQUE (post_id, model_id)
)""",
    "messages": """
CREATE TABLE IF NOT EXISTS messages (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    post_id BIGINT NOT NULL,
    text TEXT,
    price NUMERIC,
    paid BOOLEAN,
    archived BOOLEAN,
    created_at TIMESTAMPTZ,
    user_id BIGINT,
    model_id BIGINT NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE,
    group_id TEXT,
    UNIQUE (post_id, model_id)
)""",
    "stories": """
CREATE TABLE IF NOT EXISTS stories (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    post_id BIGINT NOT NULL,
    text TEXT,
    price NUMERIC,
    paid BOOLEAN,
    archived BOOLEAN,
    created_at TIMESTAMPTZ,
    model_id BIGINT NOT NULL,
    UNIQUE (post_id, model_id)
)""",
    "others": """
CREATE TABLE IF NOT EXISTS others (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    post_id BIGINT NOT NULL,
    text TEXT,
    price NUMERIC,
    paid BOOLEAN,
    archived BOOLEAN,
    created_at TIMESTAMPTZ,
    model_id BIGINT NOT NULL,
    UNIQUE (post_id, model_id)
)""",
    "products": """
CREATE TABLE IF NOT EXISTS products (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    post_id BIGINT NOT NULL,
    text TEXT,
    price NUMERIC,
    paid BOOLEAN,
    archived BOOLEAN,
    created_at TIMESTAMPTZ,
    title TEXT,
    model_id BIGINT NOT NULL,
    UNIQUE (post_id, model_id)
)""",
    "labels": """
CREATE TABLE IF NOT EXISTS labels (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    label_id TEXT,
    name TEXT,
    type TEXT,
    post_id BIGINT,
    model_id BIGINT NOT NULL,
    UNIQUE (post_id, label_id, model_id)
)""",
    "profiles": """
CREATE TABLE IF NOT EXISTS profiles (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    UNIQUE (user_id, username)
)""",
    "models": """
CREATE TABLE IF NOT EXISTS models (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_id BIGINT NOT NULL,
    UNIQUE (model_id)
)""",
    "schema_flags": """
CREATE TABLE IF NOT EXISTS schema_flags (
    flag_name TEXT PRIMARY KEY,
    flag_value TEXT
)""",
}
TABLE_COLUMNS = {
    table: tuple(
        line.split()[0]
        for line in create.splitlines()[2:]
        if line.startswith("    ") and not line.strip().startswith("UNIQUE")
    )
    for table, create in TABLES.items()
}
_COLUMN_LINES = {
    table: [
        line.split()
        for line in create.splitlines()[2:]
        if line.startswith("    ") and not line.strip().startswith("UNIQUE")
    ]
    for table, create in TABLES.items()
}
# each column's type, and the columns that can't be empty: what the import
# of SQLite files converts and checks by
COLUMN_TYPES = {
    table: {words[0]: words[1].rstrip(",") for words in lines}
    for table, lines in _COLUMN_LINES.items()
}
REQUIRED = {
    table: {
        words[0]
        for words in lines
        if "NOT NULL" in " ".join(words) or "PRIMARY KEY" in " ".join(words)
    }
    for table, lines in _COLUMN_LINES.items()
}
# the columns that together name one row of a table
UNIQUE_KEYS = {
    table: [
        tuple(part.strip() for part in line.split("(")[1].rstrip("),").split(","))
        for line in create.splitlines()
        if line.strip().startswith("UNIQUE")
    ]
    for table, create in TABLES.items()
}
# The unique keys start with the row's own id; nearly every read asks for one
# creator's rows
CREATOR_INDEXES = ("medias", "posts", "messages", "stories", "others", "products", "labels")
# The columns added since the first version that could use PostgreSQL, each
# with the upgrade step that adds it to a SQLite file: (step, table, columns).
# A database made before a step gets its columns at the next start (see
# PostgresBackend._add_columns); a new one is made with them
ADDED_COLUMNS = (
    ("profiles_seen_at", "profiles", ("first_seen_at", "last_seen_at")),
)


class PostgresUnavailable(RuntimeError):
    """PostgreSQL is configured but can't be used: one plain sentence, for
    the user. Not retried."""


class Unreadable(PostgresUnavailable):
    """The address can't be read as PostgreSQL reads it (see _reading). The
    sentence names nothing of it, and it is raised without the driver's
    error, which quotes the address."""

    def __init__(self):
        super().__init__(
            f"{URL_KEY} isn't an address PostgreSQL can read. It should "
            "look like postgresql://user:password@host:5432/database."
        )


def url():
    """The configured connection URL, or "" for SQLite."""
    return str(of_env.getattr(URL_KEY) or "").strip()


def enabled():
    return bool(url())


def sqlite_files_notice(tool):
    """What a tool that still works on the user_data.db files tells its user
    while PostgreSQL is on (#631). The caller knows whether it is on."""
    return (
        f"PostgreSQL is on ({URL_KEY} is set), but {tool} works on the"
        " user_data.db files, not PostgreSQL. It does not see anything scraped"
        " since PostgreSQL was turned on, and what it changes in those files"
        " does not reach PostgreSQL. See POSTGRESQL.md."
    )


def warn_sqlite_files(tool):
    """Says sqlite_files_notice on stderr (stdout may be a report that
    another program reads), for a tool that is run on its own, without the
    scraper: scripts/creator_names.py. (stash_sync and recover_collisions
    can work on PostgreSQL, and have a sentence of their own for when they
    are given files.)

    Only the environment the tool is run in is looked at. A URL that is only
    in one of the scraper's env files is not seen: these tools don't read the
    scraper's settings, which would bring the scraper's own environment,
    errors and start-up time into them."""
    if os.environ.get(URL_KEY, "").strip():
        print(f"warning: {sqlite_files_notice(tool)}", file=sys.stderr)


def masked(text, database_url=None):
    """`text` with the address and its password hidden. The password is
    hidden as a whole, wherever it isn't part of a longer word."""
    text = str(text)
    for secret in _secrets(database_url if database_url is not None else url(), values=True):
        text = re.sub(_hiding(secret), "{hidden}", text)
    return text


def _reading(database_url):
    """The address as PostgreSQL itself reads it (libpq, through the
    driver): host, port, dbname, user, password... Or None when the driver
    isn't installed, or it can't read the address, or what it read isn't
    what was meant: an @ outside the password (one in the password that
    isn't written as %40), a port that isn't a number. libpq never quotes
    the password in its errors once it has read the address."""
    database_url = str(database_url or "")
    try:
        from psycopg.conninfo import conninfo_to_dict
    except ImportError:
        return None
    try:
        parts = conninfo_to_dict(database_url)
    # whatever stops the driver reading it (a ProgrammingError, a %-escape
    # that isn't UTF-8, a NUL): it is an address that can't be read
    except Exception:  # noqa: BLE001
        return None
    others = [str(value) for key, value in parts.items() if key != "password"]
    _, sep, rest = database_url.partition("://")
    if (
        "\x00" in database_url
        # an @ after the login part of a URL was meant for the password
        or (sep and "@" in rest.partition("/")[2])
        or any("@" in value or not value.isprintable() for value in others)
        or not re.fullmatch(r"[0-9,]*", str(parts.get("port") or ""))
    ):
        return None
    return parts


def _secrets(database_url, values=False):
    """What to keep out of messages and logs, longest first: the address
    itself, and its password as PostgreSQL reads it, as written and
    %-encoded. Nothing else: libpq doesn't quote the password, and an
    address it can't read gets a sentence of its own (see _unavailable).
    With `values`, for messages only, every value PostgreSQL read from the
    host=... spelling too: an unquoted password ends at a space, and the
    rest is read as more settings, which errors quote (#654)."""
    database_url = str(database_url or "")
    parts = _reading(database_url) or {}
    password = parts.get("password")
    if not password:
        return []
    secrets = {database_url, password, urllib.parse.quote(password, safe="")}
    # libpq reads a URL only when it starts like one
    if values and not database_url.startswith(("postgresql://", "postgres://")):
        for value in map(str, parts.values()):
            # each value, and each part of a list (host=a,b), which errors
            # quote one by one; not one character: connect_timeout=1 would
            # hide every 1
            secrets.update(part for part in {value, *value.split(",")} if len(part) > 1)
    return sorted(secrets, key=len, reverse=True)


def _hiding(secret):
    """The pattern that hides `secret` where it isn't part of a longer
    word: a password "word" leaves "password" as it is."""
    start = r"(?<![A-Za-z0-9])" if secret[:1].isascii() and secret[:1].isalnum() else ""
    end = r"(?![A-Za-z0-9])" if secret[-1:].isascii() and secret[-1:].isalnum() else ""
    return f"{start}{re.escape(secret)}{end}"


def describe(database_url=None):
    """The server and database a URL names, as PostgreSQL reads it, without
    the login: for messages. "the configured database" when it can't be
    read for certain, without the driver, or for the host=... spelling."""
    database_url = str((database_url if database_url is not None else url()) or "")
    parts = _reading(database_url) if "://" in database_url else None
    if parts and parts.get("host"):
        port = f":{parts['port']}" if parts.get("port") else ""
        dbname = f"/{parts['dbname']}" if parts.get("dbname") else ""
        return f"{parts['host']}{port}{dbname}"
    return "the configured database"


def schema_name(site):
    """The schema that holds a site's tables: the site's name."""
    name = str(site or "").strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", name):
        raise PostgresUnavailable(f"{site!r} can't be used as a schema name")
    return name


def translate(query):
    """The table modules' SQL as the driver takes it: `?` becomes %s, and a
    literal % is doubled. Text inside quotes is left alone."""
    return _translate(query)


@functools.lru_cache(maxsize=512)
def _translate(query):
    out = []
    quoted = False
    for char in query:
        if char == "'":
            quoted = not quoted
        if char == "%":
            out.append("%%")
        elif char == "?" and not quoted:
            out.append("%s")
        else:
            out.append(char)
    return "".join(out)


def iso(text):
    """PostgreSQL's text for a timestamp (2024-01-02 03:04:05+00) as the ISO
    text the app writes and reads (2024-01-02T03:04:05+00:00)."""
    text = text.replace(" ", "T", 1)
    if re.search(r"[+-]\d\d$", text):
        text += ":00"
    return text


def number(text):
    """A NUMERIC as SQLite gave it: a whole number as an int."""
    value = float(text)
    return int(value) if value.is_integer() else value


def date_value(value):
    """A date as it's saved: ISO text with its offset, read the way the app
    reads dates back (arrow; a number is seconds since 1970, and text
    without an offset is UTC). Nothing for no date."""
    import arrow

    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            pass
    return arrow.get(value).isoformat()


class Row(tuple):
    """A result row read as sqlite3.Row is: row[0], row["name"], dict(row)."""

    __slots__ = ()
    _names = ()
    _index = {}

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                key = self._index[key.lower()]
            except KeyError:
                raise IndexError("No item with that key") from None
        return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._names)


@functools.lru_cache(maxsize=512)
def _row_class(names):
    return type(
        "Row",
        (Row,),
        {
            "__slots__": (),
            "_names": names,
            "_index": {name.lower(): place for place, name in enumerate(names)},
        },
    )


# the id columns that are TEXT in some table (see TABLES)
LOOSE_IDS = frozenset({"media_id", "post_id", "label_id"})
_TEXT_OID = 25
# as str(int) writes one, so that the number read is the text that was saved
_WHOLE_NUMBER = re.compile(r"-?(0|[1-9][0-9]*)")


def row_factory(cursor):
    description = cursor.description or ()
    make = _row_class(tuple(column.name for column in description))
    loose = [
        place
        for place, column in enumerate(description)
        if column.type_code == _TEXT_OID and column.name.lower() in LOOSE_IDS
    ]
    if not loose:
        return make

    def row(values):
        values = list(values)
        for place in loose:
            value = values[place]
            if isinstance(value, str) and _WHOLE_NUMBER.fullmatch(value):
                values[place] = int(value)
        return make(values)

    return row


def _import_driver():
    import psycopg
    import psycopg_pool

    return psycopg, psycopg_pool


def _driver():
    """psycopg and its pool, or a sentence saying how to install them.

    On first use, installs them (``OFSC_INSTALL_EXTRAS``).
    """
    try:
        return _import_driver()
    except ImportError as E:
        missing = E
    from ofscraper.utils.system import extras

    if extras.install("postgres"):
        try:
            return _import_driver()
        except ImportError as E:
            missing = E
    if getattr(sys, "frozen", False):
        fix = (
            "This standalone download doesn't include it: use the pip or "
            "Docker install, or unset the variable to use SQLite."
        )
    else:
        from ofscraper.__version__ import __dist_name__

        fix = f"Install it with: {INSTALL_HINT.format(dist=__dist_name__)}"
    raise PostgresUnavailable(
        f"{URL_KEY} is set, but the PostgreSQL driver isn't installed. {fix}"
    ) from missing


@functools.lru_cache(maxsize=1)
def _adapters():
    """How values go in and come out, so that the table modules and their
    callers see what SQLite gave them.

    In: numbers and booleans are sent as untyped text, as text already is,
    and the server reads each one as its column's type. SQLite does the
    same with a column's affinity: 1 saves as TRUE in a yes/no column and
    as 1 in a number column.
    Out: a boolean is 1 or 0, a timestamp is ISO text and a NUMERIC is an
    int or a float.
    """
    psycopg, _ = _driver()
    from psycopg.adapt import AdaptersMap, Dumper, Loader

    class AsText(Dumper):
        def dump(self, obj):
            return str(obj).encode()

    class BoolAsText(Dumper):
        def dump(self, obj):
            return b"1" if obj else b"0"

    class BoolAsInt(Loader):
        def load(self, data):
            return 1 if bytes(data) == b"t" else 0

    class TimestampAsIso(Loader):
        def load(self, data):
            return iso(bytes(data).decode())

    class NumericAsNumber(Loader):
        def load(self, data):
            return number(bytes(data).decode())

    adapters = AdaptersMap(psycopg.adapters)
    adapters.register_dumper(int, AsText)
    adapters.register_dumper(float, AsText)
    adapters.register_dumper(bool, BoolAsText)
    adapters.register_loader("bool", BoolAsInt)
    adapters.register_loader("timestamptz", TimestampAsIso)
    adapters.register_loader("numeric", NumericAsNumber)
    return adapters


@functools.lru_cache(maxsize=1)
def _cursor_class():
    psycopg, _ = _driver()

    class Cursor(psycopg.Cursor):
        """Takes the table modules' SQL (see translate)."""

        def execute(self, query, params=None, **kwargs):
            return super().execute(
                translate(query), () if params is None else params, **kwargs
            )

        def executemany(self, query, params_seq, **kwargs):
            return super().executemany(translate(query), params_seq, **kwargs)

    return Cursor


class PostgresBackend:
    """The methods the database wrapper asks of an engine (see
    wrapper.SQLiteBackend), for PostgreSQL."""

    name = "postgresql"
    # the tables are made at the current layout, so no upgrade steps and no
    # file to back up first
    born_current = True
    # one database for a whole site: "everything in the database" is no
    # longer one creator's
    holds_every_creator = True

    def __init__(self):
        self._pools = {}
        self._ready = set()
        self._lock = threading.RLock()

    @property
    def errors(self):
        return (_driver()[0].Error,)

    @property
    def operational_errors(self):
        psycopg = _driver()[0]
        return (psycopg.OperationalError, psycopg.errors.UndefinedTable)

    # --- connections ---

    def where(self, kwargs, read_only):
        """The operation's database: the current site's schema."""
        import ofscraper.sites as sites

        return schema_name(sites.current_site())

    def _pool(self, schema, timeout):
        with self._lock:
            pool = self._pools.get((url(), schema))
            if pool is None:
                pool = self._open_pool(schema, timeout)
                self._pools[(url(), schema)] = pool
            return pool

    def _open_pool(self, schema, timeout):
        psycopg, psycopg_pool = _driver()
        database_url = url()
        self._hide_password(database_url)
        if _reading(database_url) is None:
            raise Unreadable() from None
        adapters = _adapters()
        # a first connection of our own: the pool only says it timed out,
        # this says why (no server, a refused login, no such database)
        try:
            psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT).close()
        except psycopg.Error as E:
            error = self._unavailable(E, database_url)
            raise error from (None if isinstance(error, Unreadable) else E)
        lock_timeout = int(max(float(timeout or 0), 1) * 1000)

        def configure(conn):
            conn.execute("SET TIME ZONE 'UTC'")
            # dates are read back as ISO text, whatever the server's default
            conn.execute("SET DateStyle TO 'ISO, YMD'")
            conn.execute(f"SET search_path TO {schema}")
            # a row another program has locked stops the wait in the end, as
            # a locked SQLite file does
            conn.execute(f"SET lock_timeout = {lock_timeout}")
            conn.commit()

        pool = psycopg_pool.ConnectionPool(
            database_url,
            min_size=1,
            max_size=POOL_SIZE,
            open=False,
            configure=configure,
            kwargs={
                "context": adapters,
                "cursor_factory": _cursor_class(),
                "row_factory": row_factory,
                "application_name": "ofscraper",
            },
            name=f"ofscraper-{schema}",
        )
        try:
            pool.open(wait=True, timeout=CONNECT_TIMEOUT * 2)
        except Exception as E:
            # the address was read above: the error is the server's
            pool.close()
            raise self._unavailable(E, database_url) from E
        if not self._pools:
            atexit.register(self.shutdown)
        return pool

    def _hide_password(self, database_url):
        import ofscraper.utils.logs.utils.sensitive as sensitive

        for text in _secrets(database_url):
            # not one character: a password of ! would hide every ! of
            # every log line (messages hide it, see masked)
            if len(text) > 1:
                sensitive.add_sensitive_pattern(_hiding(text))

    def _unavailable(self, error, database_url):
        """A connection that can't be made, as one sentence for the user.
        The server's own first line follows in brackets."""
        psycopg, psycopg_pool = _driver()
        text = str(error)
        state = getattr(error, "sqlstate", None) or ""
        # a connection that was never made has no error code, only the
        # server's words
        if (isinstance(error, psycopg.ProgrammingError) and not state) or _reading(
            database_url
        ) is None:
            # the driver couldn't read the address, and quotes it: say so
            # without the quote
            return Unreadable()
        if (
            state.startswith("28")
            or "authentication failed" in text
            or re.search(r'role "[^"]*" does not exist', text)
        ):
            reason = "the user name or password was refused"
        elif state == "3D000" or re.search(r'database "[^"]*" does not exist', text):
            reason = "there is no database with that name on the server"
        elif state == "42501" or isinstance(error, psycopg.errors.InsufficientPrivilege):
            reason = "the user isn't allowed to make or use its tables"
        elif state == "55P03":
            reason = "another program is setting up its tables; try again"
        elif isinstance(error, psycopg_pool.PoolTimeout):
            reason = "no connection could be had in time (the server is down or busy)"
        else:
            reason = "the server can't be reached"
        detail = masked(" ".join(text.split()), database_url)[:300]
        return PostgresUnavailable(
            f"Can't use the PostgreSQL database at {describe(database_url)}: "
            f"{reason}. ({detail})"
        )

    def connect(self, where, read_only, *, timeout, check_same_thread=None):
        """A pooled connection with its transaction ready to begin: the
        driver begins one with the first statement, read-only for a read."""
        psycopg = _driver()[0]
        pool = self._pool(where, timeout)
        # not the database timeout, which is for a busy database and runs to
        # minutes: with the server gone, every operation would wait that long
        try:
            conn = pool.getconn(timeout=min(float(timeout or 30), CHECKOUT_TIMEOUT))
        except psycopg.Error as E:
            raise self._unavailable(E, url()) from E
        try:
            conn.read_only = bool(read_only)
        except BaseException:
            pool.putconn(conn)
            raise
        conn._ofscraper_pool = pool
        return conn

    def close(self, conn):
        """Done with the connection: what wasn't committed is rolled back,
        and the pool has it back (it drops a broken one)."""
        try:
            conn.rollback()
        except _driver()[0].Error as E:
            log.debug(f"Nothing to roll back on a lost connection ({masked(E)})")
        conn._ofscraper_pool.putconn(conn)

    def shutdown(self):
        with self._lock:
            pools, self._pools = self._pools, {}
            self._ready.clear()
        for pool in pools.values():
            # at exit, don't wait on a server that has gone
            pool.close(timeout=1)

    # --- errors ---

    def final_error(self, error, read_only, where):
        """The error to raise for `error`. A read-only read of tables that
        aren't there yet is DatabaseMissing, as it is for a missing file."""
        import ofscraper.db.operations_.wrapper as wrapper

        psycopg = _driver()[0]
        if read_only and isinstance(error, psycopg.errors.UndefinedTable):
            return wrapper.DatabaseMissing(str(error).strip())
        if isinstance(error, psycopg.Error):
            error.database_path = f"PostgreSQL ({where})"
        return error

    def retryable(self, error):
        """Whether a retry can fix `error`: two writers that got in each
        other's way, a lock that wasn't freed in time, or a lost connection
        (the pool hands out a new one)."""
        if isinstance(error, PostgresUnavailable):
            return False
        try:
            psycopg = _driver()[0]
        except PostgresUnavailable:
            return False
        if not isinstance(error, psycopg.OperationalError):
            return False
        state = getattr(error, "sqlstate", None)
        # no code: the connection went before the server could give one
        return state is None or state in RETRY_STATES or state.startswith("08")

    def busy(self, error):
        try:
            psycopg = _driver()[0]
        except PostgresUnavailable:
            return False
        return isinstance(
            error, (psycopg.errors.LockNotAvailable, psycopg.errors.DeadlockDetected)
        )

    # --- what is there ---

    def owns(self, conn_or_cur):
        try:
            psycopg = _driver()[0]
        except PostgresUnavailable:
            return False
        return isinstance(conn_or_cur, (psycopg.Connection, psycopg.Cursor))

    def table_exists(self, cur, table):
        return bool(
            cur.execute(
                "SELECT 1 FROM information_schema.tables"
                " WHERE table_schema = current_schema() AND table_name = ?",
                [table],
            ).fetchall()
        )

    def table_columns(self, cur, table):
        """The names of the columns `table` has (none if there's no table).
        The app's own tables are made complete, so they aren't asked for."""
        if table in TABLE_COLUMNS and self._tables_made(cur):
            return set(TABLE_COLUMNS[table])
        return {
            row[0]
            for row in cur.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = current_schema() AND table_name = ?",
                [table],
            ).fetchall()
        }

    def _tables_made(self, cur):
        pool = getattr(cur.connection, "_ofscraper_pool", None)
        return pool is not None and getattr(pool, "_ofscraper_tables_made", False)

    def database_exists(self, model_id=None, username=None, db_path=None):
        """Every creator's rows are in the one database, which is there."""
        return True

    def date_value(self, value):
        return date_value(value)

    # --- the tables ---

    def create_tables(self, flags, schema=None):
        """Make the site's schema and tables if they aren't there. `flags`
        (the upgrade steps this build knows) are recorded as done when the
        tables are first made, since they're made at the current layout.
        Tables an earlier version made get the columns added since (see
        _add_columns). `schema` names another site's than the current one."""
        schema = schema or self.where({}, False)
        with self._lock:
            if (url(), schema) in self._ready:
                return
            timeout = of_env.getattr("DATABASE_TIMEOUT")
            conn = self.connect(schema, False, timeout=timeout)
            try:
                with conn.cursor() as cur:
                    # one at a time: two programs starting together would
                    # both try to make the same tables
                    cur.execute("SELECT pg_advisory_xact_lock(?)", [0x6F667363])
                    # asked first: making a schema needs a permission that
                    # a login given a ready-made one may not have
                    if not cur.execute(
                        "SELECT 1 FROM pg_namespace WHERE nspname = ?", [schema]
                    ).fetchall():
                        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
                    first = not self.table_exists(cur, "schema_flags")
                    for create in TABLES.values():
                        cur.execute(create)
                    for table in CREATOR_INDEXES:
                        cur.execute(
                            f"CREATE INDEX IF NOT EXISTS {table}_model_id"
                            f" ON {table} (model_id)"
                        )
                    if first:
                        cur.executemany(
                            "INSERT INTO schema_flags (flag_name, flag_value)"
                            " VALUES (?, '1') ON CONFLICT (flag_name) DO NOTHING",
                            [(flag,) for flag in sorted(flags)],
                        )
                    else:
                        self._add_columns(cur)
                conn.commit()
            except self.errors as E:
                raise self._unavailable(E, url()) from E
            finally:
                self.close(conn)
            self._ready.add((url(), schema))
            self._pool(schema, timeout)._ofscraper_tables_made = True

    def _add_columns(self, cur):
        """Give tables made by an earlier version the columns added since
        (ADDED_COLUMNS), and record each step as done. Run at every start,
        under create_tables' lock: it asks which columns are there, and
        changes a table only when one is missing. The new columns are empty
        in the rows already there."""
        for flag, table, columns in ADDED_COLUMNS:
            there = {
                row[0]
                for row in cur.execute(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_schema = current_schema() AND table_name = ?",
                    [table],
                ).fetchall()
            }
            missing = [column for column in columns if column not in there]
            for column in missing:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS"
                    f" {column} {COLUMN_TYPES[table][column]}"
                )
            if missing:
                cur.execute(
                    "INSERT INTO schema_flags (flag_name, flag_value)"
                    " VALUES (?, '1') ON CONFLICT (flag_name) DO NOTHING",
                    [flag],
                )

    def check(self, site=None):
        """The startup check: connect, and stop with one sentence if the
        server can't be used. Returns the server's version text. With a
        site, its schema is used without reading the settings."""
        schema = schema_name(site) if site else self.where({}, True)
        conn = self.connect(schema, True, timeout=of_env.getattr("DATABASE_TIMEOUT"))
        try:
            version = conn.info.server_version
            if version < MIN_SERVER * 10000:
                raise PostgresUnavailable(
                    f"The PostgreSQL server at {describe()} is version "
                    f"{version // 10000}; {MIN_SERVER} or newer is needed."
                )
            return f"{version // 10000}.{version % 10000}"
        finally:
            self.close(conn)


POSTGRES = PostgresBackend()


class Reader:
    """A connection of its own for a tool that is run without the scraper
    (see creator_rows). The scraper's settings, pool and current site aren't
    used, so the URL is handed in and a query names its schema.

    Nothing can be written through it, and every read sees the database as
    it was at the first one. Values come out as the engine's do. What goes
    wrong is a PostgresUnavailable: one sentence, without the login."""

    def __init__(self, database_url):
        psycopg = _driver()[0]
        self._url = database_url
        self._errors = (psycopg.Error,)
        self._conn = None
        if _reading(database_url) is None:
            raise Unreadable() from None
        try:
            self._conn = psycopg.connect(
                database_url,
                connect_timeout=CONNECT_TIMEOUT,
                # a server that is gone without saying so is noticed in a
                # minute or two, not waited for
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3,
                # no statement is kept on the server: a pooler may hand the
                # next one to another connection
                prepare_threshold=None,
                application_name="ofscraper",
                context=_adapters(),
                cursor_factory=_cursor_class(),
                row_factory=row_factory,
            )
            # as the pool sets a connection up (see _open_pool)
            self._conn.execute("SET TIME ZONE 'UTC'")
            self._conn.execute("SET DateStyle TO 'ISO, YMD'")
            # the server ends a read that waits on another program's lock,
            # or that takes too long, and the read fails
            self._conn.execute(f"SET lock_timeout = {CHECKOUT_TIMEOUT * 1000}")
            self._conn.execute(f"SET statement_timeout = {READ_TIMEOUT * 1000}")
            self._conn.commit()
            # from here on: one read-only transaction, one view of the rows
            self._conn.read_only = True
            self._conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        except psycopg.Error as E:
            self.close()
            error = POSTGRES._unavailable(E, database_url)
            raise error from (None if isinstance(error, Unreadable) else E)

    def rows(self, query, params=()):
        """Every row of a query, written as the table modules write theirs
        (`?` for a value)."""
        try:
            with self._conn.cursor() as cur:
                return cur.execute(query, params).fetchall()
        except self._errors as E:
            detail = masked(" ".join(str(E).split()), self._url)[:300]
            raise PostgresUnavailable(
                f"Can't read the PostgreSQL database at {describe(self._url)}."
                f" ({detail})"
            ) from E

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


class ChangedMeanwhile(PostgresUnavailable):
    """A change that wasn't made because another program (the scraper, still
    running) changed or holds the same rows. Nothing was kept."""


class Unconfirmed(PostgresUnavailable):
    """Keeping the changes was begun and didn't end well (the connection
    went, or the program was stopped), so it isn't known whether they were
    kept. Whoever gets this must not tidy up as if they weren't."""

    # it was stopped from the keyboard (Ctrl-C), not by the connection
    interrupted = False


class Writer(Reader):
    """A Reader that can also change rows, for a tool that is run without
    the scraper and changes what the scraper saved (see creator_rows).

    What it reads and changes is one transaction. Nothing is kept until
    commit(); close() without it leaves the database as it was. Every read
    sees the database as it was at the first one, and the server refuses a
    change to a row that another program changed after that: a
    ChangedMeanwhile, after which nothing can be kept.

    The Reader's timeouts hold here too. A change waits CHECKOUT_TIMEOUT
    for a row another program holds (the scraper's own writes take a
    moment), and no statement may take longer than READ_TIMEOUT: a change
    names one row by its id, so only the first read of a creator's rows
    comes anywhere near that."""

    # another program got there first: it changed the row since the first
    # read (40001), holds it (55P03), or each waits for the other (40P01)
    _MEANWHILE = frozenset({"40001", "40P01", "55P03"})

    def __init__(self, database_url):
        super().__init__(database_url)
        try:
            self._conn.read_only = False
        except self._errors as E:
            self.close()
            raise POSTGRES._unavailable(E, database_url) from E

    def change(self, query, params=()):
        """Run an UPDATE, written as rows() takes a query. Returns how many
        rows it changed."""
        try:
            with self._conn.cursor() as cur:
                return cur.execute(query, params).rowcount
        except self._errors as E:
            detail = masked(" ".join(str(E).split()), self._url)[:300]
            if getattr(E, "sqlstate", None) in self._MEANWHILE:
                raise ChangedMeanwhile(
                    "Another program changed or is using the same rows of the"
                    f" PostgreSQL database at {describe(self._url)} (is the"
                    f" scraper running?). Nothing was changed. ({detail})"
                ) from E
            raise PostgresUnavailable(
                f"Can't change the PostgreSQL database at {describe(self._url)}."
                f" Nothing was changed. ({detail})"
            ) from E

    def commit(self):
        """Keep what was changed.

        Once this has begun, whatever stops it is an Unconfirmed: a lost
        connection, but also Ctrl-C or the program being told to end, which
        the driver passes on whether or not the server had kept the changes
        by then."""
        try:
            self._conn.commit()
        except BaseException as E:
            if isinstance(E, self._errors):
                detail = masked(" ".join(str(E).split()), self._url)[:300]
                said = (
                    "The connection to the PostgreSQL database at"
                    f" {describe(self._url)} was lost while the changes were being"
                    f" saved, so it isn't known whether they were. ({detail})"
                )
            else:
                said = (
                    "This was stopped while the changes were being saved to the"
                    f" PostgreSQL database at {describe(self._url)}, so it isn't"
                    " known whether they were."
                )
            unconfirmed = Unconfirmed(said)
            unconfirmed.interrupted = isinstance(E, KeyboardInterrupt)
            raise unconfirmed from E
