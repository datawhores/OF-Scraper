r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/

"""

import contextlib
import logging

import arrow
from rich.console import Console

import ofscraper.db.operations_.wrapper as wrapper
import ofscraper.db.utils.columns as db_columns
import ofscraper.db.utils.rebuild as rebuild
import ofscraper.utils.of_env.of_env as of_env

console = Console()
log = logging.getLogger("shared")

# user_id==modes.id cause of legacy
# first_seen_at and last_seen_at (#643): when the scraper first and last
# worked on the creator under the name. In a SQLite file they are ISO text in
# UTC, to the second (2024-03-01T09:30:00+00:00), so that the order of the
# text is the order of the times. Both are empty for a name recorded before
# the columns, and for one added by hand without a date
profilesCreate = """
CREATE TABLE IF NOT EXISTS profiles (
	id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	username VARCHAR NOT NULL,
	first_seen_at TIMESTAMP,
	last_seen_at TIMESTAMP,
	PRIMARY KEY (id),
    UNIQUE (user_id,username)
)
"""
SEEN_COLUMNS = ("first_seen_at", "last_seen_at")
# A name's last_seen_at is moved once in this many seconds. A run starts a
# creator more than once (the scan, then --scrape-paid), and each start would
# be a write. A name seen after another of the creator's names is always
# dated, so the name seen last has the newest date (see _seen_again)
SEEN_EVERY = 12 * 60 * 60
modelsCreate = """
CREATE TABLE IF NOT EXISTS models (
	id INTEGER NOT NULL,
	model_id INTEGER NOT NULL,
	PRIMARY KEY (id),                     
	UNIQUE (model_id)
)
"""
# The name a deleted account goes by (#643) is the first row of this. The
# three ? are the creator and placeholder_names(). In order:
# - a name the creator had comes before the placeholder of a deleted account
# - then the name seen last; of two seen at the same second, the one
#   recorded later
# - when no name has a date, the first by name: the one used before the
#   dates were kept, so that an account's folder doesn't change with them
# scripts/creator_names.py has a copy of both queries, which
# test_creator_names keeps the same
deletedAccountName = """
SELECT username FROM profiles WHERE user_id = ?
ORDER BY
    CASE WHEN username = ? OR username = ? THEN 1 ELSE 0 END,
    CASE WHEN last_seen_at IS NULL THEN 1 ELSE 0 END,
    last_seen_at DESC,
    CASE WHEN last_seen_at IS NULL THEN 0 ELSE id END DESC,
    username
"""
# the same for a database from before the dates
deletedAccountNameUndated = """
SELECT username FROM profiles WHERE user_id = ?
ORDER BY
    CASE WHEN username = ? OR username = ? THEN 1 ELSE 0 END,
    username
"""

# a row is added once (INSERT ... SELECT ?, ? WHERE NOT EXISTS gives the
# values no type outside SQLite)
profileInsert = """
INSERT INTO profiles (user_id, username) VALUES (?, ?) ON CONFLICT DO NOTHING;
"""
profileInsertSeen = """
INSERT INTO profiles (user_id, username, first_seen_at, last_seen_at)
VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING;
"""
profileLastSeen = """
SELECT username, last_seen_at FROM profiles WHERE user_id = ?
"""
# Moves a name's last_seen_at forward, and never back. The last ? is the
# date as this program read it: where that is still there it is replaced,
# whatever its form. Where another program has written one since, only an
# older one is replaced
profileSeenAgain = """
UPDATE profiles SET last_seen_at = ?
WHERE user_id = ? AND username = ?
    AND (last_seen_at IS NULL OR last_seen_at < ? OR last_seen_at = ?)
"""


profileInsertTransition = """INSERT INTO profiles(
user_id,username,first_seen_at,last_seen_at)
            VALUES (?, ?, ?, ?);
"""
# What becomes of a name's dates when rows are brought in from elsewhere
# (Merge Databases, postgres_import) and the name is already there: the
# earlier first_seen_at and the later last_seen_at are kept. A date is never
# emptied, and a row that would stay as it is isn't written. It follows an
# INSERT INTO ... profiles (...) VALUES (...) of both dates, on either engine
profileWiden = """
ON CONFLICT (user_id, username) DO UPDATE SET
    first_seen_at = CASE
        WHEN excluded.first_seen_at < profiles.first_seen_at
        THEN excluded.first_seen_at
        ELSE COALESCE(profiles.first_seen_at, excluded.first_seen_at) END,
    last_seen_at = CASE
        WHEN excluded.last_seen_at > profiles.last_seen_at
        THEN excluded.last_seen_at
        ELSE COALESCE(profiles.last_seen_at, excluded.last_seen_at) END
WHERE (excluded.first_seen_at IS NOT NULL AND (
        profiles.first_seen_at IS NULL
        OR excluded.first_seen_at < profiles.first_seen_at))
    OR (excluded.last_seen_at IS NOT NULL AND (
        profiles.last_seen_at IS NULL
        OR excluded.last_seen_at > profiles.last_seen_at))
"""
profileInsertWiden = (
    """INSERT INTO profiles (user_id, username, first_seen_at, last_seen_at)
VALUES (?, ?, ?, ?)"""
    + profileWiden
)
modelInsert = """
INSERT INTO models (model_id) VALUES (?) ON CONFLICT DO NOTHING;
"""
# a table from before the dates is read as having none
PROFILE_COLUMNS = [
    "user_id",
    "username",
    ("first_seen_at", "NULL"),
    ("last_seen_at", "NULL"),
]

modelsALL = """
select model_id from models
"""


profileUnique = """
SELECT DISTINCT user_id FROM profiles
"""


def placeholder_names(model_id):
    """The two names a deleted account is given when its own isn't known.
    Neither is a name the creator had: they get no dates, and a name the
    creator had is used before them."""
    placeholder = of_env.getattr("DELETED_MODEL_PLACEHOLDER")
    return [placeholder, f"{placeholder}_{model_id}"]


def _has_dates(cur):
    """Whether the profiles table has the two dates: one made by an earlier
    version, and not yet brought up to date, has not."""
    return "last_seen_at" in db_columns.table_columns(cur, "profiles")


def _now():
    """The time a name is seen at, to the second."""
    return arrow.utcnow().floor("second")


def _moment(saved):
    """A saved date as a moment. None for no date, or one that can't be read."""
    if saved is None or saved == "":
        return None
    try:
        return arrow.get(saved)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def _seen_again(seen, username, now):
    """Whether `username`'s last_seen_at is moved to `now`. `seen` is each of
    the creator's names with when it was last seen (None for no date).

    Always when another name was seen since, or at the same second: the name
    in use is then the one with the newest date again. Otherwise once in
    SEEN_EVERY. A date is never moved back."""
    last = seen[username]
    if last is None:
        return True
    if last >= now:
        return False
    if any(
        other is not None and other >= last
        for name, other in seen.items()
        if name != username
    ):
        return True
    return (now - last).total_seconds() >= SEEN_EVERY


@wrapper.operation_wrapper_async
def get_profile_info(model_id=None, username=None, conn=None, **kwargs) -> list:
    """The name a deleted account goes by: one the database has for it,
    chosen by deletedAccountName. None when it has none."""
    if not wrapper.database_exists(model_id, username):
        return None
    with contextlib.closing(conn.cursor()) as cur:
        try:
            cur.execute(
                deletedAccountName if _has_dates(cur) else deletedAccountNameUndated,
                [model_id, *placeholder_names(model_id)],
            )
            return (list(map(lambda x: x[0], cur.fetchall())) or [None])[0]
        except wrapper.OPERATIONAL_ERRORS:
            pass
        except Exception as E:
            raise E


@wrapper.operation_wrapper_async
def create_profile_table(
    model_id=None, username=None, conn=None, db_path=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(profilesCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def add_column_profiles_seen_at(conn=None, **kwargs):
    with contextlib.closing(conn.cursor()) as cur:
        try:
            present = db_columns.table_columns(cur, "profiles")
            for column in SEEN_COLUMNS:
                if column not in present:
                    cur.execute(f"ALTER TABLE profiles ADD COLUMN {column} TIMESTAMP;")
            conn.commit()
        except wrapper.DB_ERRORS as e:
            conn.rollback()
            raise e


@wrapper.operation_wrapper_async
def write_profile_table(model_id=None, username=None, conn=None, **kwargs) -> list:
    """Record the name the creator is being worked on under (#643). A name
    seen for the first time gets a row, with the time as both of its dates.
    After that only last_seen_at changes, and not at every start (see
    _seen_again): at most one row is written.

    The placeholder of a deleted account gets its row as before and never a
    date. So does any name in a table from before the dates."""
    with contextlib.closing(conn.cursor()) as cur:
        if username in placeholder_names(model_id) or not _has_dates(cur):
            cur.execute(profileInsert, [model_id, username])
        else:
            now = _now()
            when = wrapper.date_value(conn, now.isoformat())
            saved = {
                row[0]: row[1]
                for row in cur.execute(profileLastSeen, [model_id]).fetchall()
            }
            seen = {name: _moment(date) for name, date in saved.items()}
            if username not in seen:
                cur.execute(profileInsertSeen, [model_id, username, when, when])
            elif _seen_again(seen, username, now):
                cur.execute(
                    profileSeenAgain,
                    [when, model_id, username, when, saved[username]],
                )
        conn.commit()


def profiles_transition_rows(inputData) -> list:
    # a row read before the dates were kept has none
    return [
        (data["user_id"], data["username"], *(data.get(key) for key in SEEN_COLUMNS))
        for data in inputData
    ]


@wrapper.operation_wrapper_async
def write_profile_table_transition(inputData, conn=None, **kwargs) -> list:
    """Bring another database's names in. One this database hasn't got is
    added with its dates; one it has keeps its row, and its dates are
    widened to take the other's in (profileWiden)."""
    with contextlib.closing(conn.cursor()) as cur:
        cur.executemany(profileInsertWiden, profiles_transition_rows(inputData))
        conn.commit()


@wrapper.operation_wrapper_async
def replace_profiles_table(inputData, conn=None, **kwargs):
    rebuild.replace_table(
        conn,
        "profiles",
        profilesCreate,
        profileInsertTransition,
        profiles_transition_rows(inputData),
    )


@wrapper.operation_wrapper_async
def check_profile_table_exists(model_id=None, username=None, conn=None, **kwargs):
    if not wrapper.database_exists(model_id, username):
        return False
    with contextlib.closing(conn.cursor()) as cur:
        return wrapper.backend_of(cur).table_exists(cur, "profiles")


@wrapper.operation_wrapper_async
def get_all_profiles(
    model_id=None, username=None, conn=None, db_path=None, **kwargs
) -> list:
    if not wrapper.database_exists(model_id, username, db_path):
        return None
    with contextlib.closing(conn.cursor()) as cur:
        try:
            profiles = [
                dict(row)
                for row in cur.execute(
                    db_columns.select_all(cur, "profiles", PROFILE_COLUMNS)
                ).fetchall()
            ]
            return profiles
        except wrapper.OPERATIONAL_ERRORS:
            pass
        except Exception as E:
            raise E


@wrapper.operation_wrapper_async
def create_models_table(
    model_id=None, username=None, db_path=None, conn=None, **kwargs
):
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(modelsCreate)
        conn.commit()


@wrapper.operation_wrapper_async
def write_models_table(model_id=None, username=None, conn=None, **kwargs) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        cur.execute(modelInsert, [model_id])
        conn.commit()


@wrapper.operation_wrapper
def get_single_model_via_profile(
    model_id=None, username=None, conn=None, db_path=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        models_ids = [
            dict(row)["user_id"] for row in cur.execute(profileUnique).fetchall()
        ]
        return models_ids[0] if len(models_ids) == 1 else None


@wrapper.operation_wrapper_async
def get_all_models(
    model_id=None, username=None, conn=None, db_path=None, **kwargs
) -> list:
    with contextlib.closing(conn.cursor()) as cur:
        return [dict(row) for row in (cur.execute(modelsALL).fetchall())]


async def rebuild_profiles_table(model_id=None, username=None, db_path=None, **kwargs):
    data = await get_all_profiles(model_id=model_id, username=username, db_path=db_path)
    await replace_profiles_table(
        data, model_id=model_id, username=username, db_path=db_path
    )
