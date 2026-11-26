"""One run of the app's database functions, for comparing engines (#608).

`scenario()` saves two creators' posts, messages, stories, labels and media
through the same functions a scrape uses, then reads everything back.
test_db_postgres_live runs it on SQLite and on PostgreSQL and compares the
two results; test_db_postgres runs it on SQLite alone, so the scenario itself
is checked wherever the tests run.
"""

import contextlib
from types import SimpleNamespace
from unittest import mock

import arrow

import ofscraper.db.operations as operations
import ofscraper.db.operations_.labels as labels
import ofscraper.db.operations_.media as media
import ofscraper.db.operations_.messages as messages
import ofscraper.db.operations_.others as others
import ofscraper.db.operations_.posts as posts
import ofscraper.db.operations_.profile as profile
import ofscraper.db.operations_.stories as stories
import ofscraper.db.operations_.wrapper as wrapper

ONE, TWO = 111, 222
NAMES = {ONE: "creator_one", TWO: "creator_two"}
# a Fansly-sized id: more than 32 bits, and more than a float holds exactly
BIG = 712345678901234567
# a profile picture's ids
AVATAR = "0123456789abcdef0123456789abcdef"
AVATAR_POST = "fedcba9876543210fedcba9876543210"
DAY1 = "2024-01-03T03:04:05+00:00"
DAY2 = "2024-02-04T10:00:00+00:00"
# the same moment as 2024-03-05T06:30:00+00:00
DAY3_OFFSET = "2024-03-05T08:30:00+02:00"
DATE_KEYS = {"created_at", "posted_at", "first_seen_at", "last_seen_at"}
TABLES = (
    "medias", "posts", "messages", "stories", "others", "products", "labels",
    "profiles", "models", "schema_flags",
)
# when the scenario's clock starts: the names' dates are counted from here
START = "2024-05-01T12:00:00+00:00"
# names recorded for creator two by a version that kept no dates. With a
# capital: the order of names isn't the same on every engine
OLD_NAMES = ("moe", "Zed", "abe")


class Clock:
    """The time the names are seen at, set by the scenario: both engines
    then save the same dates."""

    def __init__(self):
        self.now = arrow.get(START)

    def __call__(self):
        return self.now

    def later(self, **time):
        self.now = self.now.shift(**time)


def after_start(**time):
    return arrow.get(START).shift(**time).isoformat()


@wrapper.operation_wrapper
def table_rows(table, conn=None, **kwargs):
    """Every row of a table, as the engine gives them."""
    with contextlib.closing(conn.cursor()) as cur:
        return [dict(row) for row in cur.execute(f"SELECT * FROM {table}").fetchall()]


@wrapper.operation_wrapper
def record_names(names, model_id=None, conn=None, **kwargs):
    """Names as a version before the dates recorded them."""
    with contextlib.closing(conn.cursor()) as cur:
        cur.executemany(
            "INSERT INTO profiles (user_id, username) VALUES (?, ?)",
            [(model_id, name) for name in names],
        )
        conn.commit()


@wrapper.operation_wrapper
def name_before_the_dates(model_id=None, conn=None, **kwargs):
    """The name a deleted account went by before #643: the first row of the
    query that was in use, on this engine."""
    with contextlib.closing(conn.cursor()) as cur:
        return cur.execute(
            "SELECT username FROM profiles where user_id=(?) ORDER BY username",
            [model_id],
        ).fetchall()[0][0]


def post(post_id, date=DAY1, **changes):
    values = dict(
        id=post_id,
        db_text=f"text of {post_id}",
        price=0,
        paid=False,
        archived=False,
        pinned=False,
        stream=False,
        opened=True,
        date=date,
        purchase_type=None,
        db_mentions=None,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def message(post_id, date=DAY1, **changes):
    values = dict(
        id=post_id,
        db_text=f"message {post_id}",
        price=0,
        paid=False,
        archived=False,
        date=date,
        fromuser=ONE,
        group_id=None,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def story(post_id, date=DAY1, **changes):
    values = dict(
        id=post_id,
        db_text=None,
        title=f"story {post_id}",
        price=0,
        paid=False,
        archived=False,
        date=date,
        responsetype="stories",
        highlight_id=None,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def item(media_id, post_id, area="timeline", kind="images", date=DAY1, **changes):
    values = dict(
        id=media_id,
        post_id=post_id,
        link=f"https://example.com/{media_id}",
        responsetype=area,
        mediatype=kind,
        preview=0,
        linked=None,
        date=date,
        postdate=date,
        duration_string=None,
        canview=True,
    )
    values.update(changes)
    return SimpleNamespace(**values)


def plain(value, key=None):
    """A result as plain data, the same from either engine: rows as dicts,
    sets and lists in one order, dates as one moment in UTC."""
    if hasattr(value, "keys") and not isinstance(value, dict):
        value = dict(value)
    if isinstance(value, dict):
        return {str(k): plain(v, k) for k, v in sorted(value.items(), key=repr)}
    if isinstance(value, tuple):
        return [plain(v) for v in value]
    if isinstance(value, (list, set, frozenset)):
        return sorted((plain(v) for v in value), key=repr)
    if isinstance(value, arrow.Arrow):
        return value.to("UTC").isoformat()
    if key in DATE_KEYS and isinstance(value, str) and value:
        return arrow.get(value).to("UTC").isoformat()
    if isinstance(value, bool):
        return int(value)
    return value


async def scenario():
    """Returns {what was read: the result}."""
    out = {}
    one = dict(model_id=ONE, username=NAMES[ONE])
    two = dict(model_id=TWO, username=NAMES[TWO])

    # --- names, and the one a deleted account goes by (#643) ---
    clock = Clock()
    placeholder = profile.placeholder_names(ONE)[1]
    with mock.patch.object(profile, "_now", clock):
        await operations.table_init_create(**one)
        # no name of creator two has a date: the name is the one used before
        record_names(OLD_NAMES, **two)
        out["name without dates is the one used before"] = (
            await profile.get_profile_info(**two) == name_before_the_dates(**two)
        )
        clock.later(minutes=5)
        # a second start for creator one changes nothing
        for who in (two, one):
            await operations.table_init_create(**who)
        # nor does one for creator two minutes later: a run starts a creator
        # more than once, and a name's date is then left as it is
        clock.later(minutes=5)
        await operations.table_init_create(**two)
        out["profile name two"] = await profile.get_profile_info(**two)
        await profile.write_profile_table(model_id=ONE, username="renamed_one")
        out["profile name"] = await profile.get_profile_info(**one)
        # back under the first name minutes later: it is dated all the same,
        # and is the one seen last again
        clock.later(minutes=5)
        await operations.table_init_create(**one)
        out["profile name, renamed back"] = await profile.get_profile_info(**one)
        # the placeholder of a deleted account gets a row, and no date
        await profile.write_profile_table(model_id=ONE, username=placeholder)
        out["profile name, with a placeholder"] = await profile.get_profile_info(**one)
        # a name recorded before the dates is seen again
        clock.later(days=2)
        await profile.write_profile_table(model_id=TWO, username=OLD_NAMES[0])
        out["profile name two, an old name seen"] = await profile.get_profile_info(**two)
    out["profile of nobody"] = await profile.get_profile_info(model_id=999, username="x")
    out["profile table"] = await profile.check_profile_table_exists(**one)
    out["flags"] = sorted(others.get_schema_changes(**one))
    out["site flag"] = others.get_site_flag(**one)

    # --- posts: post 10 belongs to both creators ---
    await posts.make_post_table_changes(
        [
            post(10),
            post(11, date=DAY2, paid=True, price=4.99, archived=True),
            post(12, date=DAY3_OFFSET, stream=True, pinned=True, price=5),
            post(BIG, date=None, opened=False, db_text="quote ' percent % question ?"),
        ],
        from_api=True,
        **one,
    )
    await posts.make_post_table_changes([post(10), post(22, date=DAY2)], **two)
    # seen again: the missing fields are filled in, and nothing is added twice
    await posts.make_post_table_changes(
        [post(10, purchase_type="tip", db_mentions="@someone"), post(11)],
        from_api=True,
        **one,
    )
    await posts.mark_post_as_deleted([11, 12], **one)
    await posts.unmark_post_as_deleted([12], **one)
    for name, who in (("one", one), ("two", two)):
        out[f"post ids {name}"] = await posts.get_all_post_ids(**who)
        out[f"timeline posts {name}"] = await posts.get_timeline_posts_info(**who)
        out[f"archived posts {name}"] = await posts.get_archived_post_info(**who)
        out[f"stream posts {name}"] = await posts.get_streams_post_info(**who)
        out[f"deleted posts {name}"] = await posts.get_deleted_post_ids(**who)

    # --- messages ---
    await messages.make_messages_table_changes(
        [message(30), message(31, date=DAY2, paid=True, price=12.5)], from_api=True, **one
    )
    await messages.make_messages_table_changes([message(30, fromuser=TWO)], **two)
    await messages.make_messages_table_changes(
        [message(30, group_id="group-7"), message(32, date=DAY3_OFFSET, archived=True)],
        from_api=True,
        **one,
    )
    await messages.mark_message_as_deleted([31], **one)
    for name, who in (("one", one), ("two", two)):
        out[f"message ids {name}"] = await messages.get_all_messages_ids(**who)
        out[f"message info {name}"] = await messages.get_messages_post_info(**who)
        out[f"deleted messages {name}"] = await messages.get_deleted_messages_ids(**who)
    await messages.unmark_message_as_deleted([31], **one)
    out["deleted messages after"] = await messages.get_deleted_messages_ids(**one)

    # --- stories and labels ---
    await stories.make_stories_table_changes(
        [story(40), story(41, responsetype="highlights", date=DAY2), story(42, responsetype="timeline")],
        **one,
    )
    await stories.make_stories_table_changes([story(40)], **two)
    await stories.make_stories_table_changes([story(40), story(43)], **one)
    out["story ids one"] = await stories.get_all_stories_ids(**one)
    out["story ids two"] = await stories.get_all_stories_ids(**two)
    # a label's id can be a word
    await labels.write_labels_table(
        SimpleNamespace(label_id="archived", name="Archived", type="archived"),
        [post(11)],
        **one,
    )
    out["label posts, a word for an id"] = await labels.get_all_labels_posts(
        SimpleNamespace(label_id="archived"), **one
    )
    label = SimpleNamespace(label_id=7, name="favourites", type="custom")
    await labels.write_labels_table(label, [post(10), post(11)], **one)
    await labels.update_labels_table(
        SimpleNamespace(label_id=7, name="renamed", type="custom"), [post(10)], **one
    )
    await labels.write_labels_table(label, [post(10)], **two)
    out["label posts one"] = await labels.get_all_labels_posts(label, **one)
    out["label posts two"] = await labels.get_all_labels_posts(label, **two)
    out["label posts none"] = await labels.get_all_labels_posts(
        SimpleNamespace(label_id=8), **one
    )

    # --- media: media 1 of post 10 belongs to both creators ---
    await media.batch_mediainsert(
        [
            item(1, 10),
            item(2, 11, area="archived", kind="videos", date=DAY2, duration_string="0:01:05"),
            item(3, 12, area="streams", kind="videos", date=DAY3_OFFSET, canview=False),
            item(4, 30, area="messages", kind="audios", preview=1, linked=1),
            item(5, 40, area="stories", date=None),
            item(6, 41, area="highlights"),
            item(7, 10, area="pinned"),
            item(BIG + 1, BIG, link=None),
        ],
        **one,
    )
    await media.batch_mediainsert([item(1, 10), item(8, 22)], **two)
    # a profile picture: its ids are hashes, not numbers
    await media.batch_mediainsert([item(AVATAR, AVATAR_POST, area="Profile")], **one)
    await media.mark_media_as_downloaded(
        item(AVATAR, AVATAR_POST, area="Profile"), filename="avatar.jpg",
        directory="/files", downloaded=True, hashdata="face", size=9, **one,
    )
    out["previous download, a profile picture"] = await media.prev_download_media_data(
        item(AVATAR, AVATAR_POST, area="Profile"), **one
    )
    # seen again: updated in place
    await media.batch_mediainsert([item(1, 10, link="https://example.com/new")], **one)
    await media.mark_media_as_downloaded(
        item(1, 10), filename="a.jpg", directory="/files", downloaded=True,
        hashdata="same", size=5, **one,
    )
    await media.mark_media_as_downloaded(
        item(7, 10, area="pinned"), filename="b.jpg", directory="/files",
        downloaded=1, hashdata="same", size=5, **one,
    )
    await media.mark_media_as_downloaded(
        item(2, 11, area="archived", kind="videos"), filename="c.mp4",
        directory="/files", downloaded=True, hashdata="other", size=BIG, **one,
    )
    # a size limit skipped it for good
    await media.mark_media_as_downloaded(
        item(4, 30, area="messages", kind="audios"), downloaded=True,
        skip_permanent=True, **one,
    )
    await media.mark_media_as_downloaded(
        item(8, 22), filename="d.jpg", directory="/two", downloaded=True,
        hashdata="same", size=5, **two,
    )
    media.batch_set_media_downloaded([{"media_id": 6}], **one)

    out["previous download"] = await media.prev_download_media_data(item(1, 10), **one)
    out["previous download, none"] = await media.prev_download_media_data(
        item(999, 10), **one
    )
    out["downloaded, every creator"] = media.get_media_ids_downloaded(**one)
    out["downloaded, every creator, no skips"] = media.get_media_ids_downloaded(
        without_permanent_skips=True, **one
    )
    out["downloaded pairs, every creator"] = media.get_media_post_ids_downloaded(
        model_only=False, **one
    )
    for name, who in (("one", one), ("two", two)):
        out[f"media ids {name}"] = await media.get_media_ids(**who)
        out[f"media pairs {name}"] = media.get_media_post_ids(**who)
        out[f"downloaded {name}"] = await media.get_media_ids_downloaded_model(**who)
        out[f"downloaded sync {name}"] = media.get_media_ids_downloaded_model_sync(
            without_permanent_skips=True, **who
        )
        out[f"downloaded pairs {name}"] = media.get_media_post_ids_downloaded(
            model_only=True, without_permanent_skips=True, **who
        )
        out[f"downloaded files {name}"] = {
            repr(key): value
            for key, value in media.get_media_post_files_downloaded(**who).items()
        }
        out[f"unlocked {name}"] = await media.get_unlocked_media_ids(**who)
        out[f"permanent skips {name}"] = await media.get_permanent_skip_media_ids(
            model_id=who["model_id"]
        )
        out[f"status {name}"] = await media.get_model_media_status(**who)
        out[f"all media {name}"] = await media.get_all_medias(**who)
        out[f"all media sync {name}"] = media.get_all_medias_sync(**who)
        out[f"post info {name}"] = media.get_post_info(**who)
        for area in ("timeline", "archived", "pinned", "stories", "highlights", "streams", "messages"):
            read = getattr(media, f"get_{area}_media")
            out[f"{area} media {name}"] = await read(**who)
    out["oldest message"] = await messages.get_oldest_message_date(**one)
    out["newest message"] = await messages.get_newest_message_date(**one)
    out["oldest archived"] = await posts.get_oldest_archived_date(**one)
    out["youngest streams"] = await posts.get_youngest_streams_date(**one)
    out["oldest timeline"] = await posts.get_oldest_timeline_date(**one)
    out["youngest timeline"] = await posts.get_youngest_timeline_date(**one)
    out["skips unmarked"] = await media.unmark_permanent_skips([1, 4, 8], model_id=ONE)
    out["permanent skips after"] = await media.get_permanent_skip_media_ids(model_id=ONE)
    out["status after"] = await media.get_model_media_status(**one)
    # every row of every table, read back whole. A row's id is given as its
    # place in line: PostgreSQL skips a number for an insert that found its
    # row already there, so only the order is the same on both
    for table in TABLES:
        rows = table_rows(table, read_only=True, **one)
        if rows and "id" in rows[0]:
            rows.sort(key=lambda row: row["id"])
            rows = [dict(row, id=place) for place, row in enumerate(rows, start=1)]
        out[f"table {table}"] = rows
    return {name: plain(value) for name, value in out.items()}


def check(result):
    """What the scenario must give on any engine."""
    assert result["name without dates is the one used before"] in (True, 1)
    assert result["profile name two"] == "creator_two"
    assert result["profile name"] == "renamed_one"
    assert result["profile name, renamed back"] == "creator_one"
    assert result["profile name, with a placeholder"] == "creator_one"
    assert result["profile name two, an old name seen"] == OLD_NAMES[0]
    seen = {
        (row["user_id"], row["username"]): (row["first_seen_at"], row["last_seen_at"])
        for row in result["table profiles"]
    }
    assert seen == {
        # first seen at the start; the second start five minutes later
        # changed nothing; last seen when the creator was renamed back
        (ONE, "creator_one"): (START, after_start(minutes=15)),
        (ONE, "renamed_one"): (after_start(minutes=10),) * 2,
        (ONE, profile.placeholder_names(ONE)[1]): (None, None),
        # started again five minutes after: not written again
        (TWO, "creator_two"): (after_start(minutes=5),) * 2,
        # recorded before the dates: when it was first seen isn't known
        (TWO, OLD_NAMES[0]): (None, after_start(days=2, minutes=15)),
        (TWO, OLD_NAMES[1]): (None, None),
        (TWO, OLD_NAMES[2]): (None, None),
    }
    assert result["profile of nobody"] is None
    assert result["profile table"] in (True, 1)
    assert result["post ids one"] == [10, 11, 12, BIG]
    assert result["post ids two"] == [10, 22]
    assert result["deleted posts one"] == [11]
    assert result["message ids one"] == [30, 31, 32]
    assert result["message ids two"] == [30]
    assert result["deleted messages one"] == [31]
    assert result["deleted messages after"] == []
    assert result["story ids one"] == [40, 41, 43]
    assert result["story ids two"] == [40]
    assert result["label posts one"] == [10, 11]
    assert result["label posts two"] == [10]
    assert result["label posts none"] == []
    assert result["media ids one"] == [AVATAR, 1, 2, 3, 4, 5, 6, 7, BIG + 1]
    assert result["media ids two"] == [1, 8]
    assert result["downloaded, every creator"] == [AVATAR, 1, 2, 4, 7, 8]
    assert result["downloaded, every creator, no skips"] == [AVATAR, 1, 2, 7, 8]
    assert result["downloaded one"] == [AVATAR, 1, 2, 4, 7]
    assert result["downloaded two"] == [8]
    assert result["permanent skips one"] == [4]
    assert result["skips unmarked"] == 1
    assert result["permanent skips after"] == []
    assert result["previous download"]["size"] == 5
    assert result["previous download, none"] is None
    # a creator's own posts, messages and stories only
    assert sorted(result["post info one"], key=int) == [
        "10", "11", "12", "30", "31", "32", "40", "41", "43", str(BIG)
    ]
    assert sorted(result["post info two"], key=int) == ["10", "22", "30", "40"]
    assert result["post info one"]["11"] == {"price": 4.99, "text": "text of 11"}
    assert result["post info one"]["31"] == {"price": 12.5, "text": "message 31"}
    assert result["post info one"]["40"] == {"price": 0, "text": "story 40"}
    assert result["all media sync one"] == result["all media one"]
    assert result["all media sync two"] == result["all media two"]
    big = [row for row in result["all media one"] if row["media_id"] == BIG + 1]
    assert big and big[0]["post_id"] == BIG
    saved = {(row["model_id"], row["post_id"]): row for row in result["table posts"]}
    assert len(saved) == 6
    assert saved[ONE, 11]["price"] == 4.99 and saved[ONE, 11]["paid"] == 1
    assert saved[ONE, 11]["archived"] == 1 and saved[ONE, 11]["is_deleted"] == 1
    assert saved[ONE, 12]["price"] == 5 and type(saved[ONE, 12]["price"]) is int
    assert saved[ONE, 12]["created_at"] == "2024-03-05T06:30:00+00:00"
    assert saved[ONE, 10]["purchase_type"] == "tip"
    assert saved[ONE, 10]["mentions"] == "@someone"
    assert saved[TWO, 10]["purchase_type"] is None
    assert saved[ONE, BIG]["created_at"] is None
    assert saved[ONE, BIG]["text"] == "quote ' percent % question ?"
    assert saved[ONE, BIG]["opened"] == 0
    texts = {(row["model_id"], row["post_id"]): row for row in result["table messages"]}
    assert texts[ONE, 30]["group_id"] == "group-7" and texts[TWO, 30]["group_id"] is None
    assert texts[ONE, 31]["price"] == 12.5
    assert sorted(row["name"] for row in result["table labels"]) == ["Archived"] + ["favourites"] * 2 + ["renamed"]
    assert result["label posts, a word for an id"] == [11]
    assert result["table models"] and len(result["table profiles"]) == 7
    assert len(result["table medias"]) == 11
    # ids come back as they went in: numbers as numbers, a hash as text
    assert [AVATAR, AVATAR_POST] in result["media pairs one"]
    assert [1, 10] in result["media pairs one"]
    assert result["previous download, a profile picture"]["filename"] == "avatar.jpg"
    assert result["table others"] == [] and result["table products"] == []
