import arrow
import click
import pytest

from ofscraper.utils.args.types.arrow import ArrowType


@pytest.mark.parametrize("value", ["2021-05-01", "05/01/2021", "5/1/2021"])
def test_absolute_dates_parse_including_the_documented_format(value):
    # --before/--after document MM/DD/YYYY
    assert ArrowType().convert(value, None, None).date() == arrow.get("2021-05-01").date()


@pytest.mark.parametrize(
    "value, shift",
    [
        ("1 minute ago", {"minutes": -1}),
        ("2 minutes ago", {"minutes": -2}),
        ("1 second ago", {"seconds": -1}),
        ("3 weeks ago", {"weeks": -3}),
        ("1 day ago", {"days": -1}),
        ("1 hour ago", {"hours": -1}),
        ("2 hours ago", {"hours": -2}),
        ("1 month ago", {"months": -1}),
        ("1 year ago", {"years": -1}),
    ],
)
def test_relative_dates_parse(value, shift):
    expected = arrow.now().shift(**shift)
    result = ArrowType().convert(value, None, None)
    # generous tolerance: the two clocks are read a moment apart
    assert abs((result - expected).total_seconds()) < 30


@pytest.mark.parametrize(
    "value", ["13/01/2021", "02/30/2021", "garbage", "05-01-2021", "yesterday"]
)
def test_a_bad_date_is_a_clear_usage_error(value):
    # a DD/MM date or a typo is reported by click, not as a traceback
    with pytest.raises(click.BadParameter, match="isn't a date"):
        ArrowType().convert(value, None, None)
