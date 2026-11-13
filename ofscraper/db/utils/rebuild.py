import contextlib
import re


def replace_table(conn, table, create_sql, insert_sql, rows):
    """Rebuild a table from rows in one transaction.

    Follows SQLite's documented order for a schema change: create the new
    table under a temporary name, copy the rows in, drop the old table, then
    rename the new one into place. Views that name the table keep pointing at
    it.

    If conn is not already in a transaction, this opens one (BEGIN IMMEDIATE),
    so it is safe on a plain sqlite3 connection too. Any failure rolls back
    and leaves the old table and its rows as they were.
    """
    new = f"{table}_rebuild_new"
    new_create_sql, count = re.subn(
        rf"(CREATE TABLE IF NOT EXISTS\s+){table}\b",
        rf"\g<1>{new}",
        create_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    if count != 1:
        raise ValueError(f"create statement does not create table {table}")
    new_insert_sql, count = re.subn(
        rf"(INSERT INTO\s+)'?{table}'?(?=\s*\()",
        rf"\g<1>'{new}'",
        insert_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    if count != 1:
        raise ValueError(f"insert statement does not insert into {table}")
    with contextlib.closing(conn.cursor()) as cur:
        try:
            if not conn.in_transaction:
                cur.execute("BEGIN IMMEDIATE;")
            cur.execute(new_create_sql)
            cur.executemany(new_insert_sql, rows)
            cur.execute(f"DROP TABLE {table};")
            # legacy mode renames only the table itself: views that name the
            # table are not checked while it is briefly missing, and keep
            # pointing at it once the new one has its name
            legacy = cur.execute("PRAGMA legacy_alter_table;").fetchone()[0]
            cur.execute("PRAGMA legacy_alter_table=ON;")
            try:
                cur.execute(f"ALTER TABLE {new} RENAME TO {table};")
            finally:
                cur.execute(f"PRAGMA legacy_alter_table={int(legacy)};")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
