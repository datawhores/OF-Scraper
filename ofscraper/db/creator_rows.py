"""One creator's rows, for a tool that is run on its own (#631).

Such a tool (stash_sync) reads what the scraper saved without loading the
scraper. SQLite keeps one file per creator; PostgreSQL keeps every creator's
rows, of both sites, in shared tables. Either way the tool gets one object
per creator, FileRows or PostgresRows, and asks both the same things:

    site                  "onlyfans" or "fansly" (a file may name another)
    name                  where the rows are, for a report
    creator               what to call the creator when no username is saved
    tables()              the names of the tables there are
    columns(table)        the table's column names; none if there is no table
    select(table, columns, where="")
                          the creator's rows of a table. PostgreSQL gives
                          them oldest first; a file gives them as SQLite
                          does when no order is asked for
    close()

`columns` and `where` are SQL that both engines take. Values come out as
SQLite gives them: a yes/no as 1 or 0, a date as ISO text (see postgres.py).

Nothing here writes, and nothing here reads the scraper's settings.
"""

import contextlib
import sqlite3
from pathlib import Path

import ofscraper.db.postgres as postgres
import ofscraper.sites as sites


class NotFound(LookupError):
    """A creator that was asked for by name has no rows."""


class FileRows:
    """A user_data.db, which holds one creator's rows. It is opened
    read-only, when first asked for something."""

    def __init__(self, path):
        self.path = Path(path)
        self.name = str(self.path)
        # the default layout names the folder after the creator's id
        self.creator = self.path.parent.name
        self._conn = None

    def _connection(self):
        if self._conn is None:
            uri = self.path.resolve().as_uri()
            self._conn = sqlite3.connect(f"{uri}?mode=ro", uri=True)
        return self._conn

    @property
    def site(self):
        """Fansly databases carry a site flag; a file without one is OnlyFans'."""
        conn = self._connection()
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_flags'"
        ).fetchone():
            return sites.DEFAULT_SITE
        row = conn.execute(
            "SELECT flag_value FROM schema_flags WHERE flag_name = 'site'"
        ).fetchone()
        return str(row[0]).lower() if row and row[0] else sites.DEFAULT_SITE

    def tables(self):
        """Tables only: a view isn't one."""
        return {
            row[0]
            for row in self._connection().execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    def columns(self, table):
        return {row[1] for row in self._connection().execute(f"PRAGMA table_info({table})")}

    def select(self, table, columns, where=""):
        query = f"SELECT {', '.join(columns)} FROM {table}"
        if where:
            query += f" WHERE {where}"
        # no order is asked for: a file made elsewhere may have no id column,
        # or one that isn't the order its rows were saved in
        return self._connection().execute(query).fetchall()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def files(paths):
    """A FileRows for each user_data.db: a path is one, or a folder (e.g. a
    profile's .data) that is searched for them."""
    found = []
    for path in map(Path, paths):
        if path.is_dir():
            found.extend(sorted(path.rglob("user_data.db")))
        elif path.is_file():
            found.append(path)
        else:
            raise FileNotFoundError(path)
    return [FileRows(path) for path in found]


class PostgresRows:
    """One creator's rows in one site's tables."""

    def __init__(self, reader, site, model_id, columns):
        self.site = site
        self.model_id = model_id
        self.name = f"PostgreSQL: {site}, creator {model_id}"
        self.creator = str(model_id)
        self._reader = reader
        self._schema = postgres.schema_name(site)
        self._columns = columns

    def tables(self):
        return set(self._columns)

    def columns(self, table):
        return set(self._columns.get(table, ()))

    def select(self, table, columns, where=""):
        # profiles names a creator by user_id, every other table by model_id
        creator = "user_id" if table == "profiles" else "model_id"
        query = f"SELECT {', '.join(columns)} FROM {self._schema}.{table} WHERE {creator} = ?"
        if where:
            query += f" AND ({where})"
        return self._reader.rows(f"{query} ORDER BY id", [self.model_id])

    def close(self):
        """Nothing to close: the connection is the whole run's (in_postgres)."""


@contextlib.contextmanager
def in_postgres(database_url, wanted_sites, wanted=()):
    """A PostgresRows for each creator the database holds rows for: a site at
    a time, in the order given, and by the id's text within a site. `wanted`
    keeps only the creators with one of these ids, or who have had one of
    these usernames (any case), which can be several for one of them. It
    raises NotFound for one that no site has.

    One read-only connection serves them all, and every read sees the
    database as it was at the first. It is closed when the block ends, so
    read inside the block. A server that can't be used, a read that fails,
    or a site whose tables the login may not read, is a
    postgres.PostgresUnavailable."""
    wanted = {str(name).lower() for name in wanted}
    reader = postgres.Reader(database_url)
    try:
        found = []
        seen = set()
        for site in wanted_sites:
            schema = postgres.schema_name(site)
            columns = {}
            for table, column in reader.rows(
                "SELECT table_name, column_name FROM information_schema.columns"
                " WHERE table_schema = ?",
                [schema],
            ):
                columns.setdefault(table, set()).add(column)
            # that lists only what the login may read, and the catalogue
            # lists every table: one that is there and can't be read is a
            # login without the right to, not a site with nothing saved
            there = {
                row[0]
                for row in reader.rows(
                    "SELECT c.relname FROM pg_catalog.pg_class AS c"
                    " JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace"
                    " WHERE n.nspname = ? AND c.relkind IN ('r', 'p')",
                    [schema],
                )
            }
            unreadable = sorted((there & set(postgres.TABLE_COLUMNS)) - set(columns))
            if unreadable:
                raise postgres.PostgresUnavailable(
                    "Can't read the PostgreSQL database at"
                    f" {postgres.describe(database_url)}: the user isn't allowed to"
                    f" read the {site} tables ({', '.join(unreadable)})."
                )
            # a creator is listed when a scan starts; media is what the
            # tools are after
            holders = [table for table in ("models", "medias") if table in columns]
            if not holders:
                continue
            held = " UNION ALL ".join(
                f"SELECT model_id FROM {schema}.{table}" for table in holders
            )
            creators = [
                row[0]
                for row in reader.rows(f"SELECT DISTINCT model_id FROM ({held}) AS held")
            ]
            names = {}
            if wanted and "profiles" in columns:
                for user_id, username in reader.rows(
                    f"SELECT user_id, username FROM {schema}.profiles"
                ):
                    names.setdefault(user_id, set()).add(str(username).lower())
            # in the order files() gives a profile's .data folder, whose
            # folders are named after the ids
            for model_id in sorted(creators, key=str):
                known = {str(model_id)} | names.get(model_id, set())
                if wanted and not known & wanted:
                    continue
                seen |= known
                found.append(PostgresRows(reader, site, model_id, columns))
        missing = sorted(wanted - seen)
        if missing:
            raise NotFound(
                f"PostgreSQL has no creator named {', '.join(missing)}"
                f" (looked in: {', '.join(wanted_sites)})"
            )
        yield found
    finally:
        reader.close()
