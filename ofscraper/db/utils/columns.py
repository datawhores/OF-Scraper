def table_columns(cur, table):
    """The names of the columns `table` has."""
    return {row[1] for row in cur.execute(f"PRAGMA table_info('{table}')")}


def select_list(present, columns):
    """The select list for `columns`, given the table's columns (`present`).

    Each item of `columns` is a column name, or a (name, stand_in) pair for a
    column a later version added: when the table doesn't have it, stand_in (an
    SQL expression, e.g. "NULL") is selected under its name instead. SQLite
    checks every column name before it runs a query, so this is decided here,
    from the table's columns, and not inside the query.
    """
    parts = []
    for column in columns:
        if isinstance(column, str):
            parts.append(column)
            continue
        name, stand_in = column
        parts.append(name if name in present else f"{stand_in} AS {name}")
    return ", ".join(parts)


def select_all(cur, table, columns):
    """A SELECT of `columns` (see select_list) from `table`, for a table that
    may be older than this version. Nothing is changed in the table."""
    return f"SELECT {select_list(table_columns(cur, table), columns)} FROM {table};"
