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

OnlyFans only: Fansly databases ({model_id}/fansly/user_data.db) aren't read.
"""

import argparse
import contextlib
import csv
import datetime
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


def add_name(data_dir, model_id, name, force=False, seen=None):
    """Record `name` for `model_id`, seen at `seen` if that is given (see parse_seen).
    Returns True if a row was added, False if it existed.

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
    db = pathlib.Path(data_dir) / str(model_id) / "user_data.db"
    if not db.exists():
        raise FileNotFoundError(f"no OF-Scraper database for account {model_id}: {db}")
    with contextlib.closing(sqlite3.connect(db)) as con:
        if when and not _has_dates(con):
            raise ValueError(
                f"--seen: the database of account {model_id} doesn't keep dates yet. Run "
                "OF-Scraper on the creator once, or add the name without --seen."
            )
        before = folder_name(con, model_id)
        added = con.execute(
            "INSERT OR IGNORE INTO profiles (user_id, username) VALUES (?, ?)",
            (int(model_id), name),
        ).rowcount
        if when:
            con.execute(WIDEN_DATES, (when, when, when, when, int(model_id), name))
        after = folder_name(con, model_id)
        if before is not None and after != before and not force:
            con.rollback()
            raise FolderNameWouldChange(
                f"adding {name!r}{f' as seen {when}' if when else ''} would change the "
                f"folder name OF-Scraper uses for account {model_id} once it's deleted, "
                f"from {before!r} to {after!r}. Nothing was changed; pass --force to do "
                "it anyway."
            )
        con.commit()
    return bool(added)


def select(data_dir, find=None, show_all=False):
    rows = []
    for row in accounts(data_dir):
        names = row[1]
        if find is not None:
            if any(n.lower() == find.lower() for n in names):
                rows.append(row)
        elif show_all or len(names) > 1:
            rows.append(row)
    return rows


def _warn_on_postgres():
    """With PostgreSQL on, say that this script works on the user_data.db
    files. The sentence is the scraper's, from the checkout this script is in
    (as scripts/reference/build_reference.py finds it). A copy of the script
    used somewhere else may have no scraper to ask, and then says nothing."""
    root = str(pathlib.Path(__file__).resolve().parents[1])
    sys.path.insert(0, root)
    try:
        from ofscraper.db.postgres import warn_sqlite_files
    except ImportError:
        return
    finally:
        sys.path.remove(root)
    warn_sqlite_files("creator_names.py")


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
    ap.add_argument("--data-dir", type=pathlib.Path, default=DEFAULT_DATA_DIR)
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
    _warn_on_postgres()

    if args.seen is not None and not args.add:
        print("--seen goes with --add MODEL_ID NAME", file=sys.stderr)
        return 1

    if args.add:
        model_id, name = args.add
        try:
            added = add_name(args.data_dir, model_id, name, force=args.force, seen=args.seen)
        except (FileNotFoundError, ValueError, FolderNameWouldChange) as e:
            print(e, file=sys.stderr)
            return 1
        seen = f", seen {parse_seen(args.seen)}" if args.seen is not None else ""
        print(f"{'Added' if added else 'Already recorded'}: {name.strip()} -> {model_id}{seen}")
        return 0

    rows = select(args.data_dir, find=args.find, show_all=args.all)
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
