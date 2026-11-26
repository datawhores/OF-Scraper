"""Media the post filters leave out is reported once per creator, by setting."""

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


def item(item_id, text, kinds=("photo",)):
    return {
        "id": item_id, "text": text, "price": 0, "isOpened": True,
        "postedAt": "2024-05-01T10:00:00+00:00", "createdAt": "2024-05-01T10:00:00+00:00",
        "media": [
            {"id": item_id * 10 + n, "type": kind, "canView": True,
             "createdAt": "2024-05-01T10:00:00+00:00",
             "files": {"full": {"url": f"https://cdn.example/{item_id}/{n}"}}}
            for n, kind in enumerate(kinds)
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


def collect(items):
    collection = PostCollection(model_id=MODEL_ID, username=USERNAME)
    collection.add_posts(
        [posts_.Post(i, MODEL_ID, USERNAME, "Timeline") for i in items], actions=["download"]
    )
    return collection


def skip_lines(caplog):
    return [r.getMessage() for r in caplog.records if "media left out" in r.getMessage()]


AGAIN = " (--force-all downloads them again, or manual --url for one post)"


def test_media_left_out_by_block_ads_is_reported(run_with, caplog):
    run_with("--block-ads")
    collection = collect([
        item(1, "new set"),
        item(2, "huge giveaway", kinds=("photo", "video")),
        item(3, "#ad go follow her"),
    ])
    with caplog.at_level(logging.INFO):
        media = collection.get_media_to_download()
    assert [m.id for m in media] == [10]
    assert skip_lines(caplog) == [
        "[a_creator] 3 media left out: 3 by --neg-filter or block_ads"
    ]


def test_each_setting_is_named_with_its_own_count(run_with, caplog):
    run_with("--mediatype", "Images", "--filter", "keep")
    collection = collect([
        item(1, "keep this", kinds=("photo", "video")),  # the video: --mediatype
        item(2, "not this"),  # --filter
        item(3, "keep too"),
    ])
    with caplog.at_level(logging.INFO):
        media = collection.get_media_to_download()
    assert sorted(m.id for m in media) == [10, 30]
    assert skip_lines(caplog) == [
        "[a_creator] 2 media left out: "
        "1 by --mediatype or download_options.filter, 1 by --filter"
    ]


def test_nothing_is_reported_when_nothing_is_left_out(run_with, caplog):
    run_with()
    with caplog.at_level(logging.INFO):
        assert len(collect([item(1, "a"), item(2, "b")]).get_media_to_download()) == 2
    assert skip_lines(caplog) == []


def test_the_report_counts_each_media_once(run_with, caplog):
    run_with("--block-ads")
    collection = collect([item(1, "#ad"), item(2, "fine")])
    with caplog.at_level(logging.INFO):
        collection.get_media_to_download()
        collection.get_media_to_download()  # e.g. the ordered Fansly path asks again
        collection.log_left_out()
    assert skip_lines(caplog) == [
        "[a_creator] 1 media left out: 1 by --neg-filter or block_ads"
    ]


def test_media_left_out_as_already_downloaded_is_counted(run_with, monkeypatch, caplog):
    run_with("--block-ads")
    # the database says the first post's photo is downloaded
    monkeypatch.setattr(filters, "downloaded_media_ids", lambda **k: {10})
    collection = collect([item(1, "new set"), item(2, "#ad"), item(3, "more")])
    with caplog.at_level(logging.INFO):
        media = collection.get_media_to_download()
    assert [m.id for m in media] == [30]
    assert skip_lines(caplog) == [
        "[a_creator] 2 media left out: 1 already downloaded, 1 by --neg-filter or block_ads"
        + AGAIN
    ]


def test_already_downloaded_alone_is_reported(run_with, monkeypatch, caplog):
    run_with()
    monkeypatch.setattr(filters, "downloaded_media_ids", lambda **k: {10, 20})
    with caplog.at_level(logging.INFO):
        assert collect([item(1, "a"), item(2, "b")]).get_media_to_download() == []
    assert skip_lines(caplog) == ["[a_creator] 2 media left out: 2 already downloaded" + AGAIN]


def test_force_all_leaves_nothing_out_as_downloaded(run_with, monkeypatch, caplog):
    run_with("--force-all")
    # --force-all: downloaded_media_ids skips the database
    monkeypatch.setattr(filters, "downloaded_media_ids", lambda **k: None)
    with caplog.at_level(logging.INFO):
        assert len(collect([item(1, "a")]).get_media_to_download()) == 1
    assert skip_lines(caplog) == []


def test_metadata_run_hint_says_force_all_checks_them_again(run_with, monkeypatch, caplog):
    merged = run_with()
    merged.command = "metadata"  # the metadata command downloads nothing
    monkeypatch.setattr(filters, "downloaded_media_ids", lambda **k: {10})
    collection = PostCollection(model_id=MODEL_ID, username=USERNAME)
    collection.add_posts(
        [posts_.Post(i, MODEL_ID, USERNAME, "Timeline") for i in [item(1, "a"), item(2, "b")]],
        actions=["metadata"],
    )
    with caplog.at_level(logging.INFO):
        assert [m.id for m in collection.get_media_for_processing()] == [20]
    assert skip_lines(caplog) == [
        "[a_creator] 1 media left out: 1 already downloaded"
        " (--force-all updates their metadata too)"
    ]
