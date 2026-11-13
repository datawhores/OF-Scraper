r"""List and record the usernames each creator account has had.

OF-Scraper keeps one database per account ({data_dir}/{model_id}/user_data.db). Its
`profiles` table holds one row per (account, username) pair, and OF-Scraper adds a row
whenever it processes a creator under a name it hasn't seen, so a renamed creator ends up
with several rows. This script reads that history back and can record a name you learned
elsewhere (e.g. from an older download tool).

    python scripts/creator_names.py                      # accounts with more than one name
    python scripts/creator_names.py --all                # every account and its names
    python scripts/creator_names.py --find NAME          # account(s) that ever used NAME
    python scripts/creator_names.py --add MODEL_ID NAME  # record another name
    python scripts/creator_names.py --csv names.csv      # also write the listing to CSV

The default data directory is the default `metadata` location for the main profile,
{home_directory}/.config/ofscraper/main_profile/.data; use --data-dir if yours differs.

For a deleted account, OF-Scraper names the folder after the first row of
`SELECT username FROM profiles WHERE user_id = ?`. That query has no ORDER BY, so SQLite
returns the names in index order (alphabetical), not the order they were recorded. The
listing shows that name as "folder if deleted".

--add only appends a row and ignores duplicates. It refuses a name that would change the
folder name OF-Scraper uses for a deleted account, unless you pass --force. Close
OF-Scraper before using --add.

OnlyFans only: Fansly databases ({model_id}/fansly/user_data.db) aren't read.
"""

import argparse
import contextlib
import csv
import pathlib
import sqlite3
import sys

DEFAULT_DATA_DIR = pathlib.Path.home() / ".config" / "ofscraper" / "main_profile" / ".data"


class FolderNameWouldChange(Exception):
    """--add would change the folder name OF-Scraper uses for a deleted account."""


def _connect_ro(db):
    return sqlite3.connect(pathlib.Path(db).resolve().as_uri() + "?mode=ro", uri=True)


def folder_name(con, model_id):
    """The name OF-Scraper uses for a deleted account's folder: the first row of the
    same query it runs (ofscraper/db/operations_/profile.py, get_profile_info)."""
    row = con.execute(
        "SELECT username FROM profiles where user_id=(?)", (int(model_id),)
    ).fetchone()
    return row[0] if row else None


def accounts(data_dir):
    """Yield (model_id, names in the order they were recorded, media count, folder name
    if deleted) per account."""
    for db in sorted(pathlib.Path(data_dir).glob("*/user_data.db")):
        model_id = db.parent.name
        with contextlib.closing(_connect_ro(db)) as con:
            try:
                names = [r[0] for r in con.execute("SELECT username FROM profiles ORDER BY id")]
                media = con.execute("SELECT count(*) FROM medias").fetchone()[0]
                folder = folder_name(con, model_id) if model_id.isdigit() else None
            except sqlite3.OperationalError:
                continue
        yield model_id, names, media, folder


def add_name(data_dir, model_id, name, force=False):
    """Record `name` for `model_id`. Returns True if a row was added, False if it existed.

    Raises FolderNameWouldChange, without adding the row, if the new name would become
    the folder name OF-Scraper uses for the account once it's deleted, unless `force`."""
    if not str(model_id).isdigit():
        raise ValueError(f"MODEL_ID must be a number, got {model_id!r}")
    name = name.strip()
    if not name:
        raise ValueError("NAME can't be empty")
    db = pathlib.Path(data_dir) / str(model_id) / "user_data.db"
    if not db.exists():
        raise FileNotFoundError(f"no OF-Scraper database for account {model_id}: {db}")
    with contextlib.closing(sqlite3.connect(db)) as con:
        before = folder_name(con, model_id)
        added = con.execute(
            "INSERT OR IGNORE INTO profiles (user_id, username) VALUES (?, ?)",
            (int(model_id), name),
        ).rowcount
        after = folder_name(con, model_id)
        if before is not None and after != before and not force:
            con.rollback()
            raise FolderNameWouldChange(
                f"adding {name!r} would change the folder name OF-Scraper uses for "
                f"account {model_id} once it's deleted, from {before!r} to {after!r}. "
                "Nothing was added; pass --force to add it anyway."
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


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--data-dir", type=pathlib.Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--all", action="store_true", help="list every account")
    ap.add_argument("--find", metavar="NAME", help="accounts that ever used NAME")
    ap.add_argument("--add", nargs=2, metavar=("MODEL_ID", "NAME"), help="record a name")
    ap.add_argument(
        "--force",
        action="store_true",
        help="with --add, add the name even if it changes the deleted-account folder name",
    )
    ap.add_argument("--csv", type=pathlib.Path, help="also write the listing to a CSV file")
    args = ap.parse_args(argv)

    if args.add:
        model_id, name = args.add
        try:
            added = add_name(args.data_dir, model_id, name, force=args.force)
        except (FileNotFoundError, ValueError, FolderNameWouldChange) as e:
            print(e, file=sys.stderr)
            return 1
        print(f"{'Added' if added else 'Already recorded'}: {name.strip()} -> {model_id}")
        return 0

    rows = select(args.data_dir, find=args.find, show_all=args.all)
    # Row order is the order names were recorded, not the order of the renames, so the
    # first recorded name is shown apart from the others rather than as a timeline.
    for model_id, names, media, folder in rows:
        others = f"   also known as: {', '.join(names[1:])}" if len(names) > 1 else ""
        print(
            f"{model_id:>10}  {media:>6} media  {names[0] if names else '?'}{others}"
            f"   folder if deleted: {folder or '?'}"
        )
    scope = "" if args.all or args.find else " with more than one name"
    print(f"\n{len(rows)} account(s){scope}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                ["model_id", "media", "first_recorded_name", "other_names", "folder_if_deleted"]
            )
            for model_id, names, media, folder in rows:
                w.writerow(
                    [
                        model_id,
                        media,
                        names[0] if names else "",
                        " | ".join(names[1:]),
                        folder or "",
                    ]
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
