"""Pin how ofscraper uses arrow, aiolimiter and pathvalidate, so upgrading
them (#404 step 2) can't change dates in file names and the database, the
download rate limit, or which output templates are accepted."""

import asyncio
import warnings

import arrow
import pytest
from pathvalidate import ValidationError, validate_filename, validate_filepath

import ofscraper.utils.dates as dates
from ofscraper.commands.scraper.actions.download.utils import leaky

# the date forms OnlyFans and Fansly send, and what ofscraper stores
DATES = [
    ("2024-03-05T14:07:09+00:00", 1709647629.0),
    ("2024-03-05T14:07:09Z", 1709647629.0),
    ("2024-03-05T16:07:09+02:00", 1709647629.0),
    ("2024-03-05T14:07:09.123456+00:00", 1709647629.123456),
    (1709647629, 1709647629.0),
    (1709647629.5, 1709647629.5),
]


@pytest.mark.parametrize("value, epoch", DATES)
def test_dates_parse_to_the_same_instant(value, epoch):
    # to the microsecond: approx's default relative tolerance is about half
    # an hour at these timestamps
    assert arrow.get(value).float_timestamp == pytest.approx(epoch, rel=0, abs=1e-6)


@pytest.mark.parametrize(
    "pattern, expected",
    [
        ("YYYY-MM-DD HH:mm:ss", "2024-03-05 14:07:09"),  # posts, media, database
        ("YYYY_MM_DD", "2024_03_05"),  # media file names
        ("YYYY.MM.DD", "2024.03.05"),  # table date filters
        ("YYYY-MM-DD", "2024-03-05"),  # models
        ("MM-DD-YYYY hh:mm A", "03-05-2024 02:07 PM"),
    ],
)
def test_formats_are_unchanged(pattern, expected):
    assert arrow.get("2024-03-05T14:07:09+00:00").format(pattern) == expected


def test_epoch_zero_formats_as_1970():
    # media without a date are formatted from 0
    assert arrow.get(0).format("YYYY_MM_DD") == "1970_01_01"


def test_local_time_conversions_keep_the_instant():
    assert dates.convert_local_time("2024-03-05T14:07:09") == 1709647629.0
    assert abs(dates.get_current_time() - arrow.utcnow().float_timestamp) < 5


def test_utc_conversion_and_shifts():
    t = arrow.get("2024-03-05T14:07:09+02:00")
    assert t.to("utc").isoformat() == "2024-03-05T12:07:09+00:00"
    assert t.shift(days=-1).float_timestamp == t.float_timestamp - 86400
    assert t.floor("day").format("YYYY-MM-DD HH:mm:ss") == "2024-03-05 00:00:00"
    assert t.is_between(t.shift(seconds=-1), t.shift(seconds=1))


def test_download_limiter_splits_big_chunks_and_needs_no_shared_loop(monkeypatch):
    """A chunk bigger than the per-second limit is taken in pieces; each run
    makes its own limiter, so a new event loop gives no reuse warning."""
    from types import SimpleNamespace

    monkeypatch.setattr(
        leaky.settings, "get_settings", lambda: SimpleNamespace(download_limit=1000)
    )
    taken = []
    real = leaky.AsyncLimiter.acquire

    async def record(self, amount=1):
        taken.append(amount)
        return await real(self, amount)

    monkeypatch.setattr(leaky.AsyncLimiter, "acquire", record)

    async def run():
        await leaky.LeakyBucket(1000, 1).acquire(2500)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        asyncio.run(run())
        asyncio.run(run())
    assert taken == [1000, 1000, 500] * 2


@pytest.mark.parametrize(
    "name",
    ["{model_username}_{date}_{filename}.{ext}", "{post_id}_{media_id}.{ext}"],
)
def test_ordinary_file_name_templates_are_valid(name):
    validate_filename(name.format(
        model_username="a_creator", date="2024-03-05", filename="clip", ext="mp4",
        post_id=1, media_id=2,
    ), platform="Linux")


@pytest.mark.parametrize("name", ["a/b.mp4", "", "x" * 300])
def test_invalid_file_names_are_refused(name):
    with pytest.raises(ValidationError):
        validate_filename(name, platform="Linux")


def test_windows_reserved_name_is_refused():
    with pytest.raises(ValidationError):
        validate_filename("CON.mp4", platform="Windows")
    validate_filepath("Fansly/a_creator/Videos/clip.mp4", platform="Windows")
