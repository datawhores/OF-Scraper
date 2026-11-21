"""A stand-in for a PostgreSQL server, for the tests of the tools that read
one without the scraper (test_stash_sync_postgres.py) or change one
(test_collision_recovery_postgres.py). It takes the place of postgres.Reader
and postgres.Writer.

What it models is the server: SQLite runs the queries, with one attached
database per schema, and keeps each value as the server keeps it (a date as
one moment, given back in UTC). What comes out goes through the real thing:
each value is written as the server sends it and read by the driver's own
loader for the column's type (the engine's among them), and each row is made
by the engine's row_factory. So the driver must be installed.

It can't tell whether PostgreSQL would take a query: that needs a server
(test_stash_sync_postgres_live.py).
"""

import re
import sqlite3
from types import SimpleNamespace

import arrow

import ofscraper.commands.postgres_import as importer
import ofscraper.db.postgres as postgres

# PostgreSQL's name for each column type in postgres.TABLES
TYPE_NAMES = {
    "BIGINT": "int8",
    "TEXT": "text",
    "BOOLEAN": "bool",
    "TIMESTAMPTZ": "timestamptz",
    "NUMERIC": "numeric",
    "INTEGER": "int4",
}
# one row per key (the import leaves out a row that is already there)
SHARED = {"profiles": ("user_id", "username"), "models": ("model_id",)}
# taken when this is first imported, before a test puts the stand-in's Writer
# in postgres.Writer's place
REAL_COMMIT = postgres.Writer.commit


def kept(value, kind):
    """A value as the server keeps it."""
    if value is None:
        return None
    if kind == "BOOLEAN":
        return int(bool(value))
    if kind == "TIMESTAMPTZ":
        # one moment, whatever offset it was given with; sent in the
        # session's time zone (UTC), fractions without their last zeros
        moment = arrow.get(value).to("UTC")
        text = moment.format("YYYY-MM-DD HH:mm:ss")
        if moment.microsecond:
            text += f".{moment.microsecond:06d}".rstrip("0")
        return text + "+00"
    return value


def sent(value, kind):
    """A kept value as the server sends it: text, or nothing for NULL."""
    if value is None:
        return None
    if kind == "BOOLEAN":
        return b"t" if value else b"f"
    return str(value).encode()


class Server:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("ATTACH ':memory:' AS information_schema")
        self.db.execute(
            "CREATE TABLE information_schema.columns"
            " (table_schema, table_name, column_name)"
        )
        # the catalogue, which lists every table whoever may read it
        self.db.execute("ATTACH ':memory:' AS pg_catalog")
        self.db.execute("CREATE TABLE pg_catalog.pg_namespace (oid INTEGER PRIMARY KEY, nspname)")
        self.db.execute("CREATE TABLE pg_catalog.pg_class (relname, relnamespace, relkind)")
        self.schemas = set()
        # what the tool did, in order: ("connect", url), ("query", sql), ("close",)
        self.events = []
        # a table whose reads fail, as a lost connection would
        self.fails_on = None
        # for a Writer: called once, before its first change (what another
        # program does between a tool's reads and its changes); an error
        # its changes raise; what its connection's commit raises without
        # keeping the changes, or after it kept them (the answer never came)
        self.before_change = None
        self.change_error = None
        self.commit_error = None
        self.commit_answer_lost = None
        self._open = False
        self._kept_elsewhere = []

    def make(self, site, without=()):
        """The site's schema and tables, as the engine makes them. `without`
        are (table, column) pairs a database made by an older version lacks."""
        schema = postgres.schema_name(site)
        if schema in self.schemas:
            return
        self.schemas.add(schema)
        self.db.execute(f"ATTACH ':memory:' AS {schema}")
        namespace = self.db.execute(
            "INSERT INTO pg_catalog.pg_namespace (nspname) VALUES (?)", [schema]
        ).lastrowid
        for table, columns in postgres.TABLE_COLUMNS.items():
            self.db.execute(
                "INSERT INTO pg_catalog.pg_class VALUES (?, ?, 'r')", [table, namespace]
            )
            columns = [c for c in columns if (table, c) not in without]
            # no column types: a value stays as `kept` made it
            rest = ", ".join(c for c in columns if c != "id")
            first = "id INTEGER PRIMARY KEY, " if "id" in columns else ""
            unique = f", UNIQUE ({', '.join(SHARED[table])})" if table in SHARED else ""
            self.db.execute(f"CREATE TABLE {schema}.{table} ({first}{rest}{unique})")
            self.db.executemany(
                "INSERT INTO information_schema.columns VALUES (?, ?, ?)",
                [(schema, table, column) for column in columns],
            )

    def forbid(self, site, tables=None):
        """The login may no longer read the site's tables (or only not
        these): information_schema stops listing them, as it does on a
        server. The catalogue goes on listing them."""
        some = "" if tables is None else f" AND table_name IN ({', '.join('?' for _ in tables)})"
        self.db.execute(
            f"DELETE FROM information_schema.columns WHERE table_schema = ?{some}",
            [postgres.schema_name(site), *(tables or ())],
        )

    def insert(self, site, table, columns, rows):
        """Rows as the import or the scraper hands them to the server."""
        self.make(site)
        name = f"{postgres.schema_name(site)}.{table}"
        kinds = [postgres.COLUMN_TYPES[table][column] for column in columns]
        for row in rows:
            values = [kept(value, kind) for value, kind in zip(row, kinds)]
            if table in SHARED:
                key = [values[columns.index(column)] for column in SHARED[table]]
                same = " AND ".join(f"{column} = ?" for column in SHARED[table])
                if self.db.execute(f"SELECT 1 FROM {name} WHERE {same}", key).fetchone():
                    continue
            self.db.execute(
                f"INSERT INTO {name} ({', '.join(columns)})"
                f" VALUES ({', '.join('?' for _ in columns)})",
                values,
            )

    def bring_in(self, folder, staging):
        """Every user_data.db under `folder`, converted as the import
        converts them and in the order it writes them."""
        sources = importer.examine(importer.find(folder), staging)
        for source in sources:
            assert not source.problems, source.problems
            if source.empty:
                # a file no creator has a row in is left out
                continue
            importer.read(
                source,
                lambda table, columns, rows, site=source.site: self.insert(
                    site, table, columns, rows
                ),
            )
            assert not source.problems, source.problems
        return sources

    def reader(self, database_url):
        return Reader(self, database_url)

    def writer(self, database_url):
        return Writer(self, database_url)

    def elsewhere(self, statement, params=()):
        """A change another program makes and keeps (the scraper, still
        running). Made while a tool's transaction is open, it outlives that
        transaction being rolled back."""
        self.db.execute(statement, list(params))
        if self._open:
            self._kept_elsewhere.append((statement, list(params)))

    def close(self):
        self.db.close()


class Reader:
    """postgres.Reader, reading the stand-in."""

    def __init__(self, server, database_url):
        import psycopg
        from psycopg.adapt import Transformer

        self.server = server
        self.closed = False
        self._adapters = postgres._adapters()
        self._transformer = Transformer(self._adapters)
        self._format = psycopg.pq.Format.TEXT
        server.events.append(("connect", database_url))

    def rows(self, query, params=()):
        self.server.events.append(("query", query))
        assert not self.closed, "read after the connection was closed"
        named = re.search(r"FROM (\w+)\.(\w+)", query)
        table = named.group(2) if named else None
        if table == self.server.fails_on:
            raise postgres.PostgresUnavailable(
                "Can't read the PostgreSQL database at db.example:5433/library."
                " (server closed the connection unexpectedly)"
            )
        cursor = self.server.db.execute(query, list(params))
        columns = [self._column(table, column[0]) for column in cursor.description]
        loaders = [
            self._transformer.get_loader(self._adapters.types[kind].oid, self._format)
            for _name, kind in columns
        ]
        make = postgres.row_factory(
            SimpleNamespace(
                description=[
                    SimpleNamespace(name=name, type_code=self._adapters.types[kind].oid)
                    for name, kind in columns
                ]
            )
        )
        found = cursor.fetchall()
        if "ORDER BY" not in query:
            # a server gives rows in no order of its own
            found.reverse()
        rows = []
        for row in found:
            values = []
            for value, loader, (_name, kind) in zip(row, loaders, columns):
                data = sent(value, _KINDS[kind])
                values.append(None if data is None else loader.load(data))
            rows.append(make(values))
        return rows

    @staticmethod
    def _column(table, text):
        """The name and type PostgreSQL gives a result column."""
        kinds = postgres.COLUMN_TYPES.get(table, {})
        if text in kinds:
            return text, TYPE_NAMES[kinds[text]]
        call = re.fullmatch(r"COALESCE\((\w+), \w+\)", text)
        if call:
            return "coalesce", TYPE_NAMES[kinds[call.group(1)]]
        if text.isdigit():
            return "?column?", "int4"
        if text.lower() == "count(*)":
            return "count", "int8"
        # information_schema's names
        return text, "text"

    def close(self):
        self.closed = True
        self.server.events.append(("close",))


def given(value, kind):
    """A value a query was sent with, as the server reads it for a column of
    this type: the engine sends numbers and booleans as untyped text."""
    if value is None:
        return None
    if kind == "TEXT":
        return str(value)
    if kind == "BIGINT":
        return int(value)
    if kind == "BOOLEAN":
        return {"1": 1, "0": 0, "True": 1, "False": 0}[str(value)]
    return kept(value, kind)


class Writer(Reader):
    """postgres.Writer, changing the stand-in: its changes are kept by
    commit() and gone without it.

    What it is not: a server's transaction. Its reads see what another
    program changed after its first read (a server's don't), and no change
    is refused because another program changed the same row (a server
    refuses it). A test says what a server would do with change_error, or
    lets the tool find the row changed (before_change, elsewhere). Rows
    aren't locked, and a column takes any value."""

    def __init__(self, server, database_url):
        import psycopg

        super().__init__(server, database_url)
        server.events.append(("open for changes",))
        server.db.execute("SAVEPOINT tool")
        server._open = True
        self._changed = False
        # what postgres.Writer's own commit() needs of a connection
        self._conn = SimpleNamespace(commit=self._keep)
        self._errors = (psycopg.Error,)
        self._url = database_url

    def change(self, query, params=()):
        self.server.events.append(("change", query))
        assert not self.closed, "change after the connection was closed"
        assert self.server._open, "change after the commit"
        if not self._changed and self.server.before_change:
            self.server.before_change()
        self._changed = True
        if self.server.change_error:
            raise self.server.change_error
        if "CASE" in query or query.startswith("INSERT"):
            # a statement of scripts/creator_names.py's: a date is the only
            # value that is kept otherwise than it is sent
            values = [
                kept(value, "TIMESTAMPTZ") if _ISO.match(str(value)) else value
                for value in params
            ]
            return self.server.db.execute(query, values).rowcount
        table = re.match(r"UPDATE \w+\.(\w+) SET ", query).group(1)
        kinds = postgres.COLUMN_TYPES[table]
        columns = re.findall(r"(\w+) (?:=|IS NOT DISTINCT FROM) \?", query)
        assert len(columns) == len(params) == query.count("?")
        values = [given(value, kinds[column]) for column, value in zip(columns, params)]
        # SQLite's own spelling of it
        return self.server.db.execute(
            query.replace(" IS NOT DISTINCT FROM ", " IS "), values
        ).rowcount

    # the real one, over _keep: what it makes of a commit that goes wrong is
    # the engine's to say
    commit = REAL_COMMIT

    def _keep(self):
        """The connection's commit."""
        self.server.events.append(("commit",))
        assert not self.closed and self.server._open
        if self.server.commit_error:
            raise self.server.commit_error
        self.server.db.execute("RELEASE tool")
        self._end()
        if self.server.commit_answer_lost:
            raise self.server.commit_answer_lost

    def close(self):
        if self.server._open:
            self.server.db.execute("ROLLBACK TO tool")
            self.server.db.execute("RELEASE tool")
            kept_elsewhere = list(self.server._kept_elsewhere)
            self._end()
            for statement, params in kept_elsewhere:
                self.server.db.execute(statement, params)
        if not self.closed:
            super().close()

    def _end(self):
        self.server._open = False
        self.server._kept_elsewhere.clear()


_KINDS = {name: kind for kind, name in TYPE_NAMES.items()}
_ISO = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d")
