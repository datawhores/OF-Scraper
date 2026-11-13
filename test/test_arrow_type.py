import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import arrow
import click
import pytest
from dateutil import tz

from ofscraper.utils.args.types.arrow import ArrowType

# US Eastern time. Windows' C runtime reads TZ too, but only in this form
# (with US daylight saving rules); elsewhere the rules are spelled out so no
# zone database is needed.
EASTERN = "EST5EDT" if sys.platform == "win32" else "EST5EDT,M3.2.0,M11.1.0"

# Run in a process whose local zone is US Eastern: parse "N days ago", with N
# reaching a day past the last daylight saving change, and print now and the
# result as local wall-clock times.
_ACROSS_DST = """
import json, time
from ofscraper.utils.args.types.arrow import ArrowType

now = time.time()
days = 1
while time.localtime(now - days * 86400).tm_isdst == time.localtime(now).tm_isdst:
    days += 1
days += 1
result = ArrowType()._parse(f"{days} days ago").float_timestamp

def local(ts):
    t = time.localtime(ts)
    return [t.tm_year, t.tm_mon, t.tm_mday, t.tm_hour, t.tm_min, t.tm_isdst]

print(json.dumps({"days": days, "now": local(now), "result": local(result)}))
"""


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
    # shifted in the local zone, daylight saving included
    expected = arrow.now(tz.tzlocal()).shift(**shift)
    result = ArrowType().convert(value, None, None)
    # generous tolerance: the two clocks are read a moment apart
    assert abs((result - expected).total_seconds()) < 30


def test_relative_dates_keep_the_wall_clock_across_daylight_saving():
    # arrow 1.4's arrow.now() has a fixed UTC offset, so "N days ago" across a
    # daylight saving change came out an hour off the local time of day, as
    # arrow 1.3 gave it
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "TZ": EASTERN}
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(root), env.get("PYTHONPATH")]))
    out = subprocess.run(
        [sys.executable, "-c", _ACROSS_DST],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    found = json.loads(out.stdout)
    now, result = found["now"], found["result"]
    # the result is on the other side of the change
    assert now[5] != result[5]
    # N days earlier on the local wall clock, at the same time of day. The
    # clock is read before parsing, so a minute can tick over in between and
    # make the result a minute later.
    gap = datetime.datetime(*now[:5]) - datetime.datetime(*result[:5])
    minutes = gap.total_seconds() / 60
    assert minutes in (found["days"] * 1440, found["days"] * 1440 - 1)


@pytest.mark.parametrize(
    "value", ["13/01/2021", "02/30/2021", "garbage", "05-01-2021", "yesterday"]
)
def test_a_bad_date_is_a_clear_usage_error(value):
    # a DD/MM date or a typo is reported by click, not as a traceback
    with pytest.raises(click.BadParameter, match="isn't a date"):
        ArrowType().convert(value, None, None)
