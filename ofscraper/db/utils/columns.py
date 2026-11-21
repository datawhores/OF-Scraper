def table_columns(cur, table):
    """The names of the columns `table` has."""
    return {row[1] for row in cur.execute(f"PRAGMA table_info('{table}')")}


def creator_filter(cur, table, model_id, joiner="AND"):
    """(sql, params) that limit a read of `table` to one creator's rows, to
    add after the query: `joiner` is "WHERE" for a query without a condition.

    A database can hold several creators (a merged one, or a `metadata`
    folder that doesn't name the creator), and a read that decides what a
    creator already has must not count another creator's rows.

    A row with no model_id still counts: an upgrade leaves it empty when it
    can't tell whose the old rows are (no profile, or several), and those
    rows were always read as the creator's. Nothing is added when no creator
    is given (a tool that reads a whole database), or for a table from
    before model_id, which holds one creator's rows."""
    if model_id is None or "model_id" not in table_columns(cur, table):
        return "", []
    return f" {joiner} (model_id=(?) OR model_id IS NULL)", [model_id]


def same_creator(model_id):
    """(sql, params) for "the row is model_id's", to fill a query's {creator}.
    model_id may be None: a row saved before the column was filled in has
    none. SQLite's `model_id IS ?` says the same, but only SQLite has it."""
    if model_id is None:
        return "model_id IS NULL", []
    return "model_id = ?", [model_id]


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
