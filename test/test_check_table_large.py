"""The check table is built in one pass over the creator's media.

row_gather filled each row's "other posts with this media" by calling
collection.posts_with_media_id, which reads collection.all_media again, and
that rebuilds every media object of every post. One rebuild per row made the
table quadratic, so for a creator with about 14,000 items it never finished.
"""

import asyncio
from types import SimpleNamespace

import pytest

import ofscraper.commands.check as check
from ofscraper.managers.postcollection import PostCollection


class _Log:
    def info(self, *a, **k):
        pass

    warning = debug = info


class _CountingCollection(PostCollection):
    """A real PostCollection that counts how often its media list is rebuilt."""

    def __init__(self, posts, max_reads=None):
        super().__init__(model_id=1, username="a creator")
        for post in posts:
            self._posts_map[post.id] = post
        self.all_media_reads = 0
        self.max_reads = max_reads

    @property
    def all_media(self):
        self.all_media_reads += 1
        if self.max_reads is not None and self.all_media_reads > self.max_reads:
            raise AssertionError(
                f"collection.all_media rebuilt {self.all_media_reads} times "
                "for one check table"
            )
        return super().all_media


def _post(post_id, media_ids, day):
    post = SimpleNamespace(id=post_id, post_media=list(media_ids), price=0)
    date = f"2024-01-{day:02d} 00:00:00"
    post.all_media = [
        SimpleNamespace(
            id=media_id,
            post_id=post_id,
            date=date,
            postdate=date,
            formatted_postdate=date,
            canview=True,
            mpd=None,
            url="https://example.invalid/x.jpg",
            _post=post,
            post=SimpleNamespace(db_sanitized_text="t"),
            mediatype="images",
            numeric_duration="N/A",
            responsetype="timeline",
        )
        for media_id in media_ids
    ]
    return post


def _rows(monkeypatch, collection):
    monkeypatch.setattr(check, "log", _Log())
    monkeypatch.setattr(check, "get_media_post_files_downloaded", lambda **kw: {})
    monkeypatch.setattr(check, "build_post_centric_rows", lambda *a, **k: [])
    monkeypatch.setattr(check, "check_user_dict", {"1": {"collection": collection}})
    monkeypatch.setattr(check, "ROWS", [])
    monkeypatch.setattr(check, "POST_ROWS", [])
    asyncio.run(check.row_gather("a creator", 1))
    return check.ROWS


def test_large_creator_reads_media_once(monkeypatch):
    # 7,000 posts with two items each: 14,000 rows
    posts = [_post(p, (p * 10, p * 10 + 1), p % 28 + 1) for p in range(1, 7001)]
    collection = _CountingCollection(posts, max_reads=1)
    rows = _rows(monkeypatch, collection)
    assert len(rows) == 14000
    assert collection.all_media_reads == 1


@pytest.mark.parametrize("dupes", [False, True])
def test_other_posts_column_unchanged(monkeypatch, dupes):
    # media 100 is in posts 1, 2 and 3; media 200 only in post 2
    posts = [
        _post(1, (100,), 3),
        _post(2, (100, 200), 2),
        _post(3, (100,), 1),
    ]
    if dupes:
        # the same media twice in one post must not list that post as "other"
        posts.append(_post(4, (300, 300), 4))
    collection = _CountingCollection(posts)
    # what the per-row lookup gave
    expected = {
        (m.id, m.post_id): [
            p for p in collection.posts_with_media_id(m.id) if p != m.post_id
        ]
        for m in collection.all_media
    }
    rows = _rows(monkeypatch, collection)
    got = {(r["media_id"], r["post_id"]): r["other_posts_with_media"] for r in rows}
    assert got == expected
    assert sorted(got[(100, 1)]) == [2, 3]
    assert got[(200, 2)] == []
