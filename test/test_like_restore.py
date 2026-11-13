"""The corrective second like/unlike request decides the result (#212)."""

import contextlib

import pytest

import ofscraper.commands.scraper.actions.like.like as like


class Response:
    def __init__(self, favorite):
        self.favorite = favorite

    def json_(self):
        if self.favorite == "bad":
            raise ValueError("not JSON")
        return {"isFavorite": self.favorite, "id": 123}


class Session:
    """Replies to each request in turn with the next isFavorite value."""

    def __init__(self, *favorites):
        self.favorites = list(favorites)
        self.calls = 0

    @contextlib.contextmanager
    def requests(self, *args, **kwargs):
        self.calls += 1
        yield Response(self.favorites.pop(0))


class Post:
    id = 123

    def __init__(self):
        self.results = []

    def mark_like_attempt(self):
        pass

    def mark_post_liked(self, success=True):
        self.results.append(success)

    def mark_post_unliked(self, success=True):
        self.results.append(success)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(like.time, "sleep", lambda *_: None)


# (first reply, second reply) for a like: the first toggle unliked an already-liked post
@pytest.mark.parametrize("second", ["bad", False])
def test_like_fails_when_the_second_request_does_not_relike(second):
    post, session = Post(), Session(False, second)
    assert like._toggle_like_requests(session, post, 456) == 3
    assert post.results == [False]
    assert session.calls == 2


def test_like_restored():
    post, session = Post(), Session(False, True)
    assert like._toggle_like_requests(session, post, 456) == 2
    assert post.results == [True]


@pytest.mark.parametrize("second", ["bad", True])
def test_unlike_fails_when_the_second_request_does_not_unlike(second):
    post, session = Post(), Session(True, second)
    assert like._toggle_unlike_requests(session, post, 456) == 3
    assert post.results == [False]
    assert session.calls == 2


def test_unlike_restored():
    post, session = Post(), Session(True, False)
    assert like._toggle_unlike_requests(session, post, 456) == 2
    assert post.results == [True]
