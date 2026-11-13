import asyncio
from types import SimpleNamespace

import ofscraper.data.posts.post as post
import ofscraper.utils.of_env.of_env as of_env


def _process(monkeypatch, scraped):
    monkeypatch.setattr(post.profile, "scrape_profile", lambda username: scraped)
    monkeypatch.setattr(
        post.free.settings, "get_settings", lambda: SimpleNamespace(system_free_min=0)
    )
    tracebacks = []
    monkeypatch.setattr(post.log, "traceback_", tracebacks.append, raising=False)
    result = asyncio.run(post.process_profile("gone"))
    return result, tracebacks


def test_deleted_model_profile_is_skipped_without_error(monkeypatch):
    placeholder = {"username": of_env.getattr("DELETED_MODEL_PLACEHOLDER")}
    result, tracebacks = _process(monkeypatch, placeholder)
    assert result == ([], post.profile.API)
    assert tracebacks == []


def test_existing_profile_still_yields_its_media(monkeypatch):
    scraped = {
        "id": 1,
        "username": "model",
        "name": "Model",
        "avatar": "https://example.invalid/avatar.jpg",
        "joinDate": "2020-01-01T00:00:00+00:00",
        "postsCount": 0,
        "photosCount": 0,
        "videosCount": 0,
        "audiosCount": 0,
        "archivedPostsCount": 0,
    }
    (posts, api), tracebacks = _process(monkeypatch, scraped)
    assert api == post.profile.API and tracebacks == []
    assert len(posts) == 1 and posts[0].model_id == 1
