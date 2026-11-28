"""A creator whose subscription isn't active is named before its scan (#767)."""

import asyncio
import contextlib
import logging
from types import SimpleNamespace

import arrow
import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.data.posts.post as post
import ofscraper.utils.settings as settings
from ofscraper.classes.of.models import Model
from ofscraper.sites.fansly import normalize, pipeline

CREATOR_ID, CREATOR = 123, "a_creator"
# skip_unavailable_content (on by default) skips the wall: only messages and
# purchases are scanned
OF_LINE = (
    f"[{CREATOR}] subscription not active: only messages and purchases are scanned"
    " (skip_unavailable_content)"
)
# with it off the wall is scanned too, and its free posts can be downloaded
OF_WALL_LINE = (
    f"[{CREATOR}] subscription not active: only free posts, messages and purchases"
    " can be downloaded"
)
FANSLY_LINE = (
    f"[{CREATOR}] subscription not active: only public posts, follower posts,"
    " messages and purchases can be downloaded"
)


def onlyfans_model(days_left):
    """An OnlyFans creator whose subscription ends ``days_left`` days from now."""
    return Model({
        "id": CREATOR_ID,
        "username": CREATOR,
        "subscribedByData": {
            "status": None,
            "renewedAt": None,
            "subscribes": [],
            "expiredAt": arrow.now().shift(days=days_left).isoformat(),
        },
    })


def fansly_model(subscription):
    """A Fansly creator, normalized as the scan reads it."""
    account = {"id": str(CREATOR_ID), "username": CREATOR, "following": True}
    if subscription:
        account["subscribed"] = True
        account["subscription"] = {
            "price": 5000,
            "endsAt": arrow.now().shift(days=20).int_timestamp * 1000,
        }
    return Model(normalize.model(account))


@pytest.fixture
def site(monkeypatch):
    real = settings.get_settings()

    class Stub(SimpleNamespace):
        def __getattr__(self, name):
            return getattr(real, name)

    stub = Stub(site="onlyfans", skip_unavailable_content=False, command="download", text=False)
    monkeypatch.setattr(settings, "get_settings", lambda *a, **k: stub)
    # no areas: only what is said before the scan is under test
    monkeypatch.setattr(post, "get_final_posts_area", lambda: set())
    monkeypatch.setattr(post, "get_like_area", lambda: set())
    monkeypatch.setattr(post, "get_download_area", lambda: set())
    monkeypatch.setattr(post.progress_utils, "setup_live", lambda *a, **k: contextlib.nullcontext())
    return stub


def notices(caplog):
    return [r.getMessage() for r in caplog.records if "subscription not active" in r.getMessage()]


def scan(ele, caplog):
    with caplog.at_level(logging.INFO):
        asyncio.run(post.process_tasks(CREATOR_ID, CREATOR, ele))
    return notices(caplog)


def test_expired_onlyfans_subscription_is_named(site, caplog):
    site.skip_unavailable_content = True
    assert scan(onlyfans_model(days_left=-30), caplog) == [OF_LINE]


def test_expired_onlyfans_subscription_with_the_wall_scanned(site, caplog):
    assert scan(onlyfans_model(days_left=-30), caplog) == [OF_WALL_LINE]


def test_active_onlyfans_subscription_says_nothing(site, caplog):
    assert scan(onlyfans_model(days_left=20), caplog) == []


def test_fansly_creator_without_a_subscription_is_named(site, caplog):
    site.site = "fansly"
    assert scan(fansly_model(subscription=False), caplog) == [FANSLY_LINE]


def test_fansly_subscriber_says_nothing(site, caplog):
    site.site = "fansly"
    assert scan(fansly_model(subscription=True), caplog) == []


def test_fansly_page_by_page_scan_names_it_too(site, caplog):
    # the Fansly download pipeline picks its areas without process_tasks
    site.site = "fansly"
    with caplog.at_level(logging.INFO):
        pipeline.areas_for(fansly_model(subscription=False), CREATOR)
    assert notices(caplog) == [FANSLY_LINE]
