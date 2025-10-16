import re

from pytest_check import check

import ofscraper.utils.args2.args as args_
from ofscraper.classes.media import Media
from ofscraper.classes.posts import Post
from ofscraper.const.test_constants import *


def test_postcreate_timeline():
    username = "test"
    model_id = TEST_ID
    try:
        Post(TIMELINE_EXAMPLE, model_id, username)
    except Exception as E:
        raise Exception(f"Exception: {E}\nPost Creation Failed")


def test_media_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (len(t.post_media)) == len(TIMELINE_EXAMPLE["media"])


def test_post_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.post) == t._post


def test_modelid_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.model_id) == model_id


def test_username_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.username) == username


def test_archived_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.archived) is False


def test_text_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.text) == TIMELINE_EXAMPLE.get("text")


def test_title_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.title) == TIMELINE_EXAMPLE.get("title")


def test_ogresponse_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.responsetype) == TIMELINE_EXAMPLE.get("responseType")


def test_id_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.id) == TIMELINE_EXAMPLE.get("id")


def test_date_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.date) == TIMELINE_EXAMPLE.get("createdAt") or TIMELINE_EXAMPLE.get(
        "postedAt"
    )


def test_value_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.value) == "free"


def test_price_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.price) == 0


def test_paid_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.paid) is True


def test_fromuser_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.fromuser) == model_id


def test_preview_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (t.preview) == TIMELINE_EXAMPLE["preview"]


def test_mediacanview_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    for ele in t.media:
        assert (ele.canview) is True


def test_mediaclass_timeline():
    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    for ele in t.media:
        assert (isinstance(ele, Media)) is True


# Media Test
def test_mediaclass_timeline():
    username = "test"
    model_id = TEST_ID
    index = 1
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    try:
        Media(t.media[index], index, t)
    except Exception as E:
        raise E


def test_mediatype_timeline():
    username = "test"
    model_id = TEST_ID
    index = 1
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mediaDict = TIMELINE_EXAMPLE["media"][index]
    media = Media(mediaDict, index, t)
    assert (mediaDict["type"]) == "photo"
    assert (media.mediatype) == "images"


def test_mediaurl_timeline():
    username = "test"
    model_id = TEST_ID
    index = 1
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mediaDict = TIMELINE_EXAMPLE["media"][index]
    media = Media(mediaDict, index, t)
    assert (re.search("http", media.url)) is not None


def test_mediapost_timeline():
    username = "test"
    model_id = TEST_ID
    index = 1
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mediaDict = TIMELINE_EXAMPLE["media"][index]
    media = Media(mediaDict, index, t)
    assert (media.post) == t


def test_media_id_timeline():
    username = "test"
    model_id = TEST_ID
    index = 1
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mediaDict = TIMELINE_EXAMPLE["media"][index]
    media = Media(mediaDict, index, t)
    assert (media.id) == mediaDict["id"]


def test_medialen_timeline():
    username = "test"
    model_id = TEST_ID
    index = 1
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mediaDict = TIMELINE_EXAMPLE["media"][index]
    media = Media(mediaDict, index, t)
    assert (len(media.post.post_media)) == len(TIMELINE_EXAMPLE["media"])


def test_mediacount_timeline():
    username = "test"
    model_id = TEST_ID
    index = 1
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mediaDict = TIMELINE_EXAMPLE["media"][index]
    media = Media(mediaDict, index, t)
    assert (media.count) == index + 1


def test_mediapreview_timeline():
    username = "test"
    model_id = TEST_ID
    index = 1
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mediaDict = TIMELINE_EXAMPLE["media"][index]
    media = Media(mediaDict, index, t)
    assert (TIMELINE_EXAMPLE["preview"]) == []
    assert (media.preview) == 0


def test_medialinked_timeline():
    username = "test"
    model_id = TEST_ID
    index = 1
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mediaDict = TIMELINE_EXAMPLE["media"][index]
    media = Media(mediaDict, index, t)
    assert (media.linked) is None


def test_mediamedia_timeline():
    username = "test"
    model_id = TEST_ID
    index = 1
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mediaDict = TIMELINE_EXAMPLE["media"][index]
    media = Media(mediaDict, index, t)
    assert (media.media) == mediaDict


def test_timeline_text_wordtruncate(mocker):
    length = TEXTLENGTH_ALT2
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_ALT2,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    args_.getargs([])
    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = ["", ""]
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 2, post)
    wordarray = list(filter(lambda x: len(x) != 0, re.split("( )", t.file_text)))
    with check:
        assert (len(wordarray)) >= length - 1

    with check:
        assert (len(wordarray)) < length + 1


def test_timeline_text_wordtruncate2(mocker):
    length = int(TEXTLENGTH_ALT2 / 2)
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    args_.getargs([])
    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = ["", ""]
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 2, post)
    wordarray = list(filter(lambda x: len(x) != 0, re.split("( )", t.file_text)))
    with check:
        assert (len(wordarray)) >= length - 1

    with check:
        assert (len(wordarray)) < length + 1


def test_timeline_text_wordtruncate3(mocker):
    length = TEXTLENGTH_DEFAULT
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    args_.getargs([])
    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = ["", ""]
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 2, post)
    wordarray = list(filter(lambda x: len(x) != 0, re.split("( )", t.file_text)))
    textarray = list(
        filter(
            lambda x: len(x) != 0,
            re.split("( )", f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"),
        )
    )
    with check:
        assert (len(wordarray)) >= len(textarray) - 1
    with check:
        assert (len(wordarray)) <= len(textarray) + 2


def test_timeline_text_wordtruncate4(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_ALT2,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    args_.getargs([])
    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = []
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 0, post)
    wordarray = list(filter(lambda x: len(x) != 0, re.split("( )", t.file_text)))
    with check:
        assert (len(wordarray)) >= TEXTLENGTH_ALT2 - 1

    with check:
        assert (len(wordarray)) < TEXTLENGTH_ALT2 + 1


def test_timeline_text_wordtruncate5(mocker):
    length = int(TEXTLENGTH_ALT2 / 2)
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    args_.getargs([])
    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = []
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 0, post)
    wordarray = list(filter(lambda x: len(x) != 0, re.split("( )", t.file_text)))
    with check:
        assert (len(wordarray)) >= length - 1

    with check:
        assert (len(wordarray)) < length + 1


def test_timeline_text_wordtruncate6(mocker):
    length = TEXTLENGTH_DEFAULT
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    args_.getargs([])
    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = []
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 0, post)
    wordarray = list(filter(lambda x: len(x) != 0, re.split("( )", t.file_text)))
    assert (len(wordarray)) >= len(
        "{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )


def test_timeline_text_lettertruncate(mocker):
    length = TEXTLENGTH_ALT
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_ALT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }

    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = ["", ""]
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 2, post)
    wordarray = t.file_text
    assert (len(wordarray)) == length


def test_timeline_text_lettertruncate2(mocker):
    length = int(TEXTLENGTH_ALT2 / 2)
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }

    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = ["", ""]
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 2, post)
    wordarray = t.file_text
    assert (len(wordarray)) == length


def test_timeline_text_lettertruncate3(mocker):
    length = TEXTLENGTH_DEFAULT
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }

    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = ["", ""]
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 2, post)
    wordarray = t.file_text
    assert (len(wordarray)) == len(
        f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    ) + 2


def test_timeline_text_lettertruncate4(mocker):
    length = TEXTLENGTH_ALT2
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }

    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = []
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 0, post)
    wordarray = t.file_text
    assert (len(wordarray)) == length


def test_timeline_text_lettertruncate5(mocker):
    length = int(TEXTLENGTH_ALT2 / 2)
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }

    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = []
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 0, post)
    wordarray = t.file_text
    assert (len(wordarray)) == length


def test_timeline_text_lettertruncate6(mocker):
    length = TEXTLENGTH_DEFAULT
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": length,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }

    mocker.patch(
        "ofscraper.classes.posts.config.read_config", return_value=migrationConfig
    )
    post = mocker.PropertyMock()
    post.post_media = []
    mocker.patch.object(
        Media, "text", new=f"{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
    t = Media(None, 0, post)
    wordarray = t.file_text
    assert (len(wordarray)) >= len(
        "{LONG_STRING}{LONG_STRING}{LONG_STRING}{LONG_STRING}"
    )
