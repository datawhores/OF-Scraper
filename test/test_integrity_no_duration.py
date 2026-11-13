"""verify_media_integrity must accept a valid file when no expected length is known.

The success log line used `diff`, which is only set when an expected length
is given. With none (the API sent no duration, or 0), a valid file raised
UnboundLocalError instead of passing. The DRM merge always runs this check,
so such a video failed after it had downloaded and merged.
"""

import pytest

import ofscraper.utils.system.ffprobe as ffprobe


@pytest.fixture
def media_of_length(monkeypatch):
    def set_length(seconds):
        monkeypatch.setattr(ffprobe, "get_media_duration", lambda path: seconds)

    return set_length


@pytest.mark.parametrize("expected", [None, 0])
def test_valid_file_without_an_expected_length_passes(media_of_length, expected):
    media_of_length(12.5)
    assert ffprobe.verify_media_integrity("video.mp4", expected) is True


def test_unreadable_file_still_fails(media_of_length):
    media_of_length(None)
    assert ffprobe.verify_media_integrity("video.mp4", None) is False


def test_length_check_unchanged(media_of_length):
    media_of_length(12.5)
    assert ffprobe.verify_media_integrity("video.mp4", 12) is True
    assert ffprobe.verify_media_integrity("video.mp4", 20) is False
