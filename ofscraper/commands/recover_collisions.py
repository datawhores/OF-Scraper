"""Offline recovery of ambiguous shared download paths; preview unless --apply."""

import argparse
import json
import os
from pathlib import Path
import sqlite3
import stat
import uuid
from collections import defaultdict
from contextlib import closing


def find_collisions(conn, path_root=None):
    """Group distinct media by their recorded path or existing file identity."""
    groups = defaultdict(list)
    rows = conn.execute(
        "SELECT model_id, media_id, directory, filename, downloaded FROM medias "
        "WHERE media_id IS NOT NULL AND filename IS NOT NULL AND filename != ''"
    )
    for model, media, directory, filename, downloaded in rows:
        path = Path(directory or "", filename)
        if not path.is_absolute():
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
            result = {
                "groups": [
                    {"paths": sorted({r[2] for r in group}),
                     "media": [{"model_id": model, "media_id": media}
                               for model, media in sorted(
                                   {(r[0], r[1]) for r in group}, key=str)]}
                    for group in groups
                ],
                "media_to_mark": len(pending),
                "rows_marked": 0,
                "undo_file": None,
                "applied": apply,
            }
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="One model's user_data.db")
    parser.add_argument("--apply", action="store_true", help="Apply the previewed recovery or undo operation")
    parser.add_argument("--undo", type=Path, help="Preview restoring flags from a recovery undo file")
    parser.add_argument("--path-root", type=Path, help="Original working directory for relative recorded paths")
    args = parser.parse_args(argv)
    try:
        result = (undo(args.database, args.undo, apply=args.apply) if args.undo
                  else recover(args.database, apply=args.apply, path_root=args.path_root))
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f"Recovery failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
