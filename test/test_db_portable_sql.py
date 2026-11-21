"""The database's queries keep to SQL that SQLite and PostgreSQL both accept
(#608), so the same query text can run on either.

The first tests read every string out of the database code and look for the
SQLite-only spellings that were in use. The rest check that the rewritten
queries still do the same thing on SQLite.
"""

import ast
import asyncio
import contextlib
import pathlib
import re
import sqlite3
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.operations as operations
import ofscraper.db.operations_.empty as empty
import ofscraper.db.operations_.media as media
import ofscraper.db.operations_.others as others
import ofscraper.db.operations_.profile as profile
import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.utils.columns as db_columns
from ofscraper.db.transition import modify_tables

DB = pathlib.Path(operations.__file__).parent
SOURCES = sorted(
    path
    for folder in ("operations_", "utils")
    for path in (DB / folder).glob("*.py")
    if path.name != "wrapper.py"
)
STATEMENT = re.compile(r"^\s*(WITH|SELECT|UPDATE|DELETE|INSERT)\b", re.IGNORECASE)
BOOLEANS = (
    "linked|downloaded|unlocked|skip_permanent|preview|paid|archived|pinned"
    "|stream|opened|is_deleted"
)
# what the queries used, and what both databases accept instead
SQLITE_ONLY = {
    "a table name in quotes": re.compile(
        r"\b(INTO|UPDATE|FROM)\s+'", re.IGNORECASE
    ),
    "INSERT OR REPLACE (use ON CONFLICT)": re.compile(r"INSERT\s+OR\b", re.IGNORECASE),
    "a yes/no column compared with 0 or 1 (use TRUE/FALSE)": re.compile(
        rf"\b({BOOLEANS})\s*(=|==|<>|!=|IS\s+NOT|IS)\s*\(?[01]\)?(?![\w.])",
        re.IGNORECASE,
    ),
    # 2 IS TRUE is true in SQLite, and 2 = TRUE is not
    "IS TRUE or IS FALSE, a truth test in SQLite (use = or <>)": re.compile(
        r"\bIS\s+(NOT\s+)?(TRUE|FALSE)\b", re.IGNORECASE
    ),
    "IS ? (use db_columns.same_creator)": re.compile(
        r"\bIS\s+(NOT\s+)?\?", re.IGNORECASE
    ),
    "a schema flag compared with a number (the column is text)": re.compile(
        r"flag_value\s*(=|==|<>|!=)\s*\d", re.IGNORECASE
    ),
    "a % sign (the PostgreSQL driver's placeholder)": re.compile("%"),
    "INSERT ... SELECT ? (the value has no type)": re.compile(
        r"INSERT\b[^;]*\bSELECT\s+\?", re.IGNORECASE | re.DOTALL
    ),
}
# a rule that also holds for a piece of a query (" and downloaded=TRUE"),
# which is checked in every string, not only in whole statements
IN_PIECES = [name for name in SQLITE_ONLY if "yes/no" in name or name.startswith("IS ")]
# the steps that bring an old SQLite file up to date only ever run on SQLite
SQLITE_UPGRADE = re.compile(r"PRAGMA|sqlite_master", re.IGNORECASE)


def strings():
    """(where, text, is a whole statement) for every string in the database
    code that isn't a docstring."""
    found = []
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            id(node.body[0].value)
            for node in ast.walk(tree)
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            )
            and node.body
            and isinstance(node.body[0], ast.Expr)
        }
        inside_fstring = {
            id(part)
            for node in ast.walk(tree)
            if isinstance(node, ast.JoinedStr)
            for part in node.values
        }
        for node in ast.walk(tree):
            if id(node) in docstrings or id(node) in inside_fstring:
                continue
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value
            elif isinstance(node, ast.JoinedStr):
                text = "".join(
                    part.value if isinstance(part, ast.Constant) else "x"
                    for part in node.values
                )
            else:
                continue
            if SQLITE_UPGRADE.search(text):
                continue
            found.append(
                (f"{path.name}:{node.lineno}", text, bool(STATEMENT.match(text)))
            )
    return found


def problems(found):
    return [
        f"{where}: {name}"
        for where, text, statement in found
        for name, pattern in SQLITE_ONLY.items()
        if (statement or name in IN_PIECES) and pattern.search(text)
    ]


def test_the_queries_are_found():
    # the check below would pass on nothing
    assert sum(statement for _, _, statement in strings()) > 60


def test_no_query_uses_a_spelling_only_sqlite_accepts():
    assert problems(strings()) == []


@pytest.mark.parametrize(
    "text, statement",
    [
        ("Update 'medias' SET x=1", True),
        ("INSERT OR REPLACE INTO schema_flags VALUES (?, ?)", True),
        ("SELECT media_id FROM medias where downloaded=(1)", True),
        (" and skip_permanent IS NOT 1", False),
        (" AND downloaded<>0", False),
        (" and skip_permanent IS NOT TRUE", False),
        ("model_id IS ?", False),
        ("model_id IS NOT ?", False),
        ("SELECT flag_name FROM schema_flags WHERE flag_value = 1;", True),
        ("SELECT a FROM t WHERE b LIKE '%x'", True),
        ("INSERT INTO models (model_id) SELECT ? WHERE NOT EXISTS (SELECT 1)", True),
    ],
)
def test_the_check_knows_each_spelling(text, statement):
    assert problems([("here", text, statement)]) != []


def test_the_check_accepts_what_the_queries_use_now():
    fine = [
        ("here", "SELECT media_id FROM medias where downloaded=TRUE", True),
        ("here", " and (skip_permanent IS NULL OR skip_permanent <> TRUE)", False),
        ("here", "model_id IS NULL", False),
        ("here", "SELECT flag_name FROM schema_flags WHERE flag_value = '1';", True),
        ("here", "UPDATE medias SET downloaded = NULL WHERE media_id = ?", True),
    ]
    assert problems(fine) == []


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "user_data.db"

    async def make():
        await operations.create_tables(db_path=path)
        await modify_tables(db_path=path, new_db=True)

    asyncio.run(make())
    return path


def rows(db, sql):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return sorted(conn.execute(sql).fetchall())


def test_a_flag_is_set_once_and_can_be_set_again(db):
    async def go():
        await others.add_flag_schema("made_up_flag", db_path=db)
        await others.add_flag_schema("made_up_flag", db_path=db)
        await others.write_site_flag("fansly", db_path=db)
        await others.write_site_flag("fansly", db_path=db)

    asyncio.run(go())

    assert rows(
        db,
        "SELECT flag_name, flag_value FROM schema_flags"
        " WHERE flag_name IN ('made_up_flag', 'site')",
    ) == [("made_up_flag", "1"), ("site", "fansly")]
    assert "made_up_flag" in others.get_schema_changes(db_path=db)
    # a flag with another value isn't a finished step
    assert "site" not in others.get_schema_changes(db_path=db)


def test_setting_a_flag_again_replaces_its_value(db):
    async def go():
        await others.write_site_flag("fansly", db_path=db)
        await others.write_site_flag("onlyfans", db_path=db)

    asyncio.run(go())

    assert others.get_site_flag(db_path=db) == "onlyfans"
    assert rows(db, "SELECT COUNT(*) FROM schema_flags WHERE flag_name = 'site'") == [
        (1,)
    ]


def test_a_profile_and_a_model_are_added_once(db):
    async def go():
        for _ in range(2):
            await profile.write_profile_table(
                model_id=5, username="a_creator", db_path=db
            )
            await profile.write_models_table(model_id=5, db_path=db)
        await profile.write_profile_table(model_id=5, username="renamed", db_path=db)

    asyncio.run(go())

    assert rows(db, "SELECT user_id, username FROM profiles") == [
        (5, "a_creator"),
        (5, "renamed"),
    ]
    assert rows(db, "SELECT model_id FROM models") == [(5,)]


def test_a_profile_without_a_name_is_still_refused(db):
    # adding a row once doesn't hide a row that can't be added at all
    async def go():
        await profile.write_profile_table(model_id=5, username=None, db_path=db)

    with pytest.raises(sqlite3.IntegrityError):
        asyncio.run(go())


def test_the_first_username_is_the_first_by_name(db, monkeypatch):
    # the unique key gave this order in SQLite; the query now asks for it.
    # get_profile_info looks for the creator's usual file before it reads
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: db,
    )

    # names without dates, as they were recorded when this order was all
    # there was to go by (test_profile_seen_dates has the names with dates)
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.executemany(
            "INSERT INTO profiles (user_id, username) VALUES (5, ?)",
            [("zed",), ("abe",), ("moe",)],
        )
        conn.commit()

    async def go():
        return await profile.get_profile_info(model_id=5, username="x", db_path=db)

    assert asyncio.run(go()) == "abe"


def test_a_medias_download_record_is_its_lowest_posts(db):
    # media in two posts has two rows; the unique key gave this order
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.executemany(
            "INSERT INTO medias (media_id, post_id, model_id, filename)"
            " VALUES (1, ?, 5, ?)",
            [(20, "second.jpg"), (10, "first.jpg")],
        )
        conn.commit()

    async def go():
        return await media.prev_download_media_data(
            SimpleNamespace(id=1, post_id=20), model_id=5, db_path=db
        )

    assert asyncio.run(go())["filename"] == "first.jpg"


@pytest.mark.parametrize("value", [2, -1, 0.5, "2"])
def test_only_a_skip_saved_as_1_is_a_permanent_skip(db, value):
    # the column has held other values in copied and hand-edited files:
    # they were never permanent skips, and still aren't
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.executemany(
            "INSERT INTO medias (media_id, post_id, model_id, downloaded,"
            " skip_permanent) VALUES (?,10,5,1,?)",
            [(1, value), (2, 1), (3, None), (4, 0)],
        )
        conn.commit()

    assert sorted(
        media.get_media_ids_downloaded(without_permanent_skips=True, db_path=db)
    ) == [1, 3, 4]
    assert sorted(
        media.get_media_ids_downloaded_model_sync(
            model_id=5, without_permanent_skips=True, db_path=db
        )
    ) == [1, 3, 4]
    assert sorted(
        media.get_media_post_ids_downloaded(
            model_id=5, model_only=True, without_permanent_skips=True, db_path=db
        )
    ) == [(1, 10), (3, 10), (4, 10)]

    async def skips():
        # an id given as text reads the same rows
        return await media.get_permanent_skip_media_ids(model_id="5", db_path=db)

    assert asyncio.run(skips()) == {2}


def test_empty_counts_rows_by_position(db):
    assert asyncio.run(empty.empty(db_path=db)) is True
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute("INSERT INTO messages (post_id, model_id) VALUES (1, 5)")
        conn.commit()
    assert asyncio.run(empty.empty(db_path=db)) is False


@pytest.mark.parametrize("model_id", [5, None], ids=["a creator", "no creator"])
def test_permanent_skips_are_read_and_unmarked_for_the_rows_creator(db, model_id):
    # model_id IS ? matched a row without a creator too; so does the new form
    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.executemany(
            "INSERT INTO medias (media_id, post_id, model_id, downloaded,"
            " skip_permanent) VALUES (?,?,?,1,?)",
            [(1, 10, model_id, 1), (2, 10, model_id, None), (3, 10, 99, 1)],
        )
        conn.commit()

    async def go():
        ids = await media.get_permanent_skip_media_ids(model_id=model_id, db_path=db)
        changed = await media.unmark_permanent_skips(
            [1, 2, 3], model_id=model_id, db_path=db
        )
        return ids, changed

    assert asyncio.run(go()) == ({1}, 1)
    assert rows(db, "SELECT media_id, downloaded, skip_permanent FROM medias") == [
        (1, None, None),
        (2, 1, None),
        (3, 1, 1),
    ]


def test_same_creator():
    assert db_columns.same_creator(5) == ("model_id = ?", [5])
    assert db_columns.same_creator(None) == ("model_id IS NULL", [])


def test_an_sqlite_too_old_for_the_queries_is_named(db, monkeypatch):
    monkeypatch.setattr(wrapper.sqlite3, "sqlite_version_info", (3, 22, 0))
    monkeypatch.setattr(wrapper.sqlite3, "sqlite_version", "3.22.0")

    with pytest.raises(wrapper.DatabaseUnreadable, match="3.22.0.*3.24 or newer"):
        others.get_schema_changes(db_path=db)

    async def write():
        await others.add_flag_schema("made_up_flag", db_path=db)

    with pytest.raises(wrapper.DatabaseUnreadable, match="3.24 or newer"):
        asyncio.run(write())


def test_this_pythons_sqlite_is_new_enough():
    assert sqlite3.sqlite_version_info >= wrapper.MIN_SQLITE
