"""The download cap (max_post_count) keeps a creator's newest media (#725)."""

import logging

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.classes.of.posts as posts_
import ofscraper.filters.media.filters as filters
import ofscraper.utils.settings as settings
from ofscraper.managers.postcollection import PostCollection
from ofscraper.utils.args.main import AutoDotDict
from ofscraper.utils.args.parse.commands.main import program

MODEL_ID, USERNAME = 123, "a_creator"


def item(item_id, day):
    date = f"2024-05-{day:02d}T10:00:00+00:00"
    return {
        "id": item_id, "text": "", "price": 0, "isOpened": True,
        "postedAt": date, "createdAt": date,
        "media": [
            {"id": item_id * 10, "type": "photo", "canView": True, "createdAt": date,
             "files": {"full": {"url": f"https://cdn.example/{item_id}"}}}
        ],
    }


@pytest.fixture
def run_with(monkeypatch):
    """Real settings from these command-line options; nothing downloaded yet."""

    def build(*options):
        params, _ = program.main(args=list(options), standalone_mode=False, prog_name="OF-Scraper")
        args = AutoDotDict(params)
        args.command = "OF-Scraper"
        monkeypatch.setattr(settings.read_args, "retriveArgs", lambda *a, **k: args)
        merged = settings.merged_settings()
        monkeypatch.setattr(settings, "get_settings", lambda *a, **k: merged)
        monkeypatch.setattr(filters, "downloaded_media_ids", lambda **k: set())
        # the account running the scraper, which made none of these posts
        monkeypatch.setattr(filters.me_util, "get_id", lambda: 999)
        return merged

    return build


def collect(action="download"):
    # five posts a day apart, given newest first as the API lists them
    collection = PostCollection(model_id=MODEL_ID, username=USERNAME)
    collection.add_posts(
        [posts_.Post(item(i, i), MODEL_ID, USERNAME, "Timeline") for i in (5, 4, 3, 2, 1)],
        actions=[action],
    )
    return collection


def cap_lines(caplog):
    return [r.getMessage() for r in caplog.records if "max_post_count" in r.getMessage()]


def test_the_cap_keeps_the_newest_media(run_with, caplog):
    run_with("--max-post-count", "2")
    with caplog.at_level(logging.INFO):
        media = collect().get_media_to_download()
    assert [m.id for m in media] == [40, 50]
    assert cap_lines(caplog) == [
        "[a_creator] 3 media left out by max_post_count (2): only the newest 2 are kept"
    ]


def test_media_desc_changes_the_order_not_which_media_are_kept(run_with):
    run_with("--max-media-count", "2", "--media-sort", "date", "--media-desc")
    assert [m.id for m in collect().get_media_to_download()] == [50, 40]


def test_the_metadata_command_keeps_the_newest_too(run_with):
    run_with("--max-post-count", "3")
    assert [m.id for m in collect("metadata").get_media_for_metadata()] == [30, 40, 50]


def test_nothing_is_reported_under_the_cap(run_with, caplog):
    run_with("--max-post-count", "5")
    with caplog.at_level(logging.INFO):
        assert len(collect().get_media_to_download()) == 5
    assert cap_lines(caplog) == []


def test_a_negative_cap_is_no_cap(run_with, caplog):
    run_with("--max-post-count", "-2")
    with caplog.at_level(logging.INFO):
        assert len(collect().get_media_to_download()) == 5
    assert cap_lines(caplog) == []


def test_without_a_username_the_line_has_no_name(run_with, caplog):
    run_with("--max-post-count", "4")
    media = collect().all_media
    with caplog.at_level(logging.INFO):
        assert len(filters.ele_count_filter(media)) == 4
    assert cap_lines(caplog) == [
        "1 media left out by max_post_count (4): only the newest 4 are kept"
    ]
