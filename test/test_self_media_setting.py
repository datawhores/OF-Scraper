"""The FILTER_SELF_MEDIA setting decides whether the media in messages the
account sent is downloaded. It is on by default: that media is skipped. With
it off the media goes through like the creator's own."""

import pytest

import ofscraper.filters.media.filters as filters
import ofscraper.utils.me as me_util
import ofscraper.utils.of_env.of_env as of_env
from ofscraper.classes.of.posts import Post

MODEL_ID = 1001
MY_ID = 2002
NAME = "a creator"


def message(post_id, sender, media_ids):
    item = {
        "id": post_id,
        "text": f"message {post_id}",
        "price": 0,
        "createdAt": "2024-08-01T10:00:00+00:00",
        "fromUser": {"id": sender},
        "media": [
            {
                "id": media_id,
                "type": "photo",
                "canView": True,
                "files": {"full": {"url": f"https://cdn.example/{media_id}.jpg"}},
            }
            for media_id in media_ids
        ],
    }
    return Post(item, MODEL_ID, NAME, "Messages")


def to_download(posts):
    """What the download run keeps of these posts' media: each post's own
    list, then the filter the run applies to the whole list."""
    media = [m for post in posts for m in post.media]
    return sorted(m.id for m in filters.seperate_self(media))


@pytest.fixture
def account(monkeypatch):
    monkeypatch.delenv("FILTER_SELF_MEDIA", raising=False)
    monkeypatch.setattr(me_util, "get_id", lambda: MY_ID)


def test_the_setting_is_on_by_default(account):
    assert of_env.getattr("FILTER_SELF_MEDIA") is True


def test_media_in_a_message_the_account_sent_is_skipped_by_default(account):
    posts = [message(1, MODEL_ID, [101, 102]), message(2, MY_ID, [201])]
    assert to_download(posts) == [101, 102]


@pytest.mark.parametrize("value", ["False", "false", "0"])
def test_with_the_setting_off_the_media_the_account_sent_is_kept(
    account, monkeypatch, value
):
    monkeypatch.setenv("FILTER_SELF_MEDIA", value)
    posts = [message(1, MODEL_ID, [101, 102]), message(2, MY_ID, [201])]
    assert to_download(posts) == [101, 102, 201]


def test_with_the_setting_off_a_sent_message_counts_as_having_media(
    account, monkeypatch
):
    # text files are written only for posts with media when a media type is
    # chosen (PostCollection.get_posts_for_text_download)
    sent = message(2, MY_ID, [201])
    assert len(sent.media) == 0
    monkeypatch.setenv("FILTER_SELF_MEDIA", "False")
    assert [m.id for m in sent.media] == [201]


def test_media_the_account_cannot_view_stays_out_with_the_setting_off(
    account, monkeypatch
):
    monkeypatch.setenv("FILTER_SELF_MEDIA", "False")
    sent = message(2, MY_ID, [201])
    sent.post["media"][0]["canView"] = False
    assert sent.media == []
