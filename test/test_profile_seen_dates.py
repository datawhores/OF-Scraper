"""When each of a creator's names was seen, and the name a deleted account
goes by (#643).

Each test works on real SQLite files in a temporary folder, through the
app's own create, upgrade and write code. The time a name is seen at is set
by the test: none waits, or depends on when it runs.
"""

import asyncio
import contextlib
import sqlite3

import arrow
import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.placeholder as placeholder
import ofscraper.db.merge as merge
import ofscraper.db.operations as operations
import ofscraper.db.operations_.profile as profile
import ofscraper.db.transition as transition
import ofscraper.utils.cache.cache as cache
from ofscraper.db.difference import get_group_difference
from ofscraper.db.operations_.media import write_media_table_transition
from test.import_files import file_2023, sql, without_the_dates
from test.test_db_merge_site import media as media_row

CREATOR = 5
START = arrow.get("2024-05-01T12:00:00+00:00")
# the queries a deleted account's name came from before: the one in use until
# now, and the one before that. Without ORDER BY, SQLite read the names from
# the index of the table's unique key, which is in the same order
BEFORE = (
    "SELECT username FROM profiles where user_id=(?) ORDER BY username",
    "SELECT username FROM profiles where user_id=(?)",
)


def at(**later):
    """A time after the start, as it is saved."""
    return START.shift(**later).isoformat()


class Clock:
    def __init__(self):
        self.now = START

    def __call__(self):
        return self.now

    def later(self, **time):
        self.now = self.now.shift(**time)


@pytest.fixture
def clock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(profile, "_now", clock)
    return clock


def call(func, *args, **kwargs):
    async def go():
        return await func(*args, **kwargs)

    return asyncio.run(go())


@pytest.fixture
def path(tmp_path, monkeypatch):
    """Where every creator's database is: nothing is there yet."""
    path = tmp_path / "data" / "user_data.db"
    path.parent.mkdir()
    monkeypatch.setattr(
        placeholder.databasePlaceholder,
        "databasePathHelper",
        lambda self, model_id, model_username: path,
    )
    # the periodic backup's times, kept out of the real cache
    store = {}
    monkeypatch.setattr(cache, "get", lambda key, default=None: store.get(key, default))
    monkeypatch.setattr(cache, "set", lambda key, value, **k: store.update({key: value}))
    return path


@pytest.fixture
def db(path):
    """A database as this version makes it."""
    call(operations.create_tables, db_path=path)
    call(transition.modify_tables, db_path=path, new_db=True)
    return path


def record(db, *names, creator=CREATOR):
    """Rows as they would be found: (name, first seen, last seen)."""
    sql(
        db,
        "INSERT INTO profiles (user_id, username, first_seen_at, last_seen_at)"
        " VALUES (?, ?, ?, ?)",
        [(creator, *name) for name in names],
    )


def start(name, creator=CREATOR):
    """The scraper starts work on the creator under a name."""
    call(profile.write_profile_table, model_id=creator, username=name)


def chosen(creator=CREATOR):
    """The name a deleted account goes by."""
    return call(profile.get_profile_info, model_id=creator, username="x")


def names(db):
    return sql(
        db, "SELECT username, first_seen_at, last_seen_at FROM profiles ORDER BY id"
    )


def columns(db):
    return [row[1] for row in sql(db, "PRAGMA table_info('profiles')")]


def first_row(db, query, creator=CREATOR):
    with contextlib.closing(sqlite3.connect(db)) as conn:
        return conn.execute(query, (creator,)).fetchone()[0]


@contextlib.contextmanager
def watching(db):
    """Gives a function that says whether the file was written to since:
    SQLite counts the changes that other connections save."""
    with contextlib.closing(sqlite3.connect(db)) as conn:

        def version():
            return conn.execute("PRAGMA data_version").fetchone()[0]

        before = version()
        yield lambda: version() != before


def old_schema_backups(db):
    folder = db.parent / "backup"
    return sorted(folder.glob("old_schema_*")) if folder.exists() else []


# --- the name a deleted account goes by ---


def test_a_deleted_account_goes_by_the_name_seen_last(db):
    # not the first by name, and not the one recorded last
    record(
        db,
        ("middle_name", at(days=1), at(days=9)),
        ("alpha_name", at(), at(days=3)),
        ("zeta_name", at(days=4), at(days=5)),
    )

    assert chosen() == "middle_name"


def test_a_name_seen_comes_before_every_name_without_a_date(db):
    # when a name was first seen doesn't count: only when it was last seen
    record(
        db,
        ("alpha_name", None, None),
        ("beta_name", at(days=5), None),
        ("seen_name", None, at(days=1)),
        ("zeta_name", None, None),
    )

    assert chosen() == "seen_name"


def test_of_two_names_seen_at_the_same_second_the_one_recorded_later_is_used(db):
    record(
        db,
        ("older_name", at(), at(days=1)),
        ("alpha_name", at(), at(days=2)),
        ("zeta_name", at(), at(days=2)),
    )
    assert chosen() == "zeta_name"

    # the later row, whatever its name
    record(db, ("beta_name", at(), at(days=2)))
    assert chosen() == "beta_name"


def test_another_creators_names_do_not_count(db):
    record(db, ("their_name", at(), at(days=9)), creator=6)
    record(db, ("my_name", at(), at(days=1)))

    assert chosen() == "my_name"
    assert chosen(creator=6) == "their_name"
    assert chosen(creator=7) is None


NAME_SETS = [
    ("zed", "abe", "moe"),
    ("only_name",),
    # capitals come first in SQLite's order
    ("zed", "abe", "Moe"),
    ("abe", "ABE", "aBe", "Abe"),
    ("b_name", "B_name", "a.name", "a_name", "a-name", "_a", "a1", "A1", "9lives"),
    ("creator10", "creator9", "creator_2", "creator"),
]


@pytest.mark.parametrize("names", NAME_SETS, ids=lambda names: names[0])
@pytest.mark.parametrize(
    "layout", ["today's", "from before the dates", "from 2023"]
)
@pytest.mark.slow
def test_without_dates_the_name_is_the_one_chosen_before(path, names, layout):
    # nobody's folder changes because of the upgrade: also in a file the
    # upgrade hasn't reached, which a deleted account's is read as it is
    if layout == "from 2023":
        file_2023(path, CREATOR, name=names[0])
        added = names[1:]
    else:
        call(operations.create_tables, db_path=path)
        call(transition.modify_tables, db_path=path, new_db=True)
        added = names
    sql(
        path,
        "INSERT INTO profiles (user_id, username) VALUES (?, ?)",
        [(CREATOR, name) for name in added],
    )
    if layout == "from before the dates":
        without_the_dates(path)
    assert ("last_seen_at" in columns(path)) is (layout == "today's")

    # a 2023 table has no index that starts with the creator, so only the
    # query with ORDER BY says which name comes first there
    queries = BEFORE[:1] if layout == "from 2023" else BEFORE
    before = {first_row(path, query) for query in queries}

    assert len(before) == 1
    assert chosen() == before.pop()


def test_the_name_chosen_before_is_the_first_in_sqlites_order(db):
    record(db, ("zed", None, None), ("abe", None, None), ("Moe", None, None))

    assert chosen() == "Moe" == first_row(db, BEFORE[0])


@pytest.mark.parametrize("form", [0, 1], ids=["the placeholder", "with the id"])
@pytest.mark.parametrize("layout", ["today's", "from before the dates"])
def test_the_placeholder_is_not_used_while_a_name_is_known(db, form, layout):
    stand_in = profile.placeholder_names(CREATOR)[form]
    sql(
        db,
        "INSERT INTO profiles (user_id, username) VALUES (?, ?)",
        [(CREATOR, stand_in), (CREATOR, "zeta_name"), (CREATOR, "upsilon_name")],
    )
    if layout == "from before the dates":
        without_the_dates(db)

    # it comes before the names in the old order, and was the one used
    assert first_row(db, BEFORE[0]) == stand_in
    assert chosen() == "upsilon_name"


def test_a_placeholder_given_a_date_by_hand_is_still_not_used(db):
    record(
        db,
        (profile.placeholder_names(CREATOR)[0], at(), at(days=9)),
        (profile.placeholder_names(CREATOR)[1], at(), at(days=9)),
        ("a_name", None, None),
    )

    assert chosen() == "a_name"


def test_an_account_known_by_no_name_still_gets_its_placeholder(db):
    stand_in = profile.placeholder_names(CREATOR)[1]
    record(db, (stand_in, None, None))

    assert chosen() == stand_in


def test_the_two_placeholders_are_the_ones_the_scraper_gives():
    plain = profile.of_env.getattr("DELETED_MODEL_PLACEHOLDER")

    assert profile.placeholder_names(77) == [plain, f"{plain}_77"]


# --- the dates, as the scraper works on a creator ---


def test_a_new_name_gets_the_time_as_both_dates(db, clock):
    start("a_name")

    assert names(db) == [("a_name", at(), at())]
    # text of one form, which sorts by time
    assert sql(db, "SELECT typeof(first_seen_at), typeof(last_seen_at) FROM profiles") == [
        ("text", "text")
    ]
    assert at() == "2024-05-01T12:00:00+00:00"


def test_the_time_is_taken_to_the_second_in_utc():
    now = profile._now()

    assert now.microsecond == 0
    assert now.isoformat().endswith("+00:00") and len(now.isoformat()) == 25
    assert abs((arrow.utcnow() - now).total_seconds()) < 60


def test_first_seen_is_set_once_and_last_seen_moves(db, clock):
    start("a_name")
    clock.later(days=1)
    start("a_name")
    clock.later(days=30)
    start("a_name")

    assert names(db) == [("a_name", at(), at(days=31))]


def test_a_creator_started_again_in_the_same_run_is_not_written_again(db, clock):
    start("a_name")
    with watching(db) as written:
        # the scan, then --scrape-paid: hours can lie between
        clock.later(minutes=20)
        start("a_name")
        clock.later(hours=11)
        start("a_name")
        assert not written()
        assert names(db) == [("a_name", at(), at())]
        # the next day's run is one write
        clock.later(hours=13)
        start("a_name")
        assert written()
    assert names(db) == [("a_name", at(), at(hours=24, minutes=20))]


def test_a_new_name_is_one_write(db, clock):
    start("a_name")
    clock.later(days=1)
    with watching(db) as written:
        start("b_name")
        assert written()

    assert names(db) == [("a_name", at(), at()), ("b_name", at(days=1), at(days=1))]


def test_a_creator_renamed_and_renamed_back_goes_by_the_first_name_again(db, clock):
    start("name_a")
    clock.later(minutes=10)
    start("name_b")
    assert chosen() == "name_b"

    # minutes later, well inside the time a date is left alone for
    clock.later(minutes=10)
    start("name_a")

    assert chosen() == "name_a"
    assert names(db) == [
        ("name_a", at(), at(minutes=20)),
        ("name_b", at(minutes=10), at(minutes=10)),
    ]


def test_another_creators_names_do_not_move_a_date(db, clock):
    start("my_name")
    clock.later(minutes=5)
    start("their_name", creator=6)
    clock.later(minutes=5)
    start("my_name")

    assert names(db) == [
        ("my_name", at(), at()),
        ("their_name", at(minutes=5), at(minutes=5)),
    ]


def test_a_date_is_never_moved_back(db, clock):
    # the computer's clock was set back, or a date was written by hand
    start("a_name")
    clock.later(days=-3)
    start("a_name")

    assert names(db) == [("a_name", at(), at())]

    # nor to come before another name's again
    record(db, ("b_name", at(days=1), at(days=1)))
    start("a_name")

    assert names(db) == [("a_name", at(), at()), ("b_name", at(days=1), at(days=1))]


def test_no_other_program_writes_to_a_file_between_the_read_and_the_write(
    db, clock, monkeypatch
):
    # a SQLite file is this program's from before the dates are read, so
    # what it read is still there when it writes. PostgreSQL has no such
    # lock: there the statement itself keeps a date from going back
    # (test_db_postgres_live, and the test below)
    start("a_name")
    clock.later(days=1)
    decide = profile._seen_again
    refused = []

    def meanwhile(seen, username, now):
        with contextlib.closing(sqlite3.connect(db, timeout=0)) as other:
            try:
                other.execute("UPDATE profiles SET last_seen_at = ?", (at(days=2),))
            except sqlite3.OperationalError as E:
                refused.append(str(E))
        return decide(seen, username, now)

    monkeypatch.setattr(profile, "_seen_again", meanwhile)

    start("a_name")

    assert refused == ["database is locked"]
    assert names(db) == [("a_name", at(), at(days=1))]


def test_the_statement_that_moves_a_date_only_moves_it_forward(db):
    # the same moment as at(hours=-1), written with another offset: as text
    # it comes after at()
    other_form = arrow.get(at(hours=-1)).to("+13:00").isoformat()
    assert other_form > at()
    record(
        db,
        ("older", None, at(seconds=-1)),
        ("same", None, at()),
        ("newer", None, at(seconds=1)),
        ("undated", None, None),
        ("as it was read", None, "some day"),
        ("in another form", None, other_form),
    )

    # the last value is the date as the program read it. For the first
    # four that is some other date: another program has written since
    read = {"as it was read": "some day", "in another form": other_form}
    for name, _, _ in names(db):
        sql(
            db,
            profile.profileSeenAgain,
            [(at(), CREATOR, name, at(), read.get(name, at(days=-9)))],
        )

    assert names(db) == [
        ("older", None, at()),
        ("same", None, at()),
        ("newer", None, at(seconds=1)),
        ("undated", None, at()),
        ("as it was read", None, at()),
        ("in another form", None, at()),
    ]


def test_a_date_saved_with_another_offset_is_moved_like_any_other(db, clock):
    # written by hand: the moment the clock starts at, which as text comes
    # after the time twelve hours on
    by_hand = arrow.get(at()).to("+13:00").isoformat()
    assert by_hand > at(hours=12)
    record(db, ("a_name", None, by_hand))
    clock.later(hours=12)

    start("a_name")

    assert names(db) == [("a_name", None, at(hours=12))]


# --- the edges of when a date is moved: to the second, on purpose ---


def test_a_name_is_dated_again_when_another_was_seen_in_the_same_second(db, clock):
    start("name_a")
    start("name_b")
    # of two seen at the same second, the one recorded later
    assert chosen() == "name_b"

    clock.later(minutes=10)
    start("name_a")

    assert names(db) == [("name_a", at(), at(minutes=10)), ("name_b", at(), at())]
    assert chosen() == "name_a"


def test_a_name_seen_at_this_very_second_is_left_alone(db, clock):
    start("name_a")
    start("name_b")
    with watching(db) as written:
        start("name_a")
        assert not written()

    assert names(db) == [("name_a", at(), at()), ("name_b", at(), at())]


def test_a_date_is_moved_after_twelve_hours_and_not_a_second_sooner(db, clock):
    start("a_name")
    with watching(db) as written:
        clock.later(hours=12, seconds=-1)
        start("a_name")
        assert not written()
        clock.later(seconds=1)
        start("a_name")
        assert written()

    assert names(db) == [("a_name", at(), at(hours=12))]


@pytest.mark.parametrize(
    "last, other, now, moved",
    [
        # no date yet
        (None, None, at(), True),
        # seen at this very second, whatever another name's date
        (at(), None, at(), False),
        (at(), at(), at(), False),
        # the clock is behind the date
        (at(), at(days=1), at(seconds=-1), False),
        # another name seen at the same second, or since
        (at(), at(), at(seconds=1), True),
        (at(), at(seconds=1), at(seconds=2), True),
        # another name seen before: once in twelve hours, to the second
        (at(), at(seconds=-1), at(hours=12, seconds=-1), False),
        (at(), at(seconds=-1), at(hours=12), True),
        (at(), None, at(hours=12, seconds=-1), False),
        (at(), None, at(hours=12), True),
    ],
)
def test_when_a_names_date_is_moved(last, other, now, moved):
    seen = {
        "a_name": last and arrow.get(last),
        "b_name": other and arrow.get(other),
    }

    assert profile._seen_again(seen, "a_name", arrow.get(now)) is moved


def test_a_name_recorded_before_the_dates_gets_only_when_it_was_last_seen(db, clock):
    record(db, ("old_name", None, None))

    start("old_name")

    assert names(db) == [("old_name", None, at())]


def test_a_saved_date_that_cant_be_read_is_replaced(db, clock):
    record(db, ("a_name", None, "not a date"))

    start("a_name")

    assert names(db) == [("a_name", None, at())]


@pytest.mark.parametrize("form", [0, 1], ids=["the placeholder", "with the id"])
def test_the_placeholder_gets_a_row_and_never_a_date(db, clock, form):
    stand_in = profile.placeholder_names(CREATOR)[form]

    start(stand_in)
    clock.later(days=1)
    start(stand_in)

    assert names(db) == [(stand_in, None, None)]


def test_a_placeholder_beside_a_name_leaves_the_name_as_it_was(db, clock):
    start("a_name")
    clock.later(days=1)
    start(profile.placeholder_names(CREATOR)[1])

    assert names(db) == [
        ("a_name", at(), at()),
        (profile.placeholder_names(CREATOR)[1], None, None),
    ]
    assert chosen() == "a_name"


def test_a_table_from_before_the_dates_still_takes_a_name(db, clock):
    without_the_dates(db)

    start("a_name")
    start("a_name")

    assert sql(db, "SELECT user_id, username FROM profiles") == [(CREATOR, "a_name")]
    assert columns(db) == ["id", "user_id", "username"]


def test_a_name_that_is_missing_is_still_refused(db, clock):
    with pytest.raises(sqlite3.IntegrityError):
        start(None)


def test_starting_a_creator_twice_dates_the_name_once(path, clock):
    call(operations.table_init_create, model_id=CREATOR, username="a_name")
    clock.later(minutes=5)
    with watching(path) as written:
        call(operations.table_init_create, model_id=CREATOR, username="a_name")
        assert not written()

    assert names(path) == [("a_name", at(), at())]


# --- a database from before the dates ---


def before_the_dates(db):
    """Two names, in a file as the version before this one left it."""
    sql(
        db,
        "INSERT INTO profiles (user_id, username) VALUES (?, ?)",
        [(CREATOR, "zeta_name"), (CREATOR, "alpha_name")],
    )
    return without_the_dates(db)


def test_an_older_database_gets_the_columns_and_keeps_its_rows(db, clock):
    before_the_dates(db)
    assert get_group_difference(db_path=db) == {"profiles_seen_at"}
    assert chosen() == "alpha_name"

    call(operations.table_init_create, model_id=CREATOR, username="zeta_name")

    assert not get_group_difference(db_path=db)
    assert columns(db) == ["id", "user_id", "username", "first_seen_at", "last_seen_at"]
    # the rows, each with the id it had; the dates are empty but for the
    # name this run is under
    assert sql(db, "SELECT * FROM profiles ORDER BY id") == [
        (1, CREATOR, "zeta_name", None, at()),
        (2, CREATOR, "alpha_name", None, None),
    ]
    # copied first, as before any upgrade: the file as it was
    (backup,) = old_schema_backups(db)
    assert backup.name.startswith(f"old_schema_{CREATOR}_")
    assert columns(backup) == ["id", "user_id", "username"]
    assert sql(backup, "SELECT * FROM profiles ORDER BY id") == [
        (1, CREATOR, "zeta_name"),
        (2, CREATOR, "alpha_name"),
    ]
    assert get_group_difference(db_path=backup) == {"profiles_seen_at"}


def test_the_upgrade_alone_changes_no_name_and_no_choice(db):
    before_the_dates(db)

    call(transition.modify_tables, model_id=CREATOR, db_path=db)

    assert names(db) == [("zeta_name", None, None), ("alpha_name", None, None)]
    assert chosen() == "alpha_name"


def test_bringing_a_database_up_to_date_twice_changes_nothing_more(db):
    before_the_dates(db)
    call(transition.modify_tables, model_id=CREATOR, db_path=db)
    layout = sql(db, "SELECT type, name, sql FROM sqlite_master ORDER BY name")
    rows = sql(db, "SELECT * FROM profiles ORDER BY id")
    flags = sql(db, "SELECT * FROM schema_flags ORDER BY flag_name")

    with watching(db) as written:
        call(transition.modify_tables, model_id=CREATOR, db_path=db)
        assert not written()

    assert sql(db, "SELECT type, name, sql FROM sqlite_master ORDER BY name") == layout
    assert sql(db, "SELECT * FROM profiles ORDER BY id") == rows
    assert sql(db, "SELECT * FROM schema_flags ORDER BY flag_name") == flags
    assert len(old_schema_backups(db)) == 1


def test_the_step_that_adds_the_columns_can_run_again(db):
    before_the_dates(db)
    # cut short the first time: one column was added
    sql(db, "ALTER TABLE profiles ADD COLUMN first_seen_at TIMESTAMP")

    for _ in range(2):
        call(profile.add_column_profiles_seen_at, db_path=db)

    assert columns(db) == ["id", "user_id", "username", "first_seen_at", "last_seen_at"]
    assert names(db) == [("zeta_name", None, None), ("alpha_name", None, None)]


def test_a_file_from_2023_gets_the_columns_too(path, clock):
    # from before every upgrade step: the table is rebuilt as well
    file_2023(path, CREATOR, name="zeta_name")
    sql(path, "INSERT INTO profiles (user_id, username) VALUES (?, ?)", [(CREATOR, "alpha_name")])

    call(operations.table_init_create, model_id=CREATOR, username="zeta_name")

    assert not get_group_difference(db_path=path)
    assert sql(path, "SELECT * FROM profiles ORDER BY id") == [
        (1, CREATOR, "zeta_name", None, at()),
        (2, CREATOR, "alpha_name", None, None),
    ]
    (backup,) = old_schema_backups(path)
    assert columns(backup) == ["id", "user_id", "username"]


def test_a_failed_upgrade_puts_the_file_back_as_it_was(db, monkeypatch):
    before_the_dates(db)

    async def fail(**kwargs):
        raise RuntimeError("upgrade failed")

    monkeypatch.setattr(transition, "repair_tables", fail)

    with pytest.raises(RuntimeError, match="upgrade failed"):
        call(transition.modify_tables, model_id=CREATOR, db_path=db)

    assert columns(db) == ["id", "user_id", "username"]
    assert get_group_difference(db_path=db) == {"profiles_seen_at"}
    assert chosen() == "alpha_name"


def test_rebuilding_the_table_keeps_the_dates(db):
    record(db, ("a_name", at(), at(days=3)), ("b_name", None, None))

    call(profile.rebuild_profiles_table, db_path=db)

    assert names(db) == [("a_name", at(), at(days=3)), ("b_name", None, None)]


def test_reading_every_name_of_a_table_from_before_the_dates(db):
    before_the_dates(db)

    assert call(profile.get_all_profiles, db_path=db) == [
        {"user_id": CREATOR, "username": "zeta_name", "first_seen_at": None, "last_seen_at": None},
        {"user_id": CREATOR, "username": "alpha_name", "first_seen_at": None, "last_seen_at": None},
    ]
    assert columns(db) == ["id", "user_id", "username"]


# --- Merge Databases ---


def merged(db, tmp_path, monkeypatch, brought, held):
    """Merge a database that has the names `brought` into `db`, which has
    the names `held`."""
    source = tmp_path / "old" / "creator" / "user_data.db"
    monkeypatch.setattr(merge.paths_db, "get_all_db", lambda folder: [source])
    source.parent.mkdir(parents=True)
    call(operations.create_tables, db_path=source)
    call(transition.modify_tables, db_path=source, new_db=True)
    record(source, *brought)
    # a database with nothing saved in it is passed over
    call(write_media_table_transition, [media_row(1, CREATOR)], db_path=source)
    record(db, *held)

    failures, done, _ = call(merge.MergeDatabase(), tmp_path / "old", db)

    assert failures == [] and len(done) == 1
    return db


def test_merge_brings_a_names_dates_along(db, tmp_path, monkeypatch):
    merged(
        db,
        tmp_path,
        monkeypatch,
        brought=[("old_name", at(), at(days=2)), ("shared_name", at(days=3), at(days=4))],
        held=[("shared_name", at(days=5), at(days=6))],
    )

    # a name both have keeps its row, with the earlier first date and the
    # later last one
    assert sql(db, "SELECT * FROM profiles ORDER BY id") == [
        (1, CREATOR, "shared_name", at(days=3), at(days=6)),
        (2, CREATOR, "old_name", at(), at(days=2)),
    ]


def test_a_merge_does_not_hand_a_deleted_account_an_older_name(db, tmp_path, monkeypatch):
    # the merged database knows the name in use, without dates; the other
    # knows when it was seen, and an older name besides
    merged(
        db,
        tmp_path,
        monkeypatch,
        brought=[
            ("old_name", at(days=1), at(days=30)),
            ("current_name", at(days=31), at(days=300)),
        ],
        held=[("current_name", None, None)],
    )

    assert names(db) == [
        ("current_name", at(days=31), at(days=300)),
        ("old_name", at(days=1), at(days=30)),
    ]
    assert chosen() == "current_name"


EARLY, EARLIER, LATE, LATER = at(days=2), at(days=1), at(days=8), at(days=9)
# (the dates a name has, the dates brought in for it, the dates it has after)
WIDENED = [
    ((None, None), (EARLY, LATE), (EARLY, LATE)),
    # a date is never emptied
    ((EARLY, LATE), (None, None), (EARLY, LATE)),
    ((EARLY, LATE), (EARLIER, None), (EARLIER, LATE)),
    ((EARLY, LATE), (None, LATER), (EARLY, LATER)),
    # the earlier first date and the later last one, from either side
    ((EARLY, LATE), (EARLIER, LATER), (EARLIER, LATER)),
    ((EARLIER, LATER), (EARLY, LATE), (EARLIER, LATER)),
    ((EARLY, LATER), (EARLIER, LATE), (EARLIER, LATER)),
    ((EARLY, LATE), (EARLY, LATE), (EARLY, LATE)),
    ((None, LATE), (EARLY, None), (EARLY, LATE)),
    ((EARLY, None), (None, LATE), (EARLY, LATE)),
    ((None, None), (None, None), (None, None)),
]


@pytest.mark.slow
@pytest.mark.parametrize("has, brought, after", WIDENED)
def test_a_merge_widens_the_dates_of_a_name_both_have(
    db, tmp_path, monkeypatch, has, brought, after
):
    merged(
        db,
        tmp_path,
        monkeypatch,
        brought=[("a_name", *brought)],
        held=[("b_name", EARLY, EARLY), ("a_name", *has)],
    )

    # the same rows, each with its id: only the dates have changed
    assert sql(db, "SELECT * FROM profiles ORDER BY id") == [
        (1, CREATOR, "b_name", EARLY, EARLY),
        (2, CREATOR, "a_name", *after),
    ]


@pytest.mark.parametrize(
    "brought",
    [(None, None), (EARLY, LATE), (LATE, EARLY), (None, EARLY), (LATE, None)],
)
def test_a_name_whose_dates_would_stay_as_they_are_is_not_written(db, brought):
    record(db, ("a_name", EARLY, LATE))

    with contextlib.closing(sqlite3.connect(db)) as conn:
        conn.execute(profile.profileInsertWiden, (CREATOR, "a_name", *brought))
        # no row was written, not even with the values it had
        assert conn.total_changes == 0
        conn.execute(profile.profileInsertWiden, (CREATOR, "a_name", EARLIER, None))
        assert conn.total_changes == 1
        conn.commit()

    assert names(db) == [("a_name", EARLIER, LATE)]


def test_a_dated_name_a_merge_brings_is_the_one_a_deleted_account_goes_by(
    db, tmp_path, monkeypatch
):
    # none of the names here has a date, so the first by name is used. The
    # other database saw another name: it is the only one known to be seen
    record(db, ("alpha_name", None, None))
    assert chosen() == "alpha_name"

    merged(
        db,
        tmp_path,
        monkeypatch,
        brought=[("zeta_name", at(), at(days=2))],
        held=[],
    )

    assert chosen() == "zeta_name"
