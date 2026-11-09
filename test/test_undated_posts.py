"""Posts and messages with no date don't stop scans or crash the media filters (#369)."""

import asyncio
import pathlib
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.classes.placeholder as placeholder
import ofscraper.commands.check as check
import ofscraper.classes.of.media as media_
import ofscraper.sites.fansly.normalize as normalize
import ofscraper.classes.of.posts as posts_
import ofscraper.data.api.messages as messages
import ofscraper.data.api.timeline as timeline
import ofscraper.filters.media.filters as filters

Y2000 = arrow.get("2000").float_timestamp


class Resp:
    status = 200

    def __init__(self, data):
        self.data = data

    async def json_(self):
        return self.data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class Client:
    """Hands out the given pages in order, then empty ones."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.urls = []

    def requests_async(self, url, **kwargs):
        self.urls.append(url)
        if self.pages and isinstance(self.pages[0], Exception):
            raise self.pages.pop(0)
        return Resp(self.pages.pop(0) if self.pages else {"list": [], "hasMore": False})


class Log:
    def __init__(self):
        self.warnings = []

    def warning(self, msg, *a, **k):
        self.warnings.append(str(msg))

    def debug(self, *a, **k):
        pass

    info = traceback_ = debug


@pytest.fixture
def log(monkeypatch):
    log = Log()
    for module in (timeline, messages):
        monkeypatch.setattr(module, "log", log)

        async def no_mark(**kwargs):
            return None

        monkeypatch.setattr(
            module,
            "mark_message_as_deleted" if module is messages else "mark_post_as_deleted",
            no_mark,
        )
        monkeypatch.setattr(
            module.settings,
            "get_settings",
            lambda: SimpleNamespace(
                before=None, api_cached_disabled=False, mediatypes=None
            ),
        )
    return log


def collect(gen):
    async def run():
        return [x["id"] async for batch in gen for x in batch]

    return asyncio.run(run())


def post(post_id, hour=None):
    item = {"id": post_id}
    if hour is not None:
        item["postedAtPrecise"] = str(1_700_000_000.25 + hour * 3600)
    return item


def message(msg_id, day=None):
    item = {"id": msg_id}
    if day is not None:
        item["createdAt"] = f"2024-03-{day:02d}T10:00:00.250000+00:00"
    return item


# ---------------------------------------------------------------- timeline


def test_timeline_undated_post_keeps_page_and_later_pages(log):
    client = Client(
        [
            {"list": [post(1, 1), post(2), post(3, 2)], "hasMore": True},
            {"list": [post(4, 3)], "hasMore": False},
        ]
    )
    ids = collect(
        timeline.scrape_timeline_posts(client, 1, "u", timestamp=0, is_last_chunk=True)
    )
    assert ids == [1, 2, 3, 4]
    # the next page starts after the newest dated post of the first page
    assert str(1_700_000_000.25 + 2 * 3600) in client.urls[1]
    assert any("post 2" in w and "Timeline" in w for w in log.warnings)


def test_timeline_page_crossing_before_keeps_undated_post(log, monkeypatch):
    before = 1_700_000_000.25 + 2.5 * 3600
    monkeypatch.setattr(
        timeline.settings, "get_settings", lambda: SimpleNamespace(before=before)
    )
    client = Client([{"list": [post(1, 1), post(2), post(3, 3)], "hasMore": True}])
    ids = collect(
        timeline.scrape_timeline_posts(client, 1, "u", timestamp=0, is_last_chunk=True)
    )
    assert ids == [1, 2]


def test_timeline_page_with_no_dated_post_is_kept_and_logged(log):
    client = Client([{"list": [post(1), post(2)], "hasMore": True}, {"list": [post(3, 1)]}])
    ids = collect(
        timeline.scrape_timeline_posts(client, 1, "u", timestamp=0, is_last_chunk=True)
    )
    # no date to page from, so the scan stops after keeping the page
    assert ids == [1, 2]
    assert len(client.urls) == 1
    assert any("no post on this page has a date" in w for w in log.warnings)


def test_timeline_empty_date_counts_as_undated(log):
    empty = {"id": 2, "postedAtPrecise": ""}
    client = Client([{"list": [post(1, 1), empty, post(3, 2)], "hasMore": False}])
    ids = collect(
        timeline.scrape_timeline_posts(client, 1, "u", timestamp=0, is_last_chunk=True)
    )
    assert ids == [1, 2, 3]
    assert any("post 2 has no date" in w for w in log.warnings)


def test_timeline_worker_error_is_logged(log):
    client = Client([RuntimeError("boom")])
    assert collect(
        timeline.scrape_timeline_posts(client, 1, "u", timestamp=0, is_last_chunk=True)
    ) == []
    assert any("Timeline" in w and "boom" in w for w in log.warnings)


# ---------------------------------------------------------------- messages


def test_messages_undated_message_keeps_page_and_later_pages(log):
    client = Client(
        [
            {"list": [message(5, 20), message(4), message(3, 18)], "hasMore": True},
            {"list": [message(2, 10), message(1, 5)], "hasMore": False},
        ]
    )
    after = arrow.get("2024-03-01").float_timestamp
    ids = collect(messages.scrape_messages(client, 1, "u", is_last_chunk=True, after=after))
    assert ids == [5, 4, 3, 2, 1]
    assert any("message 4" in w and "Messages" in w for w in log.warnings)


def test_messages_after_cutoff_still_applies_with_undated_message(log):
    client = Client(
        [
            {"list": [message(3, 20), message(2), message(1, 5)], "hasMore": True},
            {"list": [message(0, 1)], "hasMore": False},
        ]
    )
    after = arrow.get("2024-03-10").float_timestamp
    ids = collect(messages.scrape_messages(client, 1, "u", is_last_chunk=True, after=after))
    # message 1 is before the cutoff, which ends the scan; the undated one stays
    assert ids == [3, 2]
    assert len(client.urls) == 1


def test_messages_empty_date_counts_as_undated(log):
    empty = {"id": 2, "createdAt": "", "postedAt": ""}
    client = Client([{"list": [message(3, 20), empty, message(1, 18)], "hasMore": False}])
    ids = collect(messages.scrape_messages(client, 1, "u", is_last_chunk=True))
    assert ids == [3, 2, 1]
    assert any("message 2 has no date" in w for w in log.warnings)


def test_messages_worker_error_is_logged(log):
    client = Client([RuntimeError("boom")])
    assert collect(messages.scrape_messages(client, 1, "u", is_last_chunk=True)) == []
    assert any("Messages" in w and "boom" in w for w in log.warnings)


# ---------------------------------------------------------------- media filters


def make_media(post_id, date):
    raw = {
        "id": post_id,
        "text": "t",
        "price": 0,
        "isOpened": True,
        "responseType": "post",
        "media": [],
    }
    if date:
        raw["postedAt"] = date
    return media_.Media(
        {"id": post_id * 10, "type": "photo", "canView": True},
        0,
        posts_.Post(raw, 1, "u"),
    )


MIXED = [
    make_media(1, "2024-03-01T00:00:00+00:00"),
    make_media(2, None),
    make_media(3, "2024-01-01T00:00:00+00:00"),
]


def test_sort_by_date_puts_undated_first():
    assert [m.post_id for m in filters.sort_by_date(MIXED)] == [2, 3, 1]


def test_dupefiltermedia_with_undated_media():
    assert sorted(m.post_id for m in filters.dupefiltermedia(MIXED)) == [1, 2, 3]


def test_previous_download_filter_with_undated_media(monkeypatch):
    monkeypatch.setattr(
        filters.settings, "get_settings", lambda: SimpleNamespace(force_all=True)
    )
    assert [m.post_id for m in filters.previous_download_filter(MIXED)] == [2, 3, 1]


def test_dated_media_order_unchanged():
    dated = [m for m in MIXED if m.post.date]
    assert filters.sort_by_date(dated) == sorted(dated, key=lambda x: x.date)


# ---------------------------------------------------------------- check table


def check_rows(monkeypatch, media):
    collection = SimpleNamespace(all_media=media, posts_with_media_id=lambda _id: [])
    log = Log()
    monkeypatch.setattr(check, "log", log)
    monkeypatch.setattr(check, "get_media_post_ids_downloaded", lambda **kw: [])
    monkeypatch.setattr(check, "check_user_dict", {"1": {"collection": collection}})
    monkeypatch.setattr(check, "ROWS", [])
    asyncio.run(check.row_gather("u", 1))
    return check.ROWS, log


def test_check_table_with_undated_media(monkeypatch):
    rows, log = check_rows(monkeypatch, MIXED)
    # newest first, undated last as the oldest
    assert [row["post_id"] for row in rows] == [1, 3, 2]
    assert rows[2]["post_date"] == "Probably Deleted"
    assert any("media 20 in post 2 has no date" in w for w in log.warnings)


def test_check_table_warns_for_undated_post_with_dated_media(monkeypatch):
    raw = {"id": 7, "text": "t", "price": 0, "isOpened": True, "responseType": "post"}
    media = media_.Media(
        {"id": 70, "type": "photo", "canView": True, "createdAt": "2024-02-01T00:00:00+00:00"},
        0,
        posts_.Post(raw, 1, "u"),
    )
    rows, log = check_rows(monkeypatch, [media])
    assert rows[0]["post_date"] == "Probably Deleted"
    assert any("media 70 in post 7 has no date" in w for w in log.warnings)


def test_check_table_dated_order_unchanged(monkeypatch):
    rows, log = check_rows(monkeypatch, [m for m in MIXED if m.post.date])
    assert [row["post_id"] for row in rows] == [1, 3]
    assert [row["post_date"] for row in rows] == [
        "2024-03-01 00:00:00",
        "2024-01-01 00:00:00",
    ]
    assert log.warnings == []


# ---------------------------------------------------------------- timeline after


@pytest.fixture
def after_env(monkeypatch):
    state = SimpleNamespace(media=[], youngest=None)

    async def media(**kwargs):
        return state.media

    async def nothing(**kwargs):
        return set()

    async def youngest(**kwargs):
        return state.youngest

    monkeypatch.setattr(timeline, "get_after_pre_checks", lambda *a: None)
    monkeypatch.setattr(timeline, "get_timeline_media", media)
    monkeypatch.setattr(timeline, "get_media_ids_downloaded_model", nothing)
    monkeypatch.setattr(timeline, "get_deleted_post_ids", nothing)
    monkeypatch.setattr(timeline, "get_youngest_timeline_date", youngest)
    monkeypatch.setattr(
        timeline.settings, "get_settings", lambda: SimpleNamespace(mediatypes=None)
    )
    return state


def row(media_id, posted_at, downloaded=0):
    # get_timeline_media returns posted_at as an Arrow, 1970 when undated
    return {
        "media_id": media_id,
        "post_id": media_id,
        "downloaded": downloaded,
        "unlocked": 1,
        "media_type": "Images",
        "posted_at": arrow.get(posted_at),
    }


def test_after_falls_back_when_oldest_missing_media_is_undated(after_env):
    after_env.media = [row(1, 0), row(2, "2024-01-01T00:00:00.25+00:00")]
    assert asyncio.run(timeline.get_after(1, "u")) == Y2000


def test_after_falls_back_when_youngest_media_is_undated(after_env):
    after_env.media = [row(1, 0, downloaded=1)]
    after_env.youngest = arrow.get(0)
    assert asyncio.run(timeline.get_after(1, "u")) == Y2000


def test_after_unchanged_for_dated_media(after_env):
    after_env.media = [
        row(1, "2024-01-01T00:00:00.25+00:00"),
        row(2, "2024-02-01T00:00:00.25+00:00"),
    ]
    expected = arrow.get("2024-01-01T00:00:00.25+00:00").float_timestamp
    assert asyncio.run(timeline.get_after(1, "u")) == expected
    after_env.media = [row(1, "2024-01-01T00:00:00.25+00:00", downloaded=1)]
    after_env.youngest = arrow.get("2024-05-01T00:00:00.25+00:00")
    assert (
        asyncio.run(timeline.get_after(1, "u"))
        == arrow.get("2024-05-01T00:00:00.25+00:00").float_timestamp
    )


# ---------------------------------------------------------------- Fansly normalize


def fansly_response(created=None):
    item = {
        "id": 500,
        "senderId": 9,
        "content": "hi",
        "attachments": [{"contentType": normalize.ACCOUNT_MEDIA, "contentId": 600, "pos": 0}],
    }
    if created is not None:
        item["createdAt"] = created
    account_media = {
        "id": 600,
        "access": True,
        "media": {
            "id": 700,
            "mimetype": "image/jpeg",
            "locations": [{"locationId": "1", "location": "https://example.invalid/a.jpg"}],
        },
    }
    return item, account_media


@pytest.fixture
def fansly_log(monkeypatch):
    log = Log()
    monkeypatch.setattr(normalize, "log", log)
    return log


def test_fansly_undated_message_is_kept_and_logged(fansly_log):
    dated, media = fansly_response(1_700_000_000)
    undated, _ = fansly_response()
    undated["id"] = 501
    found = normalize.messages({"messages": [dated, undated], "accountMedia": [media]})
    assert [m["id"] for m in found] == [500, 501]
    assert found[1]["createdAt"] is None
    assert fansly_log.warnings == ["Fansly: message 501 has no date"]


def test_fansly_undated_post_is_logged(fansly_log):
    post, media = fansly_response()
    found = normalize.posts({"posts": [post], "accountMedia": [media]})
    assert [p["id"] for p in found] == [500]
    assert fansly_log.warnings == ["Fansly: post 500 has no date"]


def test_fansly_dated_items_log_nothing(fansly_log):
    item, media = fansly_response(1_700_000_000)
    normalize.posts({"posts": [item], "accountMedia": [media]})
    normalize.messages({"messages": [item], "accountMedia": [media]})
    assert fansly_log.warnings == []


# ---------------------------------------------------------------- file and folder names


async def _none():
    return None


@pytest.fixture
def names_env(monkeypatch, tmp_path):
    log = Log()
    log.trace = log.debug
    monkeypatch.setattr(placeholder, "log", log)
    monkeypatch.setattr(placeholder.me, "parse_user", lambda: ("1", "me"))
    monkeypatch.setattr(placeholder.me, "get_id", lambda: 1)
    monkeypatch.setattr(placeholder.profile_data, "get_active_profile", lambda: "main_profile")
    monkeypatch.setattr(placeholder.common_paths, "get_config_home", lambda: tmp_path / "cfg")
    monkeypatch.setattr(
        placeholder.common_paths, "get_save_location", lambda *a, **k: str(tmp_path / "data")
    )
    monkeypatch.setattr(placeholder.config_file, "open_config", lambda: {})
    monkeypatch.setattr(placeholder.settings, "get_args", lambda: SimpleNamespace())
    monkeypatch.setattr(
        placeholder.manager,
        "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(get_model=lambda _u: None)),
    )
    monkeypatch.setattr(placeholder, "naming_script", lambda *a, **k: _none())
    monkeypatch.setattr(placeholder.data, "get_date", lambda *a, **k: "YYYY-MM-DD")
    monkeypatch.setattr(placeholder.data, "get_dirformat", lambda *a, **k: "{date}")
    monkeypatch.setattr(placeholder.data, "get_fileformat", lambda *a, **k: "{date}_{post_id}.{ext}")
    return log


def names(item, cls=placeholder.Placeholders):
    holder = cls(item, "jpg")
    folder = asyncio.run(holder.getmediadir(create=False))
    return pathlib.Path(folder).name, asyncio.run(holder.createfilename())


def of_media(post_date=None, media_date=None):
    raw = {"id": 7, "text": "t", "price": 0, "isOpened": True, "responseType": "post"}
    if post_date:
        raw["postedAt"] = post_date
    media = {"id": 70, "type": "photo", "canView": True,
             "files": {"full": {"url": "https://example.invalid/a.jpg"}}}
    if media_date:
        media["createdAt"] = media_date
    raw["media"] = [media]
    return posts_.Post(raw, 1, "u", "timeline").all_media[0]


def test_names_unchanged_for_dated_post(names_env):
    item = of_media("2024-05-01T20:00:00+00:00", "2024-04-01T00:00:00+00:00")
    assert names(item) == ("2024-05-01", "2024-05-01_7.jpg")
    assert names_env.warnings == []


def test_names_use_media_date_when_post_is_undated(names_env):
    item = of_media(None, "2024-04-01T00:00:00+00:00")
    assert names(item) == ("2024-04-01", "2024-04-01_7.jpg")
    assert any("Post 7 (media 70) has no date, using its media date" in w
               for w in names_env.warnings)


def test_names_use_1970_when_nothing_is_dated(names_env):
    item = of_media()
    assert names(item) == ("1970-01-01", "1970-01-01_7.jpg")
    assert any("Post 7 (media 70) has no date, using 1970-01-01" in w
               for w in names_env.warnings)


def test_names_for_undated_fansly_post(names_env, fansly_log):
    post, media = fansly_response()
    (raw,) = normalize.posts({"posts": [post], "accountMedia": [media]})
    item = posts_.Post(raw, 1, "u", "timeline").all_media[0]
    assert names(item) == ("1970-01-01", "1970-01-01_500.jpg")
    assert any("Post 500 (media 700) has no date" in w for w in names_env.warnings)


def test_text_names_for_undated_post(names_env):
    raw = {"id": 8, "text": "hello", "price": 0, "isOpened": True, "responseType": "post"}
    folder, file_name = names(posts_.Post(raw, 1, "u", "timeline"), placeholder.Textholders)
    assert (folder, file_name) == ("1970-01-01", "1970-01-01_8.jpg")
    assert any("Post 8 has no date, using 1970-01-01" in w for w in names_env.warnings)


# ---------------------------------------------------------------- warned once per file (#375)


def download_names(item, tmp_path, monkeypatch):
    """Build the names a download builds: the temporary folder, then the
    final folder and file name."""
    monkeypatch.setattr(placeholder.data, "get_TempDir", lambda *a, **k: str(tmp_path / "temp"))

    async def run():
        temp = await placeholder.tempFilePlaceholder(item, "x.part").init()
        final = await placeholder.Placeholders(item, "jpg").init()
        return temp.tempfilepath, final.filepath

    return asyncio.run(run())


def no_date_warnings(log):
    return [w for w in log.warnings if "has no date" in w]


def test_undated_file_is_warned_once(names_env, tmp_path, monkeypatch):
    item = of_media()
    _, final = download_names(item, tmp_path, monkeypatch)
    assert final.name == "1970-01-01_7.jpg"
    assert no_date_warnings(names_env) == [
        "Post 7 (media 70) has no date, using 1970-01-01 for {date} in its file and folder names"
    ]
    # building the names again for the same file adds nothing
    download_names(item, tmp_path, monkeypatch)
    assert len(no_date_warnings(names_env)) == 1


def test_each_undated_file_is_warned_once(names_env, tmp_path, monkeypatch):
    raw = {"id": 9, "text": "t", "price": 0, "isOpened": True, "responseType": "post",
           "media": [{"id": mid, "type": "photo", "canView": True,
                      "files": {"full": {"url": f"https://example.invalid/{mid}.jpg"}}}
                     for mid in (91, 92)]}
    for item in posts_.Post(raw, 1, "u", "timeline").all_media:
        download_names(item, tmp_path, monkeypatch)
    warnings = no_date_warnings(names_env)
    assert len(warnings) == 2
    assert any("(media 91)" in w for w in warnings)
    assert any("(media 92)" in w for w in warnings)


def test_undated_text_file_is_warned_once(names_env):
    raw = {"id": 8, "text": "hello", "price": 0, "isOpened": True, "responseType": "post"}
    asyncio.run(placeholder.Textholders(posts_.Post(raw, 1, "u", "timeline"), "txt").init())
    assert no_date_warnings(names_env) == [
        "Post 8 has no date, using 1970-01-01 for {date} in its file and folder names"
    ]


def test_dated_file_logs_nothing(names_env, tmp_path, monkeypatch):
    item = of_media("2024-05-01T20:00:00+00:00")
    _, final = download_names(item, tmp_path, monkeypatch)
    assert final.name == "2024-05-01_7.jpg"
    assert names_env.warnings == []
