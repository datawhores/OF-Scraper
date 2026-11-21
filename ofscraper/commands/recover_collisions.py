"""Offline recovery of ambiguous shared download paths; preview unless --apply.

It works on one creator's rows: a user_data.db, or with --postgres the rows
of the creator --creator names in the PostgreSQL database OFSC_DATABASE_URL
names (see COLLISION_RECOVERY.md and POSTGRESQL.md).
"""

import argparse
import json
import os
from pathlib import Path, PureWindowsPath
import sqlite3
import stat
import sys
import tempfile
import uuid
from collections import defaultdict
from contextlib import closing

import ofscraper.db.creator_rows as creator_rows
import ofscraper.db.postgres as postgres
import ofscraper.sites as sites

# said when the command is given a file while PostgreSQL is on (#631)
FILES_NOTICE = (
    f"PostgreSQL is on ({postgres.URL_KEY} is set), but recover_collisions works"
    " on the user_data.db file it was given, not PostgreSQL. The file holds"
    " nothing scraped since PostgreSQL was turned on, and what is changed in it"
    " does not reach PostgreSQL. To work on PostgreSQL, give --postgres and"
    " --creator in place of the file. See POSTGRESQL.md."
)
# an undo file written from PostgreSQL says so
POSTGRESQL = "postgresql"
# what is read of each media row in PostgreSQL. A row is named by its media
# and post; a download writes the last four together with the flag
MEDIA = ["id", "media_id", "post_id", "downloaded", "directory", "filename", "size", "hash"]
MEANWHILE = (
    "A row was changed by another program while this ran (is the scraper"
    " running?). Nothing was changed. Close the scraper and run this again."
)


def find_collisions(conn, path_root=None):
    """Group distinct media by their recorded path or existing file identity."""
    rows = conn.execute(
        "SELECT model_id, media_id, directory, filename, downloaded FROM medias "
        "WHERE media_id IS NOT NULL AND filename IS NOT NULL AND filename != ''"
    )
    return collisions(rows, path_root)


def collisions(rows, path_root=None, written_here=False):
    """find_collisions for rows that were read already: (model_id, media_id,
    directory, filename, downloaded). With `written_here`, a path that is a
    full path only on another system is refused."""
    groups = defaultdict(list)
    for model, media, directory, filename, downloaded in rows:
        path = Path(directory or "", filename)
        if not path.is_absolute():
            if written_here and _from_another_system(path):
                raise ValueError(
                    f"The recorded path {path} is a full path on another system"
                    " than this one. Run this where the scraper runs, so that"
                    " the files are where the database says"
                )
            if path_root is None:
                raise ValueError("Relative recorded paths require --path-root (the original working directory)")
            path = Path(path_root) / path
        path = Path(os.path.abspath(path))
        try:
            info = path.stat()
        except FileNotFoundError:
            # Preserve case when there is no file to establish filesystem identity.
            key = ("path", str(path))
        else:
            if not stat.S_ISREG(info.st_mode):
                continue
            key = ("file", info.st_dev, info.st_ino) if info.st_ino else ("path", str(path))
        groups[key].append((model, media, str(path), downloaded))
    return [
        rows for rows in groups.values()
        if len({(r[0], r[1]) for r in rows}) > 1
    ]


def _from_another_system(path):
    """Whether a path that isn't a full path here is one elsewhere: C:\\...
    read on Linux, or /... read on Windows. --path-root is not for those."""
    if os.name == "nt":
        return bool(path.root)
    return PureWindowsPath(str(path)).is_absolute()


def report(groups, media_to_mark, apply):
    return {
        "groups": [
            {"paths": sorted({r[2] for r in group}),
             "media": [{"model_id": model, "media_id": media}
                       for model, media in sorted(
                           {(r[0], r[1]) for r in group}, key=str)]}
            for group in groups
        ],
        "media_to_mark": media_to_mark,
        "rows_marked": 0,
        "undo_file": None,
        "applied": apply,
    }


def recover(database, apply=False, path_root=None):
    """Record changed rows in an undo file, then reset their download flags."""
    database = Path(database).resolve(strict=True)
    uri = database.as_uri()
    mode = "rw" if apply else "ro"
    with closing(sqlite3.connect(f"{uri}?mode={mode}", uri=True)) as conn:
        conn.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
        undo_file = None
        undo_created = False
        try:
            groups = find_collisions(conn, path_root)
            owners = {(r[0], r[1]) for group in groups for r in group}
            pending = [
                owner for owner in owners
                if conn.execute(
                    "SELECT 1 FROM medias WHERE model_id IS ? AND media_id = ? "
                    "AND downloaded = 1 LIMIT 1", owner
                ).fetchone()
            ]
            result = report(groups, len(pending), apply)
            if apply and pending:
                changed_rows = []
                for owner in pending:
                    changed_rows.extend(conn.execute(
                        "SELECT id, model_id, media_id, post_id, downloaded FROM medias "
                        "WHERE model_id IS ? AND media_id = ? AND downloaded = 1", owner
                    ).fetchall())
                undo_file = database.with_name(
                    f"{database.name}.collision-undo-{uuid.uuid4().hex}.json"
                )
                # Persist the small undo record before committing any flag changes.
                with undo_file.open("x", encoding="utf-8") as output:
                    undo_created = True
                    json.dump({"version": 1, "database": str(database),
                               "rows": sorted(changed_rows)}, output)
                    output.flush()
                    os.fsync(output.fileno())
                result["undo_file"] = str(undo_file)
                for owner in pending:
                    result["rows_marked"] += conn.execute(
                        "UPDATE medias SET downloaded = 0 "
                        "WHERE model_id IS ? AND media_id = ? AND downloaded = 1",
                        owner,
                    ).rowcount
            conn.commit()
            return result
        except BaseException:
            conn.rollback()
            if undo_created:
                undo_file.unlink(missing_ok=True)
            raise


def undo(database, undo_file, apply=False):
    """Restore recorded flags only for matching rows that are still pending."""
    database = Path(database).resolve(strict=True)
    record = json.loads(Path(undo_file).read_text(encoding="utf-8"))
    if isinstance(record, dict) and record.get("source") == POSTGRESQL:
        raise ValueError(
            "Undo file was written from PostgreSQL, not a user_data.db: give"
            " --postgres and --creator in place of the database"
        )
    if record.get("version") != 1 or record.get("database") != str(database):
        raise ValueError("Undo file does not belong to this database")
    rows = record.get("rows")
    if not isinstance(rows, list) or any(
        not isinstance(row, list) or len(row) != 5 or row[4] != 1 for row in rows
    ):
        raise ValueError("Invalid undo rows")
    mode = "rw" if apply else "ro"
    with closing(sqlite3.connect(f"{database.as_uri()}?mode={mode}", uri=True)) as conn:
        with conn:
            conn.execute("BEGIN IMMEDIATE" if apply else "BEGIN")
            count = 0
            for row_id, model, media, post, previous in rows:
                params = (row_id, model, media, post)
                condition = "id = ? AND model_id IS ? AND media_id = ? AND post_id = ? AND downloaded = 0"
                if apply:
                    count += conn.execute(
                        f"UPDATE medias SET downloaded = ? WHERE {condition}",
                        (previous, *params),
                    ).rowcount
                else:
                    count += conn.execute(
                        f"SELECT COUNT(*) FROM medias WHERE {condition}", params
                    ).fetchone()[0]
            return {"applied": apply, "rows_to_restore": count}


# --- PostgreSQL ---
# One creator's rows of one site, out of tables every creator shares (see
# creator_rows). What is found and changed is what a file with the same rows
# gives. The differences are in how it is done:
#
# - A row is changed through its creator's rows only, and only while it still
#   holds what was read from it. Reads and changes are one transaction.
# - Nothing locks the scraper out, as SQLite's lock on a file does. If the
#   scraper changes one of the rows meanwhile, nothing is changed here.
# - The undo file names a row by its media and post, not by its id: a row's
#   id is not the one it had in a file, and changes if the rows are brought
#   in again. PostgreSQL keeps one row per creator, media and post.


def recover_postgres(rows, apply=False, path_root=None, undo_dir=None, database=None):
    """recover for a creator's rows in PostgreSQL, which are open for changes
    when applying. The undo file goes to `undo_dir`, and says that it was
    made on `database` (the server and database, without the login)."""
    media = [tuple(row) for row in rows.select("medias", MEDIA, "media_id IS NOT NULL")]
    groups = collisions(
        (
            (rows.model_id, media_id, directory, filename, downloaded)
            for _id, media_id, _post, downloaded, directory, filename, _size, _hash in media
            if filename is not None and filename != ""
        ),
        path_root,
        written_here=True,
    )
    owners = {r[1] for group in groups for r in group}
    # every downloaded row of those media, as with a file: their other posts' too
    marking = [row for row in media if row[1] in owners and row[3] == 1]
    result = report(groups, len({row[1] for row in marking}), apply)
    result["creator"] = _creator(rows)
    if not (apply and marking):
        return result
    if undo_dir is None:
        raise ValueError("A folder for the undo file is needed to apply")
    undo_file = Path(undo_dir).resolve() / (
        f"postgresql-{rows.site}-{rows.model_id}.collision-undo-{uuid.uuid4().hex}.json"
    )
    record = {"version": 2, "source": POSTGRESQL, "site": rows.site, "model_id": rows.model_id}
    if database:
        record["database"] = database
    record["rows"] = [dict(zip(MEDIA[1:], row[1:])) for row in marking]
    undo_created = False
    try:
        # Persist the small undo record before any flag is changed. "x": a
        # file that is there already is another run's, and is never replaced.
        with undo_file.open("x", encoding="utf-8") as output:
            undo_created = True
            json.dump(record, output)
            output.flush()
            os.fsync(output.fileno())
        for row in marking:
            if not rows.change("medias", row[0], dict(zip(MEDIA[3:], row[3:])), {"downloaded": 0}):
                raise postgres.ChangedMeanwhile(MEANWHILE)
    except BaseException as error:
        # nothing was kept, so the undo file is of no use
        if undo_created:
            _remove_unused(undo_file, error)
        raise
    # From here on the undo file is never removed. Once the server is asked
    # to keep the changes, only it knows whether it did, whatever happens to
    # this program meanwhile: the undo file is the only way back.
    try:
        rows.commit()
    except BaseException as error:
        raise _unconfirmed(
            error,
            f"The undo file is kept: {undo_file}. Run this with --undo and that"
            " file, without --apply, to see whether the changes arrived.",
        ) from error
    result["undo_file"] = str(undo_file)
    result["rows_marked"] = len(marking)
    return result


def _remove_unused(undo_file, error):
    """Remove the undo file of changes that were not kept, after `error`. If
    it can't be removed, what went wrong first stays what is said, with the
    file that is left."""
    try:
        undo_file.unlink(missing_ok=True)
    except OSError as left:
        if not isinstance(error, Exception):
            # an interrupt goes on as it is
            return
        said = str(error)
        if "Nothing was changed" not in said:
            said = f"{said.rstrip('.')}. Nothing was changed."
        raise ValueError(
            f"{said} The undo file {undo_file} could not be removed"
            f" ({left.strerror or left}): nothing needs it, and it is safe to"
            " delete."
        ) from error


def _unconfirmed(error, then):
    """What stopped a commit that had begun, as the sentence to end on: it
    isn't known whether the changes were kept, and `then` says what to do."""
    unconfirmed = postgres.Unconfirmed(
        f"{error} {then}"
        if isinstance(error, postgres.Unconfirmed)
        else "This was stopped while the changes were being saved to PostgreSQL,"
        f" so it isn't known whether they were. {then}"
    )
    unconfirmed.interrupted = (
        error.interrupted
        if isinstance(error, postgres.Unconfirmed)
        else isinstance(error, KeyboardInterrupt)
    )
    return unconfirmed


def undo_postgres(rows, undo_file, apply=False, database=None):
    """undo for a creator's rows in PostgreSQL. All of the recorded rows are
    restored or none: a row that is no longer as the recovery left it (or as
    it was before) stops it. `database` is where the rows are, to compare
    with where the undo file says it was made."""
    record = json.loads(Path(undo_file).read_text(encoding="utf-8"))
    if not isinstance(record, dict):
        raise ValueError("Invalid undo file")
    if record.get("source") != POSTGRESQL:
        raise ValueError(
            "Undo file was written for a user_data.db, not PostgreSQL: give"
            " that file in place of --postgres"
        )
    if record.get("version") != 2:
        raise ValueError("Undo file was written by a version of this command that this one doesn't know")
    # the id as text: a file written by hand may have it in quotes
    if (record.get("site"), str(record.get("model_id"))) != (rows.site, str(rows.model_id)):
        raise ValueError(
            f"Undo file is for {record.get('site')} creator {record.get('model_id')},"
            f" not {rows.site} creator {rows.model_id}"
        )
    wanted = record.get("rows")
    if not isinstance(wanted, list) or any(not _undo_row(row) for row in wanted):
        raise ValueError("Invalid undo rows")
    # by the ids' text, which is what PostgreSQL keeps: 12 and "12" are one row
    named = [(str(row["media_id"]), str(row["post_id"])) for row in wanted]
    twice = sorted({name for name in named if named.count(name) > 1})
    if twice:
        raise ValueError(
            f"Undo file lists a row twice (media {twice[0][0]}, post {twice[0][1]}):"
            " it isn't one this command wrote. Nothing was restored"
        )
    current = {
        (str(row[1]), str(row[2])): tuple(row)
        for row in rows.select("medias", MEDIA, "media_id IS NOT NULL")
    }
    restoring = []
    changed = 0
    for row, name in zip(wanted, named):
        found = current.get(name)
        left = [row[column] for column in MEDIA[4:]]
        if found is None or list(found[4:]) != left or found[3] not in (0, 1):
            changed += 1
        elif found[3] == 0:
            restoring.append(found)
        # else it is downloaded again, with the file it had: nothing to restore
    if changed:
        made_on = record.get("database")
        # a hint only: the same database can go by another address
        elsewhere = (
            f": the undo file was made on {made_on}, this is {database}"
            if isinstance(made_on, str) and database and made_on != database
            else ""
        )
        raise ValueError(
            f"{changed} of the undo file's {len(wanted)} rows are no longer as"
            " the recovery left them (media downloaded again since, or"
            f" another database{elsewhere}). Nothing was restored"
        )
    result = {"applied": apply, "rows_to_restore": len(restoring), "creator": _creator(rows)}
    if apply:
        for found in restoring:
            if not rows.change("medias", found[0], dict(zip(MEDIA[3:], found[3:])), {"downloaded": 1}):
                raise postgres.ChangedMeanwhile(MEANWHILE)
        try:
            rows.commit()
        except BaseException as error:
            raise _unconfirmed(
                error,
                "Run the same --undo again, without --apply: it shows what is"
                " left to restore.",
            ) from error
    return result


def _undo_row(row):
    def an_id(value):
        return isinstance(value, (int, str)) and not isinstance(value, bool)

    return (
        isinstance(row, dict)
        and set(row) == set(MEDIA[1:])
        and an_id(row["media_id"])
        and an_id(row["post_id"])
        and row["downloaded"] == 1
    )


def _goes_by(rows):
    """A creator for a refusal: the site, the id and every username it has had."""
    names = []
    if "username" in rows.columns("profiles"):
        names = sorted({str(row[0]) for row in rows.select("profiles", ["username"])})
    return f"{rows.site} {rows.model_id}" + (f" ({', '.join(names)})" if names else "")


def _creator(rows):
    """Who a name turned out to be, for the report: the site, the id and the
    username saved last (as stash_sync takes it)."""
    names = []
    if {"username", "id"} <= rows.columns("profiles"):
        names = rows.select("profiles", ["username", "id"])
    username = max(names, key=lambda row: row[1])[0] if names else None
    return {"site": rows.site, "model_id": rows.model_id, "username": username}


def _undo_folder(folder):
    """The folder for the undo file, as a full path, having seen that a file
    can be made in it: a preview finds that out, not the apply after it."""
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError(f"The undo folder {folder} isn't there, or isn't a folder")
    try:
        # made and removed at once
        with tempfile.TemporaryFile(dir=folder):
            pass
    except OSError as error:
        raise ValueError(
            f"The undo folder {folder} can't be written to ({error.strerror or error})"
        ) from error
    return folder


def on_postgres(database_url, creator, site=None, undo_file=None, apply=False, path_root=None, undo_dir=None):
    """Recover, or undo, for the one creator this names. Without --apply the
    connection is read-only."""
    if undo_dir is not None:
        undo_dir = _undo_folder(undo_dir)
    elif apply and undo_file is None:
        raise ValueError("A folder for the undo file is needed to apply")
    wanted_sites = [site] if site else list(sites.SITES)
    # the server and database, without the login; nothing if the address
    # isn't one that can be read that way
    database = postgres.describe(database_url)
    if database == postgres.describe(""):
        database = None
    try:
        with creator_rows.in_postgres(database_url, wanted_sites, [creator], write=apply) as found:
            if len(found) != 1:
                # an id both sites have, an id that is another creator's
                # username, or a username two creators have had
                raise ValueError(
                    f"PostgreSQL has more than one creator named {creator}:"
                    f" {', '.join(_goes_by(rows) for rows in found)}."
                    " Give --site, or a username or id that only one of them has"
                )
            if undo_file is not None:
                return undo_postgres(found[0], undo_file, apply=apply, database=database)
            return recover_postgres(
                found[0], apply=apply, path_root=path_root, undo_dir=undo_dir, database=database
            )
    except creator_rows.NotFound:
        # the name as it was typed (in_postgres has it in small letters)
        raise creator_rows.NotFound(
            f"PostgreSQL has no creator named {creator} (looked in: {', '.join(wanted_sites)})"
        ) from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, nargs="?", help="One model's user_data.db")
    parser.add_argument("--apply", action="store_true", help="Apply the previewed recovery or undo operation")
    parser.add_argument("--undo", help="Preview restoring flags from a recovery undo file")
    parser.add_argument("--path-root", type=Path, help="Original working directory for relative recorded paths")
    parser.add_argument("--postgres", action="store_true", help=f"Work on the PostgreSQL database ${postgres.URL_KEY} names instead of a user_data.db; give --creator and no database with it")
    parser.add_argument("--site", choices=list(sites.SITES), help="With --postgres, the creator's site (default: the site that has the creator)")
    parser.add_argument("--creator", metavar="NAME", help="With --postgres, the one creator to work on, by a username or id that no other creator has")
    parser.add_argument("--undo-dir", metavar="DIR", help="With --postgres, the folder --apply writes the undo file to: needed with --apply, and it must be a folder that is kept (in Docker, a mounted one)")
    args = parser.parse_args(argv)
    # as a path, as before: an empty one is the current folder
    undo_file = None if args.undo is None else Path(args.undo)

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
        # a path that is empty (a shell variable that isn't set) would be
        # the current folder
        if args.undo is not None and not args.undo.strip():
            parser.error("--undo needs the path of an undo file")
        if args.undo_dir is not None and not args.undo_dir.strip():
            parser.error("--undo-dir needs the path of a folder")
        if args.undo is not None and args.undo_dir is not None:
            parser.error("--undo-dir is where --apply writes a new undo file; it doesn't go with --undo")
        if args.apply and args.undo is None and args.undo_dir is None:
            parser.error(
                "--postgres --apply needs --undo-dir: the folder for the undo file, which is"
                " the only way back. Give a folder that is kept (in Docker a mounted one,"
                " not one inside the container)"
            )
    elif args.site is not None or args.creator is not None or args.undo_dir is not None:
        parser.error("--site, --creator and --undo-dir go with --postgres; with a file, give that creator's user_data.db")
    elif not args.database:
        parser.error("the following arguments are required: database, or --postgres")
    elif database_url:
        print(f"warning: {FILES_NOTICE}", file=sys.stderr)

    # What the driver and the server say reaches here with the address's
    # password hidden already (see postgres.py). The command's own sentences
    # are said as they are: a folder, a name or an option may hold the same
    # letters as a password.
    try:
        if args.postgres:
            result = on_postgres(
                database_url, args.creator, site=args.site, undo_file=undo_file,
                apply=args.apply, path_root=args.path_root, undo_dir=args.undo_dir,
            )
        else:
            result = (undo(args.database, undo_file, apply=args.apply) if undo_file is not None
                      else recover(args.database, apply=args.apply, path_root=args.path_root))
    except postgres.Unconfirmed as error:
        # stopped from the keyboard: the sentence, then the exit Ctrl-C gives
        parser.exit(130 if error.interrupted else 1, f"Recovery failed: {error}\n")
    except (OSError, sqlite3.Error, ValueError, creator_rows.NotFound, postgres.PostgresUnavailable) as error:
        parser.exit(1, f"Recovery failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
