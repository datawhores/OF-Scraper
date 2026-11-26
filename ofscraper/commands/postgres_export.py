"""Write what PostgreSQL holds back to user_data.db files; preview unless --apply.

    python -m ofscraper.commands.postgres_export FOLDER [--apply] [--site SITE]

The other direction of postgres_import, for going back to SQLite files. The
PostgreSQL database is the one OFSC_DATABASE_URL names (see POSTGRESQL.md),
and it is only read. Every creator it has rows for gets a file of their own,
FOLDER/<the creator's id>/user_data.db: the layout of a profile's .data
folder with the default `metadata` setting.

Without --apply nothing is written: the report says which files would be
made. A file that is already there is never changed: its creator is left out
and listed, and naming another FOLDER gets their rows out. Each file is made
under another name beside its place, by the code that makes a new creator's
database, and is given its name only once it is whole and holds what
PostgreSQL gave.
"""

import argparse
import asyncio
import contextlib
import os
import sqlite3
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import ofscraper.commands.postgres_import as importer
import ofscraper.db.postgres as postgres
import ofscraper.sites as sites

DATABASE = "user_data.db"
# the end of a file's name while it is being made
PARTIAL = ".partial"
# a database, and everything SQLite can leave beside one
BESIDE = (*importer.SIDE_FILES, "-shm")
# every table a creator's rows are in
TABLES = (*importer.DATA_TABLES, *importer.SHARED_TABLES)
# the column that names a row's creator, where it isn't model_id
CREATOR_COLUMN = {"profiles": "user_id"}
ALREADY_THERE = "it is already there, and a file that is there is never changed"
# said under a value that stops a creator's file
IN_POSTGRESQL = (
    "that value is in PostgreSQL: change it there, then run this again. A row's"
    " number is its place among the creator's rows of the table, oldest first"
)
# SQLite's whole numbers are 64 bits
LARGEST = 2**63


class Taken(Exception):
    """A file has appeared where a new one was to go."""


class Unkept(Exception):
    """A value PostgreSQL holds that a user_data.db can't keep as it is:
    which, in words."""


@dataclass
class File:
    """One creator's user_data.db: where it goes, and how many rows
    PostgreSQL holds for it."""

    site: str
    creator: int
    path: Path
    counts: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)
    written: bool = False


# --- PostgreSQL ---


class Database(importer.Target):
    """The PostgreSQL database, read through the engine the scraper uses."""

    def open(self, read_only=True):
        # never to write, whatever is asked
        super().open(read_only=True)
        # one view of the database for the whole run, whatever a scraper
        # saves meanwhile
        with self.conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

    def _tables(self, cur, site):
        return {
            row[0]
            for row in cur.execute(
                "SELECT table_name FROM information_schema.tables"
                " WHERE table_schema = ?",
                [postgres.schema_name(site)],
            ).fetchall()
        }

    def held(self, site):
        """{creator: {table: rows}} for every creator the site's tables
        name. Nothing for a site whose tables were never made."""
        schema = postgres.schema_name(site)
        found = {}
        with self.conn.cursor() as cur:
            there = self._tables(cur, site)
            for table in TABLES:
                if table not in there:
                    continue
                column = CREATOR_COLUMN.get(table, "model_id")
                for creator, count in cur.execute(
                    f"SELECT {column}, COUNT(*) FROM {schema}.{table} GROUP BY {column}"
                ).fetchall():
                    found.setdefault(creator, {})[table] = count
        return found

    def flags(self, site):
        """The upgrade steps the site's tables have had."""
        with self.conn.cursor() as cur:
            if "schema_flags" not in self._tables(cur, site):
                return set()
            return {
                row[0]
                for row in cur.execute(
                    f"SELECT flag_name FROM {postgres.schema_name(site)}.schema_flags"
                    " WHERE flag_value = '1'"
                ).fetchall()
            }

    def lacking(self, site, table):
        """The columns added since PostgreSQL could first be used
        (postgres.ADDED_COLUMNS) that the site's table hasn't got. The
        scraper adds them when it starts, and this command only reads: a
        database last used by an earlier version is still without them."""
        added = {
            column
            for _flag, name, columns in postgres.ADDED_COLUMNS
            if name == table
            for column in columns
        }
        if not added:
            return added
        with self.conn.cursor() as cur:
            there = {
                row[0]
                for row in cur.execute(
                    "SELECT column_name FROM information_schema.columns"
                    " WHERE table_schema = ? AND table_name = ?",
                    [postgres.schema_name(site), table],
                ).fetchall()
            }
        return added - there

    def rows(self, site, table, columns, creator):
        """One creator's rows of a table, oldest first, as the scraper reads
        them: a yes or no as 1 or 0, a date as ISO text. A column the table
        hasn't got yet (see lacking) is read as empty."""
        lacking = self.lacking(site, table)
        listed = ", ".join(
            f"NULL AS {column}" if column in lacking else column for column in columns
        )
        with self.conn.cursor() as cur:
            return cur.execute(
                f"SELECT {listed} FROM {postgres.schema_name(site)}.{table}"
                f" WHERE {CREATOR_COLUMN.get(table, 'model_id')} = ? ORDER BY id",
                [creator],
            ).fetchall()


# --- the files ---


def plan(folder, site, held):
    """A File for each creator in `held` ({creator: {table: rows}}). One
    whose file is already there has that as its problem, and isn't written."""
    files = []
    for creator in sorted(held):
        file = File(
            site=site,
            creator=creator,
            path=Path(folder) / str(creator) / DATABASE,
            counts=dict(held[creator]),
        )
        # a link that leads nowhere is in the way too. So is what SQLite kept
        # beside a database that has gone: it would be read into the new file
        there = [
            DATABASE + suffix
            for suffix in importer.SIDE_FILES
            if os.path.lexists(file.path.with_name(DATABASE + suffix))
        ]
        if DATABASE in there:
            file.problems.append(ALREADY_THERE)
        elif there:
            file.problems.append(
                f"{there[0]} is there without its database, and SQLite would"
                " read it into a new one: move it away first"
            )
        files.append(file)
    return files


def fill(temporary, file, read):
    """Make a database at `temporary` the way a scan makes a new creator's,
    and put in the rows read(table, columns) gives. A value SQLite can't
    keep as it was given raises Unkept."""
    app = importer._app()

    async def make():
        await app.operations.create_tables(db_path=temporary)
        # every upgrade step has nothing to do in a new file and is recorded
        # as done. backup_labels: no backup beside the file is read
        await app.transition.modify_tables(
            db_path=temporary, new_db=True, backup_labels=set()
        )
        # only a file of another site than OnlyFans says which site it is for
        if file.site != sites.DEFAULT_SITE:
            await app.others.write_site_flag(file.site, db_path=temporary)

    try:
        asyncio.run(make())
    finally:
        # that code works on one thread of its own, which Ctrl-C doesn't
        # stop: it has the file open until what it was doing is done. Wait
        # for that, so that what was made so far can be removed (a second
        # Ctrl-C ends the wait, and can leave it)
        app.wrapper._DB_POOL.submit(lambda: None).result()
    # the new file's own tables and columns, without each row's own id
    source = importer.Source(path=file.path, staged=temporary)
    wanted = importer.tables(source)
    if source.problems:
        raise ValueError(source.problems[0])
    with contextlib.closing(sqlite3.connect(temporary)) as conn:
        for table, columns in wanted.items():
            listed = ", ".join(columns)
            rows = [tuple(row) for row in read(table, columns)]
            _fits(table, columns, rows)
            conn.executemany(
                f"INSERT INTO {table} ({listed})"
                f" VALUES ({', '.join('?' for _ in columns)})",
                rows,
            )
            kept = conn.execute(
                f"SELECT {listed} FROM {table} ORDER BY rowid"
            ).fetchall()
            _same(table, columns, rows, kept)
        # a scan adds its creator to models when it starts
        conn.execute(app.profile.modelInsert, [file.creator])
        conn.commit()
        # Until now SQLite kept the rows beside the file (in its -wal file),
        # and only the file itself gets the name. Closing the file moves
        # them too, but says nothing when it can't: another program that
        # has the file open is enough to stop it
        busy = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()[0]
        if busy:
            raise sqlite3.OperationalError("the rows couldn't be moved into the file")


def _fits(table, columns, rows):
    """A whole number of more than 64 bits is one SQLite can't take."""
    for number, row in enumerate(rows, start=1):
        for column, value in zip(columns, row):
            if isinstance(value, int) and not -LARGEST <= value < LARGEST:
                raise Unkept(
                    f"{table} row {number}, {column}: {importer._short(value)}"
                    " is too large a number for SQLite"
                )


def _same(table, columns, given, kept):
    """SQLite's columns keep some values their own way (text that reads as a
    number becomes one in an id column). Such a row would no longer be the
    row PostgreSQL holds."""
    for number, (was, now) in enumerate(zip(given, kept), start=1):
        for column, before, after in zip(columns, was, now):
            if before != after:
                raise Unkept(
                    f"{table} row {number}, {column}: SQLite keeps"
                    f" {importer._short(before)} as {importer._short(after)}"
                )
    if len(given) != len(kept):
        raise ValueError(f"{table} kept {len(kept)} of {len(given)} rows")


def check(temporary, file):
    """The finished file, read the way the import reads a file: it has to
    hold nothing the import would refuse (Unkept), and as many rows as
    PostgreSQL does for the creator (ValueError)."""
    source = importer.Source(path=file.path, staged=temporary)
    importer.read(source)
    if source.problems:
        raise Unkept(source.problems[0])
    expected = dict(file.counts, models=1)
    for table in TABLES:
        found = source.counts.get(table, 0)
        if found != expected.get(table, 0):
            raise ValueError(
                f"its {table} table holds {found} rows where PostgreSQL holds"
                f" {expected.get(table, 0)}"
            )


def place(temporary, path):
    """Give a finished file its name. A file that took the name meanwhile is
    left as it is: Taken. The caller removes the other name.

    Where the disk can give a file a second name (a hard link), and on
    Windows, the step that gives the name is the one that refuses a name
    that is taken. On another system's disk without second names (FAT and
    exFAT, some network shares) the name is looked for first and given
    after: a file another program makes in the moment between is replaced.
    Holding the name with an empty file first would close that moment, and
    leave an empty user_data.db behind when the run is killed."""
    try:
        # a second name for the file: never given in place of another file
        os.link(temporary, path)
    except FileExistsError:
        raise Taken() from None
    except OSError:
        if os.path.lexists(path):
            raise Taken() from None
        try:
            os.rename(temporary, path)
        except FileExistsError:
            # Windows, where a rename doesn't replace
            raise Taken() from None


def write(file, read):
    """Make file.path, whole or not at all. Why it couldn't be made is added
    to file.problems; what the server refuses is raised, and so is Ctrl-C.
    Either way nothing else is left behind, unless another program has the
    unfinished file open: Windows then doesn't let it be removed. Only a
    run that is killed leaves it otherwise, and never under the name
    user_data.db."""
    folder = file.path.parent
    new_folder = not folder.exists()
    temporary = folder / f"{DATABASE}.{uuid.uuid4().hex}{PARTIAL}"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        fill(temporary, file, read)
        check(temporary, file)
        place(temporary, file.path)
        file.written = True
    except Taken:
        file.problems.append(
            "a file appeared there while this ran, and was left as it is"
        )
    except Unkept as E:
        file.problems += [str(E), IN_POSTGRESQL]
    except (sqlite3.Error, OSError, ValueError) as E:
        file.problems.append(f"it couldn't be written ({E})")
    finally:
        for suffix in BESIDE:
            with contextlib.suppress(OSError):
                temporary.with_name(temporary.name + suffix).unlink(missing_ok=True)
        if new_folder and not file.written:
            with contextlib.suppress(OSError):
                folder.rmdir()


# --- the report ---


def _listed(files, out):
    for file in files:
        out(f"  {file.path}")
        for problem in file.problems:
            out(f"    - {problem}")


def report(files, out):
    good = [f for f in files if not f.problems]
    for site in sorted({f.site for f in good}):
        of_site = [f for f in good if f.site == site]
        out(f"{site}: {importer._many(len(of_site), 'creator')}")
        for table in TABLES:
            count = sum(f.counts.get(table, 0) for f in of_site)
            if count:
                out(f"  {table:<9} {count:>10,} rows")
    bad = [f for f in files if f.problems]
    if bad:
        out(
            f"\n{importer._many(len(bad), 'creator')}"
            f" {'is' if len(bad) == 1 else 'are'} left out:"
        )
        _listed(bad, out)
        out("To write their files anyway, run this again with another folder.")
    return good, bad


def run(folder, apply=False, site=None, target=None, out=print):
    """The command. Returns its exit code: 0 when every creator PostgreSQL
    has rows for got (or could get) a file."""
    folder = Path(folder)
    if os.path.lexists(folder) and not folder.is_dir():
        out(f"{folder} isn't a folder.")
        return 2
    if not (target or postgres.enabled()):
        out(
            f"{postgres.URL_KEY} isn't set, so there is no PostgreSQL database"
            " to write files from. See POSTGRESQL.md."
        )
        return 2
    app = importer._app()
    if target is None:
        target = Database()
    refusals = (importer.Refused, postgres.PostgresUnavailable)
    files = []
    try:
        target.check()
        # the driver's own errors, now that it is known to be installed
        refusals += tuple(target.errors)
        out("Reading what PostgreSQL holds (it is only read)...")
        try:
            target.open()
            held = {name: target.held(name) for name in sites.SITES}
            held = {name: creators for name, creators in held.items() if creators}
            if site and site not in held:
                # most likely the other site was meant
                others = " and ".join(sorted(held))
                out(
                    f"PostgreSQL has no rows for {site}."
                    + (f" It has rows for {others}." if others else "")
                )
                return 0
            if site:
                held = {site: held[site]}
            if not held:
                out("PostgreSQL has no rows.")
                return 0
            if len(held) > 1:
                # a site's creators are one profile's, with a .data folder of
                # its own, and an id is a creator of its own on each site
                out(
                    f"PostgreSQL has rows for {' and '.join(sorted(held))}. Each"
                    " site's files go in a folder of their own: run this once"
                    " for each, with --site and that site's folder."
                )
                return 2
            ((site, creators),) = held.items()
            newer = sorted(target.flags(site) - app.difference.ALL_FLAGS)
            if newer:
                raise importer.Refused(
                    f"PostgreSQL's tables for {site} were last used by a newer"
                    " version of the scraper than this one (they have had the"
                    f" upgrade step {newer[0]!r}, which this version doesn't know)."
                )
            files = plan(folder, site, creators)
            good, bad = report(files, out)
            if not good:
                out("\nThere is nothing to write.")
                return 1 if bad else 0
            if not apply:
                out(
                    "\nNothing was written. Run again with --apply to write"
                    f" {importer._many(len(good), 'file')} under {folder}."
                )
                return 1 if bad else 0
            out(f"\nWriting {importer._many(len(good), 'file')} under {folder}...")
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as E:
                raise importer.Refused(f"{folder} couldn't be made ({E}).") from E
            for file in good:

                def read(table, columns, file=file):
                    return target.rows(file.site, table, columns, file.creator)

                write(file, read)
        finally:
            target.close()
        done = [f for f in good if f.written]
        failed = [f for f in good if f.problems]
        total = sum(f.counts.get(table, 0) for f in done for table in TABLES)
        out(f"{site}: {importer._many(len(done), 'file')} written, {total:,} rows.")
        if failed:
            out(f"\n{importer._many(len(failed), 'file')} couldn't be written:")
            _listed(failed, out)
        out("Done. PostgreSQL was only read, and still holds everything.")
        return 1 if bad or failed else 0
    except refusals as E:
        done = sum(f.written for f in files)
        # a file that has its name is whole: only the rest is missing
        out(
            f"\n{'Stopped' if done else 'Nothing was written'}."
            f" {postgres.masked(' '.join(str(E).split()))}"
        )
        if done:
            out(
                f"{importer._many(done, 'file')} had been written by then."
                " A second run leaves out what is already there."
            )
        return 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="folder the user_data.db files go under, one folder per creator",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the files; without it, only report",
    )
    parser.add_argument(
        "--site",
        choices=sites.SITES,
        help="the site whose creators are written; needed only when PostgreSQL"
        " has rows for more than one site",
    )
    args = parser.parse_args(argv)
    # the scraper's own settings: OFSC_DATABASE_URL may be in an env file
    # that config.json names
    importer._app()
    import ofscraper.utils.settings as settings

    settings.get_settings()
    return run(args.folder, apply=args.apply, site=args.site)


if __name__ == "__main__":
    raise SystemExit(main())
