"""A stand-in for a PostgreSQL server, for the tests of the tools that read
one without the scraper (test_stash_sync_postgres.py). It takes the place of
postgres.Reader.

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
            self.db.execute(f"CREATE TABLE {schema}.{table} ({first}{rest})")
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
        # information_schema's names
        return text, "text"

    def close(self):
        self.closed = True
        self.server.events.append(("close",))


_KINDS = {name: kind for kind, name in TYPE_NAMES.items()}
