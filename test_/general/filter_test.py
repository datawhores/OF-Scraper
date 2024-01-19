import arrow
from pytest_check import check

import ofscraper.filters.media.main as filters
import ofscraper.utils.args2.args as args_
from ofscraper.classes.posts import Post
from ofscraper.const.test_constants import *


def test_after(mocker):
    username = "test"
    model_id = TEST_ID
    input = list(map(lambda x: Post(x, model_id, username), POST_ARRAY))
    output = []
    [output.extend(ele.media) for ele in input]
    total = len(output)
    mocker.patch(
        "ofscraper.utils.args.getargs", return_value=args_.getargs(["--after", "2023"])
    )
    included = filters.posts_date_filter(output)
    excluded = list(filter(lambda x: arrow.get(x.date).year != 2023, output))

    with check:
        assert (len(excluded)) == total - len(included)
    with check:
        assert (len(included)) > 0
    with check:
        assert (len(included) + len(excluded)) == total


def test_after2(mocker):
    username = "test"
    model_id = TEST_ID
    input = list(map(lambda x: Post(x, model_id, username), POST_ARRAY))
    total = len(POST_ARRAY)
    output = []
    [output.extend(ele.media) for ele in input]
    total = len(output)
    mocker.patch(
        "ofscraper.utils.args.getargs", return_value=args_.getargs(["--after", "2023"])
    )

    included = filters.posts_date_filter(output)
    excluded = list(filter(lambda x: arrow.get(x.date).year != 2023, output))

    with check:
        assert (len(excluded)) == total - len(included)
    with check:
        assert (len(included)) > 0
    with check:
        assert (len(included) + len(excluded)) == total


def test_before(mocker):
    username = "test"
    model_id = TEST_ID
    input = list(map(lambda x: Post(x, model_id, username), POST_ARRAY))
    output = []
    [output.extend(ele.media) for ele in input]
    total = len(output)
    mocker.patch(
        "ofscraper.utils.args.getargs", return_value=args_.getargs(["--before", "2023"])
    )
    included = filters.posts_date_filter(output)
    excluded = list(filter(lambda x: arrow.get(x.date).year == 2023, output))

    with check:
        assert (len(excluded)) == total - len(included)
    with check:
        assert (len(included)) > 0
    with check:
        assert (len(included) + len(excluded)) == total


def test_before2(mocker):
    username = "test"
    model_id = TEST_ID
    input = list(map(lambda x: Post(x, model_id, username), POST_ARRAY))
    output = []
    [output.extend(ele.media) for ele in input]
    total = len(output)
    mocker.patch(
        "ofscraper.utils.args.getargs", return_value=args_.getargs(["--before", "2023"])
    )

    included = filters.posts_date_filter(output)
    excluded = list(filter(lambda x: arrow.get(x.date).year == 2023, output))

    with check:
        assert (len(excluded)) == total - len(included)
    with check:
        assert (len(included)) > 0
    with check:
        assert (len(included) + len(excluded)) == total


def test_like_after(mocker):
    mocker.patch(
        "ofscraper.utils.args.getargs", return_value=args_.getargs(["--after", "2023"])
    )
    total = len(POST_ARRAY)
    included = filters.timeline_array_filter(POST_ARRAY)
    excluded = list(
        filter(lambda x: arrow.get(x.get("postedAt")).year != 2023, POST_ARRAY)
    )

    with check:
        assert (len(excluded)) == total - len(included)
    with check:
        assert (len(included)) > 0
    with check:
        assert (len(included) + len(excluded)) == total
