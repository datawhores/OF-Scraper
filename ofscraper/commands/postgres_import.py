"""Bring existing user_data.db files into PostgreSQL; preview unless --apply.

    python -m ofscraper.commands.postgres_import FOLDER [--apply]

FOLDER is searched for user_data.db files (for example <profile>/.data). The
PostgreSQL database is the one OFSC_DATABASE_URL names, as for the scraper
itself (see POSTGRESQL.md).

The files themselves are never opened. Each is copied to a staging folder
(with what SQLite keeps beside it: its -wal or -journal file), the copy is
brought up to date the way a scan would, and the rows are read from the copy. Without --apply nothing is written to PostgreSQL: the report
says what would be brought in, and what stands in the way. With --apply every
file goes in in one transaction, so it is all of them or nothing.
"""

import argparse
import asyncio
import contextlib
import math
import re
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import ofscraper.db.postgres as postgres

# every row of these belongs to a creator (model_id)
DATA_TABLES = ("medias", "posts", "messages", "stories", "others", "products", "labels")
# small, and shared between creators: a row that is already there is left
SHARED_TABLES = ("profiles", "models")
# made by this build, not copied. Nor are SQLite's own tables (sqlite_...)
NOT_COPIED = {"schema_flags"}
# a database, and what SQLite hasn't yet written into it (-wal) or needs to
# undo a write that was cut short (-journal)
SIDE_FILES = ("", "-wal", "-journal")
# bad values listed for one file
SHOWN = 20
BIGINT = 2**63
WHOLE_NUMBER = re.compile(r"[+-]?\d+")


class Refused(Exception):
    """The import can't go ahead: one sentence for the user."""


class Unconfirmed(Exception):
    """The connection went while the rows were being saved."""


class Changed(Exception):
    """A file was written to while it was being copied."""


class Bad(Exception):
    """A value PostgreSQL's column can't hold: why, in a few words."""


class Listed:
    """What can't be stored: how many, and the first few in words."""

    def __init__(self):
        self.count = 0
        self.shown = []

    def add(self, text):
        self.count += 1
        if len(self.shown) < SHOWN:
            self.shown.append(text)


def _many(number, word):
    return f"{number:,} {word}{'' if number == 1 else 's'}"


@dataclass
class Source:
    """One user_data.db: where it is, and what was learned from its copy."""

    path: Path
    staged: Path = None
    site: str = None
    # the creator its profiles table names, when that is exactly one
    owner: int = None
    creators: set = field(default_factory=set)
    counts: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    empty: bool = False


# --- values ---


def convert(value, kind):
    """`value`, read from SQLite, as PostgreSQL's column type `kind` takes it.
    Raises Bad for a value the column can't hold. Text arrives as bytes."""
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            raise Bad("isn't valid UTF-8 text") from None
    if value is None:
        return None
    if kind == "TEXT":
        if isinstance(value, bool):
            value = int(value)
        value = str(value)
        if "\x00" in value:
            raise Bad("has a null character in it")
        return value
    # SQLite keeps an empty text in any column: nothing was saved
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
    if kind == "BIGINT":
        return _whole_number(value)
    if kind == "BOOLEAN":
        return _yes_no(value)
    if kind == "NUMERIC":
        return _number(value)
    if kind == "TIMESTAMPTZ":
        try:
            return postgres.date_value(value)
        except (ValueError, TypeError, OverflowError, OSError):
            raise Bad(f"{value!r} isn't a date") from None
    raise Bad(f"is for a column type this build doesn't know ({kind})")


def _whole_number(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    elif isinstance(value, str) and WHOLE_NUMBER.fullmatch(value):
        value = int(value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise Bad(f"{_short(value)} isn't a whole number")
    if not -BIGINT <= value < BIGINT:
        raise Bad(f"{value} is too large")
    return value


def _yes_no(value):
    if isinstance(value, str) and value.lower() in ("0", "1", "true", "false"):
        return value.lower() in ("1", "true")
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise Bad(f"{_short(value)} is neither yes (1) nor no (0)")


def _number(value):
    if isinstance(value, str):
        try:
            value = int(value) if WHOLE_NUMBER.fullmatch(value) else float(value)
        except ValueError:
            raise Bad(f"{_short(value)} isn't a number") from None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Bad(f"{_short(value)} isn't a number")
    if isinstance(value, float) and not math.isfinite(value):
        raise Bad(f"{value} isn't a number")
    return value


def _short(value):
    text = repr(value)
    return text if len(text) <= 40 else text[:37] + "..."


# --- the files ---


def find(folder):
    return sorted(
        path for path in Path(folder).rglob("user_data.db") if path.is_file()
    )


def _state(path):
    """The size and time of a database and the files beside it."""
    found = []
    for suffix in SIDE_FILES:
        try:
            status = path.with_name(path.name + suffix).stat()
        except FileNotFoundError:
            found.append(None)
        else:
            found.append((status.st_size, status.st_mtime_ns))
    return found


def stage(path, folder, number):
    """Copy a database and the files SQLite keeps beside it to a folder of
    its own. The original is only read as a file. Only what is in the files
    is copied: a read-only original has a copy that can be brought up to
    date."""
    target = Path(folder) / str(number)
    target.mkdir(parents=True)
    before = _state(path)
    for suffix in SIDE_FILES:
        original = path.with_name(path.name + suffix)
        if original.is_file():
            shutil.copyfile(original, target / original.name)
    # the files are copied one after the other: a write in between would
    # give a copy that never was
    if _state(path) != before:
        raise Changed()
    return target / path.name


def _app():
    """The app's database code, imported late: the app reads the command line
    the first time its settings are read, and this command has its own."""
    sys.argv = sys.argv[:1]
    import ofscraper.main.open.load  # noqa: F401  (import order)
    import ofscraper.db.backup as backup
    import ofscraper.db.difference as difference
    import ofscraper.db.operations as operations
    import ofscraper.db.operations_.media as media
    import ofscraper.db.operations_.others as others
    import ofscraper.db.operations_.profile as profile
    import ofscraper.db.operations_.wrapper as wrapper
    import ofscraper.db.transition as transition
    import ofscraper.sites as sites

    return argparse.Namespace(
        backup=backup,
        difference=difference,
        operations=operations,
        media=media,
        others=others,
        profile=profile,
        transition=transition,
        wrapper=wrapper,
        sites=sites,
    )


def upgrade(source):
    """Bring the staged copy up to date, as a scan of its creator would, and
    note its site and creator. A reason it can't be brought in is added to
    source.problems."""
    app = _app()
    staged = source.staged

    async def go():
        await app.operations.create_tables(db_path=staged)
        if _nothing_in(staged):
            source.empty = True
            return
        flags = app.others.get_schema_changes(db_path=staged)
        newer = sorted(set(flags) - app.difference.ALL_FLAGS)
        if newer:
            source.problems.append(
                "it was last used by a newer version of the scraper than this"
                f" one (it has had the upgrade step {newer[0]!r}, which this"
                " version doesn't know)"
            )
            return
        owner = app.profile.get_single_model_via_profile(db_path=staged)
        if owner is not None and str(owner).isnumeric():
            source.owner = int(owner)
        # the size-skip repair reads the backups beside the database, and
        # the copy has none beside it: read the original's (they're only read)
        labels = set()
        if app.media.SIZE_SKIP_REPAIR_FLAG in app.difference.get_group_difference(
            db_path=staged
        ):
            labels = app.backup.media_labelled_in_backups(
                source.path, app.media.SIZE_SKIP_LABEL
            )
        # new_db: no backup of the copy, which is a copy already
        await app.transition.modify_tables(
            model_id=source.owner, db_path=staged, new_db=True, backup_labels=labels
        )
        unfinished = sorted(app.difference.get_group_difference(db_path=staged))
        if unfinished:
            source.problems.append(
                "its copy couldn't be brought up to date (the upgrade step"
                f" {unfinished[0]!r} didn't finish)"
            )
            return
        site = app.others.get_site_flag(db_path=staged)
        source.site = app.sites.normalize(site or app.sites.DEFAULT_SITE)
        if source.site is None:
            source.problems.append(
                f"it is for a site this version doesn't know ({site!r})"
            )

    try:
        asyncio.run(go())
    except (sqlite3.Error, OSError, ValueError) as E:
        source.problems.append(f"its copy couldn't be brought up to date ({E})")


def _nothing_in(staged):
    """Whether no creator has a row in the staged copy."""
    with contextlib.closing(_open(staged)) as conn:
        return not any(
            conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
            for table in DATA_TABLES
        )


def _open(staged):
    # the app's own way to a read-only file, which a network path needs
    uri = _app().wrapper._read_only_uri(Path(staged).resolve())
    conn = sqlite3.connect(uri, uri=True)
    # text as it is stored, so that text that isn't UTF-8 is a listed value
    # and not an error that stops the read
    conn.text_factory = bytes
    return conn


def _name(value):
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value


def tables(source):
    """{table: its columns} for the staged copy's tables PostgreSQL has.
    A table or column PostgreSQL has no place for is noted or refused."""
    found = {}
    with contextlib.closing(_open(source.staged)) as conn:
        names = [
            _name(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
        ]
        for table in names:
            if table in NOT_COPIED or table.startswith("sqlite_"):
                continue
            if table not in postgres.TABLE_COLUMNS:
                count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                source.notes.append(
                    f"its table {table!r} ({count} rows) isn't one of the"
                    " scraper's and is left out"
                )
                continue
            columns = [
                _name(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")
            ]
            unknown = [c for c in columns if c not in postgres.TABLE_COLUMNS[table]]
            if unknown:
                source.problems.append(
                    f"its table {table} has a column this version doesn't know"
                    f" ({unknown[0]})"
                )
                continue
            found[table] = [c for c in columns if c != "id"]
    return found


def rows(source, table, columns, bad):
    """One table's rows from the staged copy, oldest first, converted for
    PostgreSQL. A value that can't be converted is added to `bad` (as text)
    and its row left out; so is a row that names no creator, and a row
    PostgreSQL would take for one it already has."""
    kinds = postgres.COLUMN_TYPES[table]
    required = postgres.REQUIRED[table]
    converted = []
    # SQLite keeps two rows apart when one of them names no creator. Once
    # the creator is filled in they are one row to PostgreSQL, which would
    # refuse the whole import. Shared tables leave out a row already there
    keys = [
        (key, [columns.index(column) for column in key], {})
        for key in postgres.UNIQUE_KEYS[table]
        if table in DATA_TABLES and set(key) <= set(columns)
    ]
    with contextlib.closing(_open(source.staged)) as conn:
        cursor = conn.execute(
            f"SELECT rowid, {', '.join(columns)} FROM {table} ORDER BY rowid"
        )
        for number, *values in cursor:
            row = []
            fine = True
            for column, value in zip(columns, values):
                try:
                    value = convert(value, kinds[column])
                    if value is None and column == "model_id":
                        value = source.owner
                    if value is None and column in required:
                        raise Bad(
                            "has no creator, and the file's profiles don't name one"
                            if column == "model_id"
                            else "is empty"
                        )
                except Bad as E:
                    fine = False
                    bad.add(f"{table} row {number}, {column}: {E}")
                row.append(value)
            for key, positions, first in keys if fine else ():
                named = tuple(row[position] for position in positions)
                if None in named:
                    continue
                if named in first:
                    fine = False
                    bad.add(
                        f"{table} row {number}: has the same"
                        f" {' and '.join(key)} as row {first[named]}"
                    )
                    break
                first[named] = number
            if fine:
                converted.append(tuple(row))
    return converted


def read(source, write=None):
    """Read everything the staged copy holds. With `write`, each table's rows
    are handed to write(table, columns, rows); without, they are only checked
    and counted. Problems are added to source.problems."""
    bad = Listed()
    for table, columns in tables(source).items():
        converted = rows(source, table, columns, bad)
        source.counts[table] = len(converted)
        if table in DATA_TABLES:
            position = columns.index("model_id")
            source.creators.update(row[position] for row in converted)
        if write and not bad.count:
            write(table, columns, converted)
    # a scan adds its creator to models when it starts: a file from before
    # that table, or one a scan never finished, hasn't the row
    if write and not bad.count:
        write("models", ["model_id"], [(c,) for c in sorted(source.creators)])
    if bad.count:
        more = f" (and {bad.count - SHOWN:,} more)" if bad.count > SHOWN else ""
        source.problems.append(
            f"{_many(bad.count, 'value')} can't be stored{more}:\n      "
            + "\n      ".join(bad.shown)
        )


def examine(paths, staging):
    """Stage, upgrade and check each file. Returns a Source for each."""
    sources = []
    for number, path in enumerate(paths):
        source = Source(path=path)
        sources.append(source)
        try:
            source.staged = stage(path, staging, number)
        except OSError as E:
            source.problems.append(f"it couldn't be copied ({E})")
            continue
        except Changed:
            source.problems.append(
                "it changed while it was being copied: close the scraper and"
                " run this again"
            )
            continue
        upgrade(source)
        if source.empty or source.problems:
            continue
        try:
            read(source)
        except sqlite3.Error as E:
            source.problems.append(f"its copy couldn't be read ({E})")
    # a creator's rows have one home: two files for one creator would clash
    seen = {}
    for source in sources:
        if source.problems or source.empty:
            continue
        for creator in source.creators:
            seen.setdefault((source.site, creator), []).append(source)
    for (_site, creator), holders in sorted(seen.items(), key=str):
        if len(holders) > 1:
            # Merge Databases takes files of one creator each
            advice = (
                "put the two together with Merge Databases first"
                if all(len(s.creators) == 1 for s in holders)
                else "a creator can be brought in from one file only"
            )
            for source in holders:
                others = ", ".join(str(s.path) for s in holders if s is not source)
                source.problems.append(
                    f"creator {creator} is also in {others}: {advice}"
                )
    return sources


# --- PostgreSQL ---


class Target:
    """The PostgreSQL database, through the engine the scraper uses."""

    def __init__(self):
        import ofscraper.utils.of_env.of_env as of_env

        self.engine = postgres.POSTGRES
        self.timeout = of_env.getattr("DATABASE_TIMEOUT")
        self.conn = None

    @property
    def errors(self):
        """What the server's refusals are raised as."""
        return self.engine.errors

    def check(self):
        return self.engine.check()

    def open(self, read_only):
        schema = postgres.schema_name(_app().sites.DEFAULT_SITE)
        self.conn = self.engine.connect(schema, read_only, timeout=self.timeout)

    def prepare(self, sites, flags):
        for site in sites:
            self.engine.create_tables(flags, schema=postgres.schema_name(site))

    def creators(self, site):
        """The creators the site's data tables already hold rows for."""
        schema = postgres.schema_name(site)
        found = set()
        with self.conn.cursor() as cur:
            there = {
                row[0]
                for row in cur.execute(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema = ?",
                    [schema],
                ).fetchall()
            }
            for table in DATA_TABLES:
                if table in there:
                    found.update(
                        row[0]
                        for row in cur.execute(
                            f"SELECT DISTINCT model_id FROM {schema}.{table}"
                        ).fetchall()
                    )
        return found

    def count(self, site, table):
        with self.conn.cursor() as cur:
            return cur.execute(
                f"SELECT COUNT(*) FROM {postgres.schema_name(site)}.{table}"
            ).fetchone()[0]

    def write(self, site, table, columns, rows):
        """Add rows to a table; returns how many are new there."""
        name = f"{postgres.schema_name(site)}.{table}"
        listed = ", ".join(columns)
        with self.conn.cursor() as cur:
            if table in SHARED_TABLES:
                before = self.count(site, table)
                marks = ", ".join("?" for _ in columns)
                cur.executemany(
                    f"INSERT INTO {name} ({listed}) VALUES ({marks})"
                    " ON CONFLICT DO NOTHING",
                    rows,
                )
                return self.count(site, table) - before
            with cur.copy(f"COPY {name} ({listed}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row(row)
            return len(rows)

    def commit(self):
        self.conn.commit()

    def close(self):
        if self.conn is not None:
            self.engine.close(self.conn)
            self.conn = None


def already_there(sources, target):
    """Refuse the files whose creators PostgreSQL already has rows for."""
    held = {}
    for source in sources:
        if source.problems or source.empty:
            continue
        if source.site not in held:
            held[source.site] = target.creators(source.site)
        both = sorted(source.creators & held[source.site])
        if both:
            source.problems.append(
                f"PostgreSQL already has rows for creator {both[0]}"
                + (f" (and {len(both) - 1} more)" if len(both) > 1 else "")
            )


def bring_in(sources, target, flags):
    """Write every good source in one transaction. Returns {site: {table:
    rows added}}. Nothing is kept unless every row arrives."""
    good = [s for s in sources if not s.problems and not s.empty]
    target.prepare(sorted({s.site for s in good}), flags)
    target.open(read_only=False)
    added = {}
    before = {}
    for source in good:
        site_added = added.setdefault(source.site, {})

        def write(table, columns, converted, source=source, site_added=site_added):
            if (source.site, table) not in before:
                before[source.site, table] = target.count(source.site, table)
            new = target.write(source.site, table, columns, converted)
            site_added[table] = site_added.get(table, 0) + new

        read(source, write)
        if source.problems:
            raise Refused(
                f"{source.path} changed while it was being brought in:"
                f" {source.problems[-1]}"
            )
    for (site, table), count in before.items():
        now = target.count(site, table)
        if now != count + added[site][table]:
            raise Refused(
                f"{site}.{table} holds {now} rows where"
                f" {count + added[site][table]} were expected"
            )
    try:
        target.commit()
    except tuple(target.errors) as E:
        # the server may have kept the rows before the connection went
        raise Unconfirmed() from E
    return added


# --- the report ---


def report(sources, out):
    good = [s for s in sources if not s.problems and not s.empty]
    for site in sorted({s.site for s in good}):
        of_site = [s for s in good if s.site == site]
        creators = set().union(*(s.creators for s in of_site))
        out(
            f"{site}: {_many(len(of_site), 'file')},"
            f" {_many(len(creators), 'creator')}"
        )
        for table in (*DATA_TABLES, *SHARED_TABLES):
            count = sum(s.counts.get(table, 0) for s in of_site)
            if count:
                out(f"  {table:<9} {count:>10,} rows")
    empty = [s for s in sources if s.empty]
    if empty:
        out(
            "1 file has nothing in it and is left out."
            if len(empty) == 1
            else f"{len(empty):,} files have nothing in them and are left out."
        )
    for source in sources:
        for note in source.notes:
            out(f"Note: {source.path}: {note}.")
    bad = [s for s in sources if s.problems]
    if bad:
        out(f"\n{_many(len(bad), 'file')} can't be brought in:")
        for source in bad:
            out(f"  {source.path}")
            for problem in source.problems:
                out(f"    - {problem}")
    return good, bad


def run(folder, apply=False, skip_bad=False, staging=None, target=None, out=print):
    """The command. Returns its exit code: 0 when everything found was (or
    could be) brought in."""
    folder = Path(folder)
    if not folder.is_dir():
        out(f"There is no folder at {folder}.")
        return 2
    paths = find(folder)
    if not paths:
        out(f"No user_data.db files were found under {folder}.")
        return 2
    if apply and not (target or postgres.enabled()):
        out(
            f"{postgres.URL_KEY} isn't set, so there is no PostgreSQL database"
            " to bring the files into. See POSTGRESQL.md."
        )
        return 2
    out(f"Found {_many(len(paths), 'user_data.db file')} under {folder}.")
    # a new folder of this run's own, so that nothing already in the staging
    # folder is touched, and nothing of this run is left
    if staging is not None:
        Path(staging).mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="ofscraper-import-", dir=staging))
    if target is None and postgres.enabled():
        target = Target()
    refusals = (Refused, postgres.PostgresUnavailable)
    try:
        if target:
            target.check()
            # the driver's own errors, now that it is known to be installed
            refusals += tuple(target.errors)
        out("Copying each file and checking the copy (the files aren't opened)...")
        sources = examine(paths, staging)
        if target:
            target.open(read_only=True)
            try:
                already_there(sources, target)
            finally:
                target.close()
        good, bad = report(sources, out)
        if not target:
            out(
                f"\n{postgres.URL_KEY} isn't set: the files were checked, and"
                " PostgreSQL wasn't."
            )
        if not good:
            out("\nThere is nothing to bring in.")
            return 1 if bad else 0
        if not apply:
            out(
                "\nNothing was written. Run again with --apply to bring"
                f" {_many(len(good), 'file')} in."
                + (
                    " The files listed above stop that: fix them or move them"
                    " out of the folder, or add --skip-bad-files to leave"
                    " them out."
                    if bad
                    else ""
                )
            )
            return 1 if bad else 0
        if bad and not skip_bad:
            out(
                "\nNothing was written: the files listed above can't be"
                " brought in. Fix them or move them out of the folder, or"
                " add --skip-bad-files to bring in the rest."
            )
            return 1
        out(f"\nBringing {_many(len(good), 'file')} in...")
        try:
            added = bring_in(sources, target, _app().difference.ALL_FLAGS)
        finally:
            target.close()
        for site, counts in sorted(added.items()):
            total = sum(counts.get(table, 0) for table in DATA_TABLES)
            out(f"{site}: {total:,} rows added.")
        if bad:
            out(
                "Done. The files brought in are unchanged and are no longer"
                f" used. The {_many(len(bad), 'file')} left out"
                f" {'is' if len(bad) == 1 else 'are'} still only in SQLite."
            )
        else:
            out("Done. The user_data.db files are unchanged and are no longer used.")
        return 1 if bad else 0
    except Unconfirmed:
        out(
            "\nThe connection was lost while the rows were being saved, so"
            " PostgreSQL may or may not have kept them. Run this again without"
            " --apply: it says which creators PostgreSQL already has."
        )
        return 1
    except refusals as E:
        # closing the connection rolled the transaction back
        out(f"\nNothing was written. {postgres.masked(' '.join(str(E).split()))}")
        return 1
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "folder", type=Path, help="folder to search for user_data.db files"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write to PostgreSQL; without it, only report",
    )
    parser.add_argument(
        "--skip-bad-files",
        action="store_true",
        help="with --apply, bring in the files that can be and leave out the rest",
    )
    parser.add_argument(
        "--staging",
        type=Path,
        help="folder for the working copies, which need as much room as the"
        " files (default: the system's temporary folder)",
    )
    args = parser.parse_args(argv)
    # the scraper's own settings: OFSC_DATABASE_URL may be in an env file
    # that config.json names
    _app()
    import ofscraper.utils.settings as settings

    settings.get_settings()
    return run(
        args.folder,
        apply=args.apply,
        skip_bad=args.skip_bad_files,
        staging=args.staging,
    )


if __name__ == "__main__":
    raise SystemExit(main())
