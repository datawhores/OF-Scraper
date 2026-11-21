r"""List and record the usernames each creator account has had.

OF-Scraper keeps one database per account ({data_dir}/{model_id}/user_data.db). Its
`profiles` table holds one row per (account, username) pair, and OF-Scraper adds a row
whenever it processes a creator under a name it hasn't seen, so a renamed creator ends up
with several rows. With each name it keeps two dates: when it first and when it last
worked on the creator under that name. This script reads that history back and can record
a name you learned elsewhere (e.g. from an older download tool).

    python scripts/creator_names.py                      # accounts with more than one name
    python scripts/creator_names.py --all                # every account and its names
    python scripts/creator_names.py --find NAME          # account(s) that ever used NAME
    python scripts/creator_names.py --add MODEL_ID NAME  # record another name
    python scripts/creator_names.py --add MODEL_ID NAME --seen 2024-03-01
                                                         # ... and when it was in use
    python scripts/creator_names.py --csv names.csv      # also write the listing to CSV

The default data directory is the default `metadata` location for the main profile,
{home_directory}/.config/ofscraper/main_profile/.data; use --data-dir if yours differs.

The listing shows the days each name was seen on, after the name. A name has no dates if
it was recorded before OF-Scraper kept them, or added here without --seen. The CSV has
the full dates (in UTC), one for each name, in the same order as the names.

For a deleted account, OF-Scraper names the folder after one of the names recorded here
(ofscraper/db/operations_/profile.py, get_profile_info):

- the name it saw last, going by the dates;
- if no name of the account has a date, the first one in alphabetical order (capital
  letters first). That is the name it used before it kept dates;
- the placeholder it gives a deleted account (modeldeleted or modeldeleted_<id>) only
  when no other name is recorded.

The listing shows that name as "folder if deleted". If you changed
DELETED_MODEL_PLACEHOLDER, set OFSC_DELETED_MODEL_PLACEHOLDER to the same value when you
run this script.

This script only records names: files already downloaded stay in the folder of the name
they were saved under. To move them to the current name's folder, see MOVING_FILES.md
(python -m ofscraper.commands.move_creator_files).

--add appends a name and ignores one already recorded. --seen DATE says when the name was
in use: 2024-03-01, or with a time, 2024-03-01T09:30:00+00:00 (without an offset the time
is UTC). A new name gets DATE as both of its dates. For a name already recorded, the dates
are widened to take DATE in and never narrowed. A date more than a day in the future is
refused (a day is allowed, because today's date where you are can be tomorrow's in UTC).
Without --seen the name gets no dates, and one already recorded keeps its own. --seen
needs a database that OF-Scraper has opened since it started keeping dates, and isn't
taken for the placeholder, which never has a date.

--add refuses a name, or a date, that would change the folder name OF-Scraper uses for
a deleted account, unless you pass --force. Close OF-Scraper before using --add.

--force doesn't choose the folder name: the rule above does. For a deleted account
OF-Scraper keeps moving the last-seen date of the name it uses, each time it works on the
account. So a name added without a date, or with an older one, doesn't become the folder
name, with --force or without. To make a name the folder name on purpose, give it a --seen
later than the last-seen date of every other name (the time now will do; the CSV has the
full dates) and pass --force. When no name of the account has a date, any --seen does
that, and without --seen only a name that comes first in alphabetical order does. The
placeholder can't be made the folder name while another name is recorded.

The files are OnlyFans only: Fansly databases ({model_id}/fansly/user_data.db) aren't
read. With --postgres [--site onlyfans|fansly] (default onlyfans), the script lists and
adds names in that site's tables in the PostgreSQL database OFSC_DATABASE_URL names in
the environment it is run in (not the scraper's settings or env files), in place of the
files: the same listing, CSV, folder name and refusals, for the creators PostgreSQL has
rows for. --add there is one transaction, kept only if nothing is refused. It needs the
PostgreSQL driver and the scraper this script is in (run it from that checkout).
"""

import argparse
import contextlib
import csv
import datetime
import importlib
import os
import pathlib
import sqlite3
import sys

DEFAULT_DATA_DIR = pathlib.Path.home() / ".config" / "ofscraper" / "main_profile" / ".data"

# The queries OF-Scraper picks a deleted account's name with (deletedAccountName and
# deletedAccountNameUndated in ofscraper/db/operations_/profile.py); the first row is the
# name. test_creator_names fails when a copy here differs from the original.
FOLDER_NAME = """
SELECT username FROM profiles WHERE user_id = ?
ORDER BY
    CASE WHEN username = ? OR username = ? THEN 1 ELSE 0 END,
    CASE WHEN last_seen_at IS NULL THEN 1 ELSE 0 END,
    last_seen_at DESC,
    CASE WHEN last_seen_at IS NULL THEN 0 ELSE id END DESC,
    username
"""
# for a database from before the dates
FOLDER_NAME_UNDATED = """
SELECT username FROM profiles WHERE user_id = ?
ORDER BY
    CASE WHEN username = ? OR username = ? THEN 1 ELSE 0 END,
    username
"""
# first_seen_at only ever moves back and last_seen_at only forward. The dates are text
# of one form (see parse_seen), so the order of the text is the order of the times.
WIDEN_DATES = """
UPDATE profiles SET
    first_seen_at = CASE
        WHEN first_seen_at IS NULL OR first_seen_at > ? THEN ? ELSE first_seen_at END,
    last_seen_at = CASE
        WHEN last_seen_at IS NULL OR last_seen_at < ? THEN ? ELSE last_seen_at END
WHERE user_id = ? AND username = ?
"""
# a name is added once, on either engine (as the scraper's profileInsert)
ADD_NAME = "INSERT INTO profiles (user_id, username) VALUES (?, ?) ON CONFLICT DO NOTHING"
SITES = ("onlyfans", "fansly")
SEEN = ("first_seen_at", "last_seen_at")


class FolderNameWouldChange(Exception):
    """--add would change the folder name OF-Scraper uses for a deleted account."""


def _connect_ro(db):
    return sqlite3.connect(pathlib.Path(db).resolve().as_uri() + "?mode=ro", uri=True)


def _has_dates(con):
    """Whether the database has the two dates: one that OF-Scraper hasn't opened since it
    started keeping them has not."""
    return "last_seen_at" in {row[1] for row in con.execute("PRAGMA table_info('profiles')")}


def placeholder_names(model_id):
    """The two names OF-Scraper gives a deleted account whose own name it doesn't know."""
    placeholder = os.environ.get("OFSC_DELETED_MODEL_PLACEHOLDER", "modeldeleted")
    return placeholder, f"{placeholder}_{model_id}"


def folder_name(con, model_id):
    """The name OF-Scraper uses for a deleted account's folder: the first row of the same
    query it runs (ofscraper/db/operations_/profile.py, get_profile_info)."""
    row = con.execute(
        FOLDER_NAME if _has_dates(con) else FOLDER_NAME_UNDATED,
        (int(model_id), *placeholder_names(int(model_id))),
    ).fetchone()
    return row[0] if row else None


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_seen(text):
    """A date given to --seen, as OF-Scraper saves one: ISO text in UTC, to the second
    (2024-03-01T09:30:00+00:00). Raises ValueError for text that isn't a date, and for a
    date more than a day in the future."""
    try:
        moment = datetime.datetime.fromisoformat(text.strip())
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=datetime.timezone.utc)
        # OverflowError: a date at the very start or end of the calendar, whose offset
        # takes it past that in UTC
        moment = moment.astimezone(datetime.timezone.utc).replace(microsecond=0)
    except (ValueError, OverflowError):
        raise ValueError(
            f"--seen: {text!r} isn't a date. Write it as 2024-03-01, or with a time as "
            "2024-03-01T09:30:00+00:00."
        ) from None
    # a day's grace: a date without a time is its first moment in UTC, which is still to
    # come for someone whose own day began earlier
    if moment > _now() + datetime.timedelta(days=1):
        raise ValueError(f"--seen: {text!r} is more than a day in the future.")
    return moment.isoformat()


def accounts(data_dir):
    """Yield (model_id, names in the order they were recorded, media count, folder name
    if deleted, each name's (first seen, last seen)) per account."""
    for db in sorted(pathlib.Path(data_dir).glob("*/user_data.db")):
        model_id = db.parent.name
        with contextlib.closing(_connect_ro(db)) as con:
            try:
                dates = "first_seen_at, last_seen_at" if _has_dates(con) else "NULL, NULL"
                found = con.execute(
                    f"SELECT username, {dates} FROM profiles ORDER BY id"
                ).fetchall()
                media = con.execute("SELECT count(*) FROM medias").fetchone()[0]
                folder = folder_name(con, model_id) if model_id.isdigit() else None
            except sqlite3.OperationalError:
                continue
        yield model_id, [r[0] for r in found], media, folder, [r[1:] for r in found]


def add_name(data_dir, model_id, name, force=False, seen=None, postgres=None):
    """Record `name` for `model_id`, seen at `seen` if that is given (see parse_seen).
    Returns True if a row was added, False if it existed. With `postgres`
    (creator_rows, database URL, site), in that site's tables instead of the file.

    Raises FolderNameWouldChange, without changing anything, if the name or the date
    would change the folder name OF-Scraper uses for the account once it's deleted,
    unless `force`."""
    if not str(model_id).isdigit():
        raise ValueError(f"MODEL_ID must be a number, got {model_id!r}")
    name = name.strip()
    if not name:
        raise ValueError("NAME can't be empty")
    when = parse_seen(seen) if seen is not None else None
    if when and name in placeholder_names(model_id):
        raise ValueError(
            f"--seen: {name!r} is the placeholder OF-Scraper gives a deleted account whose "
            "name it doesn't know, not a name the creator had. It never has a date."
        )
    if postgres:
        return pg_add_name(*postgres, model_id, name, when, force)
    db = pathlib.Path(data_dir) / str(model_id) / "user_data.db"
    if not db.exists():
        raise FileNotFoundError(f"no OF-Scraper database for account {model_id}: {db}")
    # closed without a commit, nothing is kept
    with contextlib.closing(sqlite3.connect(db)) as con:
        added = _add(
            lambda query, params: con.execute(query, params).rowcount,
            lambda: folder_name(con, model_id), _has_dates(con), model_id, name, when, force,
        )
        con.commit()
    return added


def _add(execute, folder, dated, model_id, name, when, force):
    """Add the name (and its date) with execute(query, params), which returns how many
    rows it wrote, and compare folder() before and after."""
    if when and not dated:
        raise ValueError(
            f"--seen: the database of account {model_id} doesn't keep dates yet. Run "
            "OF-Scraper on the creator once, or add the name without --seen."
        )
    before = folder()
    added = execute(ADD_NAME, (int(model_id), name))
    if when:
        execute(WIDEN_DATES, (when, when, when, when, int(model_id), name))
    after = folder()
    if before is not None and after != before and not force:
        raise FolderNameWouldChange(
            f"adding {name!r}{f' as seen {when}' if when else ''} would change the "
            f"folder name OF-Scraper uses for account {model_id} once it's deleted, "
            f"from {before!r} to {after!r}. Nothing was changed; pass --force to do "
            "it anyway."
        )
    return bool(added)


# --- PostgreSQL: the same, on a site's tables (rows: creator_rows.PostgresRows) ---


def _in_schema(rows, query):
    # the queries rewritten here name "profiles" only as the table
    return query.replace("profiles", f"{rows.schema}.profiles")


def _pg_dated(rows):
    return "last_seen_at" in rows.columns("profiles")


def pg_folder_name(rows):
    """folder_name, for a creator in PostgreSQL."""
    found = rows.query(
        _in_schema(rows, FOLDER_NAME if _pg_dated(rows) else FOLDER_NAME_UNDATED),
        (rows.model_id, *placeholder_names(rows.model_id)),
    )
    return found[0][0] if found else None


def _pg_account(rows):
    """A row of accounts(), for a creator in PostgreSQL."""
    names = rows.select(
        "profiles", ["username", *(SEEN if _pg_dated(rows) else ("NULL", "NULL"))]
    )
    media = rows.query(f"SELECT count(*) FROM {rows.schema}.medias WHERE model_id = ?", [rows.model_id])
    dates = [tuple(r[1:]) for r in names]
    return str(rows.model_id), [r[0] for r in names], media[0][0], pg_folder_name(rows), dates


def pg_accounts(creator_rows, database_url, site):
    """accounts(), for each creator PostgreSQL has rows for in the site's tables."""
    with creator_rows.in_postgres(database_url, [site]) as creators:
        return [_pg_account(rows) for rows in creators]


def pg_add_name(creator_rows, database_url, site, model_id, name, when, force):
    """add_name's change, in one transaction: closed without a commit, nothing is kept."""
    with creator_rows.in_postgres(database_url, [site], write=True) as creators:
        rows = next((r for r in creators if str(r.model_id) == str(model_id)), None)
        if rows is None:
            raise FileNotFoundError(f"PostgreSQL has no creator {model_id} in its {site} tables")
        added = _add(
            lambda query, params: rows.write(_in_schema(rows, query), params),
            lambda: pg_folder_name(rows), _pg_dated(rows), model_id, name, when, force,
        )
        rows.commit()
    return added


def select(data_dir, find=None, show_all=False, found=None):
    """The accounts to list: from the files in data_dir, or from `found` (pg_accounts)."""
    rows = []
    for row in accounts(data_dir) if found is None else found:
        names = row[1]
        if find is not None:
            if any(n.lower() == find.lower() for n in names):
                rows.append(row)
        elif show_all or len(names) > 1:
            rows.append(row)
    return rows


def _scraper(module):
    """A module of the scraper in the checkout this script is in (as
    scripts/reference/build_reference.py finds it). None for a copy of the script
    used somewhere else, which may have no scraper to ask."""
    root = str(pathlib.Path(__file__).resolve().parents[1])
    sys.path.insert(0, root)
    try:
        return importlib.import_module(module)
    except ImportError:
        return None
    finally:
        sys.path.remove(root)


def _shown(name, first, last):
    """A name as the listing prints it: followed by the days it was seen on, if any."""
    first, last = (str(date)[:10] if date else None for date in (first, last))
    if first and last:
        return f"{name} (seen {first if first == last else f'{first} to {last}'})"
    if last:
        return f"{name} (last seen {last})"
    if first:
        return f"{name} (first seen {first})"
    return name


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--data-dir", type=pathlib.Path)
    ap.add_argument("--postgres", action="store_true", help="use $OFSC_DATABASE_URL, not the files")
    ap.add_argument("--site", choices=SITES, help="with --postgres: the site (default: onlyfans)")
    ap.add_argument("--all", action="store_true", help="list every account")
    ap.add_argument("--find", metavar="NAME", help="accounts that ever used NAME")
    ap.add_argument("--add", nargs=2, metavar=("MODEL_ID", "NAME"), help="record a name")
    ap.add_argument(
        "--seen",
        metavar="DATE",
        help="with --add, when the name was in use: 2024-03-01 or 2024-03-01T09:30:00+00:00 "
        "(UTC unless it has an offset; no more than a day ahead)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="with --add, add the name even if it changes the deleted-account folder name",
    )
    ap.add_argument("--csv", type=pathlib.Path, help="also write the listing to a CSV file")
    args = ap.parse_args(argv)
    # Only this script's own environment says where PostgreSQL is
    database_url = os.environ.get("OFSC_DATABASE_URL", "").strip()
    creator_rows = _scraper("ofscraper.db.creator_rows") if args.postgres else None
    for wrong, said in (
        (args.postgres and args.data_dir is not None, "give --data-dir or --postgres, not both"),
        (args.site is not None and not args.postgres, "--site goes with --postgres"),
        (args.postgres and not database_url, "--postgres needs OFSC_DATABASE_URL set in the "
         "environment this is run in (an env file of the scraper's isn't read)"),
        (args.postgres and creator_rows is None, "--postgres needs the scraper this script "
         "is in: run it from the scraper's checkout, with the scraper installed"),
    ):
        if wrong:
            print(said, file=sys.stderr)
            return 1
    failed, postgres = (FileNotFoundError, ValueError, FolderNameWouldChange), None
    if creator_rows:
        failed += (creator_rows.postgres.PostgresUnavailable,)
        postgres = (creator_rows, database_url, args.site or SITES[0])
    elif (engine := _scraper("ofscraper.db.postgres")) is not None:
        # with PostgreSQL on, say that this works on the files, in the scraper's
        # sentence; a copy of the script without a scraper beside it says nothing
        engine.warn_sqlite_files("creator_names.py")
    data_dir = args.data_dir or DEFAULT_DATA_DIR

    if args.seen is not None and not args.add:
        print("--seen goes with --add MODEL_ID NAME", file=sys.stderr)
        return 1

    if args.add:
        model_id, name = args.add
        # what the driver and the server say comes with the password hidden already
        try:
            added = add_name(data_dir, model_id, name, args.force, args.seen, postgres)
        except failed as e:
            print(e, file=sys.stderr)
            return 1
        seen = f", seen {parse_seen(args.seen)}" if args.seen is not None else ""
        print(f"{'Added' if added else 'Already recorded'}: {name.strip()} -> {model_id}{seen}")
        return 0

    try:
        found = pg_accounts(*postgres) if postgres else None
    except failed as e:
        print(e, file=sys.stderr)
        return 1
    rows = select(data_dir, find=args.find, show_all=args.all, found=found)
    # Row order is the order names were recorded, not the order of the renames, so the
    # first recorded name is shown apart from the others rather than as a timeline.
    for model_id, names, media, folder, dates in rows:
        shown = [_shown(name, *seen) for name, seen in zip(names, dates)]
        others = f"   also known as: {', '.join(shown[1:])}" if len(shown) > 1 else ""
        print(
            f"{model_id:>10}  {media:>6} media  {shown[0] if shown else '?'}{others}"
            f"   folder if deleted: {folder or '?'}"
        )
    scope = "" if args.all or args.find else " with more than one name"
    print(f"\n{len(rows)} account(s){scope}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                [
                    "model_id",
                    "media",
                    "first_recorded_name",
                    "other_names",
                    "folder_if_deleted",
                    "first_seen",
                    "last_seen",
                ]
            )
            for model_id, names, media, folder, dates in rows:
                w.writerow(
                    [
                        model_id,
                        media,
                        names[0] if names else "",
                        " | ".join(names[1:]),
                        folder or "",
                        # one for each name, the first recorded name's first
                        " | ".join(str(first or "") for first, _ in dates),
                        " | ".join(str(last or "") for _, last in dates),
                    ]
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
