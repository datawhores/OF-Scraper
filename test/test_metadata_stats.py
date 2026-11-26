"""Metadata stats count media whose metadata wasn't attempted as skipped (#726)."""

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
from ofscraper.classes.of.media import Media
from ofscraper.classes.of.posts import Post
from ofscraper.managers.stats import StatsManager


def _media(media_id, mediatype):
    post = Post(
        {"id": 1, "postedAt": "2026-01-02T03:04:05+00:00", "text": ""},
        12345, "a creator", responsetype="timeline",
    )
    return Media(
        {"id": media_id, "type": mediatype, "canView": True,
         "files": {"full": {"url": f"https://example.invalid/{media_id}.jpg"}}},
        0, post,
    )


def test_metadata_stats_count_unattempted_media_as_skipped(caplog):
    skipped = _media(1, "photo")
    changed = _media(2, "video")
    changed.mark_metadata_changed()
    unchanged = _media(3, "photo")
    unchanged.mark_metadata_unchanged()
    failed = _media(4, "photo")
    failed.mark_metadata_failed()

    manager = StatsManager()
    manager.update_and_print_stats(
        "a creator", "metadata", [skipped, changed, unchanged, failed]
    )

    stats = next(iter(manager._stats["a creator"].values()))
    assert stats.skipped_count == 1
    assert stats.changed_video == stats.unchanged_count == stats.failed_count == 1
    assert "1 skipped" in str(stats)
    assert "1 skipped" in caplog.text


def test_the_run_totals_count_skipped_metadata(caplog):
    manager = StatsManager()
    manager.update_and_print_stats("a creator", "metadata", [_media(1, "photo")])
    manager.update_and_print_stats("another creator", "metadata", [_media(2, "photo")])
    caplog.clear()

    manager.print_global_summary()

    assert "METADATA UPDATES" in caplog.text
    assert "SKIPPED:       2 overall" in caplog.text
