"""Move a creator's downloaded files to the folder of their current name, and
record the new folders in the database; preview unless --apply (#644).

After a creator changes username the scraper saves new files under the new
name, and the old files stay where they were. This puts them together. It
works on one creator's rows: a user_data.db, or with --postgres the rows of
the creator --creator names in the PostgreSQL database OFSC_DATABASE_URL
names (see MOVING_FILES.md). Close the scraper first.

Only the paths the database records are used, never the scraper's settings.

- The scraper writes a name into a folder path in small letters and cleans
  nothing out of it. So a recorded folder is cut at its separators, and each
  piece is compared, exactly, with the creator's recorded names.
- A folder is moved if exactly one piece is one of the creator's names, it
  isn't the name the files go to, and it is followed by one or two of the
  layout's own folders (`{responsetype}`, `{mediatype}`: Posts, Images).
  That piece becomes the new name, and nothing else in the path changes.
  No piece is a name: nothing to do. Two are, or the name is followed by
  something else (a folder above the library that has the same name), or
  the piece above it is the name's first letter ({first_letter}) and the
  new name has another: left and listed. `Posts` is not the creator
  `posts`: the layout's own folders start with a capital letter.
- With --apply each recorded file is handled on its own, by where it is:
      at the old place, new place free    moved (a rename), rows changed
      only at the new place               rows changed ("already there")
      at both places                      left and listed, rows unchanged
      at neither                          listed
  The row changes are saved together at the end. Then the old folders that
  were emptied are removed (rmdir, which can't remove a folder that holds
  anything).

There is no undo file. A run that stops part way is finished by running the
same command again: a file that is at its new place already only gets its
rows changed. To go back, run it with --to and the old name. Nothing here
deletes a file or loads the scraper, and a file is renamed only to a place
that was seen to be free just before. (Elsewhere than on Windows a rename
replaces a file that another program puts there in between: one more reason
to close the scraper.)
"""

import argparse
import datetime
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path

import ofscraper.db.creator_rows as creator_rows
import ofscraper.db.postgres as postgres
import ofscraper.sites as sites
from ofscraper.commands import recover_collisions as sibling

FILES_NOTICE = sibling.FILES_NOTICE.replace("recover_collisions", "move_creator_files")
# where the scraper is told what to call a deleted account whose name it
# doesn't know; read from this command's own environment
PLACEHOLDER_KEY = "OFSC_DELETED_MODEL_PLACEHOLDER"
EITHER = re.compile(r"([\\/]+)")
SEPARATORS = EITHER if os.name == "nt" else re.compile(r"(/+)")
# why a recorded file is left where it is
TAKEN = "something is already at the new place"
NOT_FOUND = "not at the old place, and not at the new one"
OTHER_SIZE = "not at the old place; the file at the new place doesn't have the size the row records"
TWICE = "more than one folder in its path is one of the creator's names"
LEFT = {
    "twice": TWICE,
    "layout": "the folder with the name isn't followed by one or two of the scraper's own folders (Posts, Images)",
    "letter": "the folder above the name is its first letter ({first_letter}), and the new name has another",
}
MEANWHILE = (
    "A row was changed by another program while this ran (is the scraper"
    " running?). No row was changed. Close the scraper and run this again."
)
AGAIN = (
    "Files moved before this stopped: {}. The database may not record their"
    " new folders yet. Run the same command again to finish."
)


class _FileRows(creator_rows.FileRows):
    """A user_data.db that, with `write`, can also be changed as PostgresRows
    can. It is then locked from the first read on, as recover_collisions
    locks it: a scraper that is writing to it stops the run before a file
    is moved."""

    # what names a row: a file made elsewhere may have no id column
    row_id = "rowid"

    def __init__(self, path, write=False):
        super().__init__(path)
        self._write = write

    def _connection(self):
        if self._conn is None and self._write:
            uri = self.path.resolve(strict=True).as_uri()
            self._conn = sqlite3.connect(f"{uri}?mode=rw", uri=True)
            self._conn.execute("BEGIN IMMEDIATE")
        return super()._connection()

    def change(self, table, row_id, was, to):
        # the file is locked, so the row still holds `was`
        query = f"UPDATE {table} SET {', '.join(f'{column} = ?' for column in to)} WHERE rowid = ?"
        return self._connection().execute(query, [*to.values(), row_id]).rowcount == 1

    def commit(self):
        self._connection().commit()


def _moment(saved):
    moment = datetime.datetime.fromisoformat(str(saved).strip())
    return moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)


def current_name(names, model_id, to=None):
    """The folder name the files go to, and why. `names` is each recorded
    name with its last_seen_at.

    It is --to if that is given, and a recorded name. Otherwise the name
    seen last. Where that would be a guess, this asks for --to: several
    names and no date, a date that can't be read, two names seen last at
    the same moment. The placeholder the scraper gives a deleted account is
    only chosen with --to."""
    placeholder = os.environ.get(PLACEHOLDER_KEY, "modeldeleted").lower()
    recorded = {str(name).lower() for name, _last in names}
    seen = {}
    for name, last in names:
        if str(name).lower() not in (placeholder, f"{placeholder}_{model_id}"):
            seen.setdefault(str(name).lower(), []).extend([] if last in (None, "") else [last])
    listed = ", ".join(sorted(recorded)) or "none"
    if to is not None:
        if to.strip().lower() not in recorded:
            raise ValueError(
                f"--to: {to} is not one of the names the database records for this"
                f" creator ({listed}). scripts/creator_names.py --add records a name"
                " in a user_data.db"
            )
        return to.strip().lower(), "given with --to"
    if len(seen) == 1:
        return next(iter(seen)), "the only name recorded"
    ask = f"Give --to NAME with the name the files should go to (recorded: {listed})"
    try:
        dated = {name: max(map(_moment, dates)) for name, dates in seen.items() if dates}
    except ValueError:
        raise ValueError(f"A date one of this creator's names was last seen at can't be read. {ask}") from None
    newest = max(dated.values(), default=None)
    last = [name for name, when in dated.items() if when == newest]
    if len(last) != 1:
        why = "more than one was seen last at the same moment" if last else "none has a date"
        raise ValueError(
            f"This creator has {len(seen)} names recorded and {why}, so it isn't"
            f" known which is the current one. {ask}"
        )
    return last[0], f"the name seen last ({newest.isoformat()})"


def _under(directory, names, target, separators):
    """Where a recorded folder names the creator: (what, the folder with the
    target name in that place, the folder up to and with the old name).
    `what` is "none", "target", a reason it is left (LEFT), or "former";
    only "former" comes with folders."""
    pieces = separators.split(directory)
    named = [place for place in range(0, len(pieces), 2) if pieces[place] in names]
    if len(named) != 1:
        return ("twice" if named else "none"), None, None
    place = named[0]
    if pieces[place] == target:
        return "target", None, None
    # the name's folder is the one {model_username} makes: below it come one
    # or two of the layout's own folders, which the scraper writes with
    # str.capitalize() (Posts, Images). Anything else may be a folder above
    # the library that only has the same name (a user's own folder)
    below = [piece for piece in pieces[place + 2 :: 2] if piece]
    if not 1 <= len(below) <= 2 or any(not piece[0].isupper() or piece != piece.capitalize() for piece in below):
        return "layout", None, None
    letter = pieces[place - 2] if place >= 2 else ""
    if letter == pieces[place][0].upper() and letter != target[0].upper():
        return "letter", None, None
    top = "".join(pieces[: place + 1])
    pieces[place] = target
    return "former", "".join(pieces), top


def _full(path, path_root):
    """A recorded path as a full one, as recover_collisions reads it."""
    path = Path(path)
    if not path.is_absolute():
        if sibling._from_another_system(path):
            raise ValueError(
                f"The recorded path {path} is a full path on another system"
                " than this one. Run this where the scraper runs, so that"
                " the files are where the database says"
            )
        if path_root is None:
            raise ValueError("Relative recorded paths require --path-root (the original working directory)")
        path = Path(path_root) / path
    return os.path.abspath(path)


def _remove_emptied(gone):
    """Remove the old folders the move left empty, up to the old name's own.
    rmdir can't remove a folder that still holds anything."""
    removed = []
    for old, top in gone:
        folder = os.path.dirname(old)
        while len(folder) >= len(top):
            try:
                os.rmdir(folder)
            except OSError:
                break
            removed.append(folder)
            folder = os.path.dirname(folder)
    return removed


def move(rows, model_id, apply=False, to=None, path_root=None):
    """Preview, or with `apply` carry out, the move for the creator `rows`
    holds the rows of (see the module's docstring). Returns the report."""
    names = []
    if "username" in rows.columns("profiles"):
        # a file made by an earlier version has no dates
        wanted = ["username", "last_seen_at"] if "last_seen_at" in rows.columns("profiles") else ["username"]
        names = [(row[0], row[1] if len(wanted) > 1 else None) for row in rows.select("profiles", wanted)]
    target, why = current_name(names, model_id, to)
    folders = {str(name).lower() for name, _last in names}
    media = []
    if {"directory", "filename", "size"} <= rows.columns("medias"):
        columns = [getattr(rows, "row_id", "id"), "directory", "filename", "size"]
        media = rows.select("medias", columns, "directory IS NOT NULL AND filename IS NOT NULL")
    left = []
    # each file once, with every row that records it
    files = {}
    for row_id, directory, filename, size in media:
        if not isinstance(directory, str) or not isinstance(filename, str):
            continue
        # a Windows path read elsewhere is cut as Windows cuts it, so that
        # one that names the creator is refused (_full) and not passed over
        foreign = os.name != "nt" and sibling._from_another_system(Path(directory))
        what, new_directory, top = _under(directory, folders, target, EITHER if foreign else SEPARATORS)
        if what in LEFT:
            left.append({"file": str(Path(directory, filename)), "why": LEFT[what]})
        if what != "former" or not filename:
            continue
        old, new = _full(Path(directory, filename), path_root), _full(Path(new_directory, filename), path_root)
        files.setdefault((old, new, _full(top, path_root)), []).append((row_id, directory, new_directory, size))

    result = {"creator": {"site": rows.site, "model_id": model_id}, "to": target, "why": why, "folders": [],
              "to_move": 0, "already_there": 0, "taken": 0, "not_found": 0, "left": left,
              "moved": 0, "rows_changed": 0, "folders_removed": [], "applied": apply}
    mapping = Counter()
    # the files that are no longer at their old places, each with the old
    # name's folder
    gone = []
    # the new places of the files handled so far: a preview moves nothing
    claimed = set()
    try:
        for (old, new, top), recorded in sorted(files.items()):
            there = os.path.lexists(new)
            if os.path.lexists(old):
                # the new place must be free: elsewhere than on Windows a
                # rename replaces the file that has the name
                if there or os.path.normcase(new) in claimed:
                    left.append({"file": old, "why": TAKEN})
                    continue
                claimed.add(os.path.normcase(new))
                mapping[os.path.dirname(old), os.path.dirname(new)] += 1
                result["to_move"] += 1
                if not apply:
                    continue
                try:
                    os.makedirs(os.path.dirname(new), exist_ok=True)
                    os.rename(old, new)
                except OSError as error:
                    # another disk, a folder that can't be written to
                    left.append({"file": old, "why": f"it could not be moved ({error.strerror or error})"})
                    continue
                result["moved"] += 1
            elif not there or os.path.normcase(new) in claimed:
                # a file this run moved or took there is another row's
                left.append({"file": old, "why": NOT_FOUND})
                continue
            elif {size for *_row, size in recorded if size is not None} - {os.lstat(new).st_size}:
                left.append({"file": old, "why": OTHER_SIZE, "new_place": new})
                continue
            else:
                claimed.add(os.path.normcase(new))
                result["already_there"] += 1
            if not apply:
                continue
            gone.append((old, top))
            for row_id, directory, new_directory, _size in recorded:
                if not rows.change("medias", row_id, {"directory": directory}, {"directory": new_directory}):
                    raise postgres.ChangedMeanwhile(MEANWHILE)
                result["rows_changed"] += 1
        if apply:
            rows.commit()
    except BaseException:
        if result["moved"]:
            print(AGAIN.format(result["moved"]), file=sys.stderr)
        raise
    result["folders"] = [{"from": old, "to": new, "files": count} for (old, new), count in sorted(mapping.items())]
    result["taken"] = sum(file["why"] == TAKEN for file in left)
    result["not_found"] = sum(file["why"] == NOT_FOUND for file in left)
    result["folders_removed"] = _remove_emptied(gone)
    return result


def on_file(database, apply=False, to=None, path_root=None):
    """The move for the creator a user_data.db holds the rows of. A file
    that holds the media or the names of more than one is refused: every
    name in it would be taken for one creator's."""
    with closing(_FileRows(database, write=apply)) as rows:
        ids = set()
        for table, column in (("medias", "model_id"), ("profiles", "user_id")):
            if column in rows.columns(table):
                ids |= {row[0] for row in rows.select(table, [f"DISTINCT {column}"])} - {None}
        if len(ids) > 1:
            raise ValueError(
                "This user_data.db holds the rows of more than one creator"
                f" ({', '.join(sorted(map(str, ids)))}), so it isn't known whose files to move"
            )
        return move(rows, ids.pop() if ids else None, apply=apply, to=to, path_root=path_root)


def on_postgres(database_url, creator, site=None, apply=False, to=None, path_root=None):
    """The move for the one creator this names, found as recover_collisions
    finds one. Without --apply the connection is read-only."""
    wanted_sites = [site] if site else list(sites.SITES)
    try:
        with creator_rows.in_postgres(database_url, wanted_sites, [creator], write=apply) as found:
            if len(found) != 1:
                raise ValueError(
                    f"PostgreSQL has more than one creator named {creator}:"
                    f" {', '.join(sibling._goes_by(rows) for rows in found)}."
                    " Give --site, or a username or id that only one of them has"
                )
            return move(found[0], found[0].model_id, apply=apply, to=to, path_root=path_root)
    except creator_rows.NotFound:
        # the name as it was typed (in_postgres has it in small letters)
        raise creator_rows.NotFound(
            f"PostgreSQL has no creator named {creator} (looked in: {', '.join(wanted_sites)})"
        ) from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("database", type=Path, nargs="?", help="One creator's user_data.db")
    parser.add_argument("--apply", action="store_true", help="Move the files and change the rows; without it, only report")
    parser.add_argument("--to", metavar="NAME", help="The recorded name whose folder the files go to (default: the name seen last)")
    parser.add_argument("--path-root", type=Path, help="Original working directory for relative recorded paths")
    parser.add_argument("--postgres", action="store_true", help=f"Work on the PostgreSQL database ${postgres.URL_KEY} names instead of a user_data.db; give --creator and no database with it")
    parser.add_argument("--site", choices=list(sites.SITES), help="With --postgres, the creator's site (default: the site that has the creator)")
    parser.add_argument("--creator", metavar="NAME", help="With --postgres, the one creator to work on, by a username or id that no other creator has")
    args = parser.parse_args(argv)

    # Only this command's own environment says where PostgreSQL is: the
    # scraper's settings and env files aren't read
    database_url = os.environ.get(postgres.URL_KEY, "").strip()
    if args.postgres:
        if args.database:
            parser.error("give a user_data.db or --postgres, not both")
        if not database_url:
            parser.error(
                f"--postgres needs {postgres.URL_KEY} set in the environment this is run in"
                " (an env file of the scraper's isn't read); see POSTGRESQL.md"
            )
        if not args.creator:
            parser.error("--postgres needs --creator: the one creator to work on, by username or id")
    elif args.site is not None or args.creator is not None:
        parser.error("--site and --creator go with --postgres; with a file, give that creator's user_data.db")
    elif not args.database:
        parser.error("the following arguments are required: database, or --postgres")
    elif database_url:
        print(f"warning: {FILES_NOTICE}", file=sys.stderr)

    try:
        if args.postgres:
            result = on_postgres(database_url, args.creator, site=args.site, apply=args.apply, to=args.to, path_root=args.path_root)
        else:
            result = on_file(args.database, apply=args.apply, to=args.to, path_root=args.path_root)
    except KeyboardInterrupt:
        parser.exit(130, "Move stopped.\n")
    except postgres.Unconfirmed as error:
        parser.exit(130 if error.interrupted else 1, f"Move failed: {error}\n")
    except (OSError, sqlite3.Error, ValueError, creator_rows.NotFound, postgres.PostgresUnavailable) as error:
        parser.exit(1, f"Move failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
