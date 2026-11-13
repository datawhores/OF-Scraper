from ofscraper.actions.like import *
from ofscraper.const.test_constants import *


def test_unlike_filter():
    unliked_only = filter_for_unfavorited(POST_ARRAY)
    test_array = list(filter(lambda x: x.get("isFavorite") is True, unliked_only))
    assert (len(test_array)) == 0


def test_unlike_filter_count():
    array = POST_ARRAY
    for i in range(0, len(array), 1):
        array[i]["isFavorite"] = None
    for i in range(0, len(array), 5):
        array[i]["isFavorite"] = False
    test_array = filter_for_unfavorited(array)
    assert (len(test_array)) == 10


def test_unlike_post_id():
    array = POST_ARRAY
    for i in range(0, len(array), 1):
        array[i]["isFavorite"] = None
    for i in range(0, len(array), 5):
        array[i]["isFavorite"] = False

    test_array = filter_for_unfavorited(array)
    test_array = get_post_ids(test_array)

    assert (len(test_array)) == len(
        list(filter(lambda x: isinstance(x, int), test_array))
    )


def test_like_filter():
    liked_only = filter_for_favorited(POST_ARRAY)
    test_array = list(filter(lambda x: x.get("isFavorite") is False, liked_only))
    assert (len(test_array)) == 0


def test_like_filter_count():
    array = POST_ARRAY
    for i in range(0, len(array), 1):
        array[i]["isFavorite"] = None
    for i in range(0, len(array), 5):
        array[i]["isFavorite"] = True
    test_array = test_array = filter_for_favorited(array)
    assert (len(test_array)) == 10


def test_like_post_id():
    array = POST_ARRAY
    for i in range(0, len(array), 1):
        array[i]["isFavorite"] = None
    for i in range(0, len(array), 5):
        array[i]["isFavorite"] = True

    test_array = filter_for_favorited(array)
    test_array = get_post_ids(test_array)

    assert (len(test_array)) == len(
        list(filter(lambda x: isinstance(x, int), test_array))
    )
