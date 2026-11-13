import os
import pathlib
import random
import re
import string
import tempfile
from unittest.mock import MagicMock, patch

import arrow
import pytest
from pytest_check import check
from random_unicode_emoji import random_emoji

import ofscraper.classes.placeholder as placeholder
import ofscraper.download.downloadbatch as downloadbatch
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.paths.paths as paths
from ofscraper.classes.posts import Post
from ofscraper.const.test_constants import *
from ofscraper.utils.dates import convert_local_time


# Word split
def test_windows_trunicate_custom1(mocker):
    with patch("platform.system", MagicMock(return_value="Windows")):
        long_path = pathlib.Path(
            "F:\vr vids\AAA other\A dLd cont\new OF\jeanhollywood\Posts\Videos\2021-09-24_Behind the scenes! Y’all gonna love this one. I was a porn addicted gooner for a shoot. My roommate left to go out and I immediately whipped out my laptop and my Handy. I got 4 hours deep before she came back and offered to join. Gooners are gonna go crazy for it when it comes out 😈😈😈_1.mp4"
        )
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(truncated))) <= 256
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix


def test_windows_truncate(mocker):
    with patch("platform.system", MagicMock(return_value="Windows")):
        long_path = pathlib.Path(f"{WINDOWS_LONGPATH}.mkv")
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(truncated))) <= 256
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix


def test_windows_truncate_256(mocker):
    with patch("platform.system", MagicMock(return_value="Windows")):
        pathbase = WINDOWS_LONGPATH[:252]
        long_path = pathlib.Path(f"{pathbase}.mkv")
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(long_path))) == 256
        with check:
            assert (len(str(truncated))) == 256
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix


def test_windows_truncate_small(mocker):
    with patch("platform.system", MagicMock(return_value="Windows")):
        pathbase = WINDOWS_LONGPATH[:200]
        long_path = pathlib.Path(f"{pathbase}.mkv")
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(long_path))) == 204
        with check:
            assert (len(str(truncated))) == 204
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix


def test_windows_truncate_count(mocker):
    with patch("platform.system", MagicMock(return_value="Windows")):
        number = 5000
        long_path = pathlib.Path(f"{WINDOWS_LONGPATH}_{number}.mkv")
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(truncated))) <= 256
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix
        with check:
            assert (str(truncated).find(f"{number}")) != 0


def test_windows_truncate_count_small(mocker):
    with patch("platform.system", MagicMock(return_value="Windows")):
        number = 5000
        long_path = pathlib.Path(f"{WINDOWS_LONGPATH[:200]}_{number}.mkv")
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(truncated))) <= 256
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix
        with check:
            assert (str(truncated).find(f"{number}")) != 0


def test_linux_truncate(mocker):
    with patch("platform.system", MagicMock(return_value="Linux")):
        long_path = pathlib.Path(f"{LINUX_LONGPATH}.mkv")
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(truncated.name).encode("utf8"))) <= 255
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix


def test_linux_truncate_255(mocker):
    with patch("platform.system", MagicMock(return_value="Linux")):
        dirLength = len(str(pathlib.Path(LINUX_LONGPATH).parent).encode("utf8"))
        extLength = len(".mkv".encode("utf8"))
        maxlenth = 254
        pathbase = (
            LINUX_LONGPATH.encode("utf8")[: dirLength + 1 + maxlenth - extLength]
        ).decode()
        long_path = pathlib.Path(f"{pathbase}.mkv")
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(long_path.name).encode("utf8"))) == maxlenth
        with check:
            assert (len(str(truncated.name).encode("utf8"))) == maxlenth
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix


def test_linux_truncate_small(mocker):
    with patch("platform.system", MagicMock(return_value="Linux")):
        dirLength = len(str(pathlib.Path(LINUX_LONGPATH).parent).encode("utf8"))
        extLength = len(".mkv".encode("utf8"))
        maxlenth = 200
        pathbase = (
            LINUX_LONGPATH.encode("utf8")[: dirLength + 1 + maxlenth - extLength]
        ).decode()
        long_path = pathlib.Path(f"{pathbase}.mkv")
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(long_path.name).encode("utf8"))) == maxlenth
        with check:
            assert (len(str(truncated.name).encode("utf8"))) == maxlenth
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix


def test_linux_truncate_count(mocker):
    with patch("platform.system", MagicMock(return_value="Linux")):
        number = 5000
        long_path = pathlib.Path(f"{LINUX_LONGPATH}_{number}.mkv")
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(truncated.name).encode("utf8"))) <= 255
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix
        with check:
            assert (str(truncated).find(f"{number}")) != 0


def test_linux_truncate_count_small(mocker):
    with patch("platform.system", MagicMock(return_value="Linux")):
        number = 5000
        long_path = pathlib.Path(f"{LINUX_LONGPATH[:200]}_{number}.mkv")
        truncated = paths.truncate(long_path)
        with check:
            assert (len(str(truncated.name).encode("utf8"))) <= 255
        with check:
            assert (long_path.parent) == truncated.parent
        with check:
            assert (long_path.suffix) == truncated.suffix
        with check:
            assert (str(truncated).find(f"{number}")) != 0


def test_linux_truncator_super():
    with tempfile.TemporaryDirectory() as p:
        masterfile = "".join(
            random.choices(string.ascii_uppercase + string.ascii_lowercase, k=5000)
        )
        for i in range(1, 5000):
            print(i)
            with check:
                modified = paths._linux_truncateHelper(
                    pathlib.Path(p, f"{masterfile[:i]}_1.ext")
                )
                assert (len(modified.name.encode("utf8"))) <= 255


def test_linux_truncator_super2():
    with tempfile.TemporaryDirectory() as p:
        masterfile = "".join(
            random.choices(string.ascii_uppercase + string.ascii_lowercase, k=5000)
        )
        for i in range(1, 5000):
            with check:
                modified = paths._linux_truncateHelper(
                    pathlib.Path(p, f"{masterfile[:i]}.part")
                )
                if (len(modified.name.encode("utf8"))) > 255:
                    print("dd")
                assert (len(modified.name.encode("utf8"))) <= 255


def test_linux_truncator_super3():
    with tempfile.TemporaryDirectory() as p:
        masterfile = "".join(
            random.choices(string.ascii_uppercase + string.ascii_lowercase, k=5000)
        )
        for i in range(1, 5000):
            with check:
                modified = paths._linux_truncateHelper(
                    pathlib.Path(p, f"{masterfile[:i]}.part")
                )
                assert (len(modified.name.encode("utf8"))) <= 255
                modified.unlink(missing_ok=True)


def test_linux_truncator_super_emoji():
    with tempfile.TemporaryDirectory() as p:
        masterfile = "".join(
            random.choices(
                string.ascii_uppercase + string.ascii_lowercase + random_emoji()[0],
                k=5000,
            )
        )
        for i in range(260, 5000):
            with check:
                modified = paths._linux_truncateHelper(
                    pathlib.Path(p, f"{masterfile[:i]}_1.ext")
                )
                if (len(modified.name.encode("utf8"))) > 255:
                    print("dd")
                assert (len(modified.name.encode("utf8"))) <= 255


def test_linux_truncator_super_emoji2():
    with tempfile.TemporaryDirectory() as p:
        masterfile = "".join(
            random.choices(
                string.ascii_uppercase + string.ascii_lowercase + random_emoji()[0],
                k=5000,
            )
        )
        for i in range(260, 5000):
            with check:
                modified = paths._linux_truncateHelper(
                    pathlib.Path(p, f"{masterfile[:i]}.part")
                )
                if (len(modified.name.encode("utf8"))) > 255:
                    print("dd")
                assert (len(modified.name.encode("utf8"))) <= 255


def test_mac_truncate_255(mocker):
    with patch("platform.system", MagicMock(return_value="Darwin")):
        suffix = ".mkv"
        long_path = f"{pathlib.Path(LINUX_LONGPATH)}{suffix}"
        maxlength = 255
        truncated = paths.truncate(long_path)

        with check:
            assert (len(str(truncated.name))) == maxlength
        with check:
            assert (pathlib.Path(long_path).parent) == truncated.parent
        with check:
            assert (re.search(f"{suffix}$", str(truncated.name))) is not None


def test_user_data_dc_db_str(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILE_FORMAT_DEFAULT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DC,
        "filter": FILTER_DEFAULT,
    }
    logger.init_stdout_logger()

    mocker.patch(
        "ofscraper.utils.paths.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)

    assert (
        str(placeholder.databasePlaceholder().databasePathHelper("1111", "test"))
    ) == str(pathlib.Path(SAVE_PATH_DEFAULT, "test", "metadata", "user_data.db"))


def test_context_provider(mocker):
    with tempfile.TemporaryDirectory() as p:
        with paths.set_directory(p):
            assert (pathlib.Path(".").absolute()) == pathlib.Path(p)


def test_context_provider2(mocker):
    with tempfile.TemporaryDirectory() as p:
        with paths.set_directory(p):
            None
        assert (pathlib.Path(".").absolute()) != pathlib.Path(p)


def test_createfilename(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILE_FORMAT_DEFAULT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    mocker.patch(
        "ofscraper.utils.download.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)
    logger.init_stdout_logger()

    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    print(t.media[0].filename)
    assert (
        placeholder.Placeholders().createfilename(t.media[0], username, model_id, "mkv")
    ) == f"{t.media[0].filename}.mkv"


def test_createfilename_allkeys(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_VALID_ALL,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }

    mocker.patch(
        "ofscraper.utils.download.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)
    logger.init_stdout_logger()

    username = "test"
    model_id = TEST_ID
    try:
        t = Post(TIMELINE_EXAMPLE, model_id, username)
        assert placeholder.Placeholders().createfilename(
            t.media[0], username, model_id, "mkv"
        )
    except:
        raise Exception


def test_createfilename_invalid(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_ALLVALIDWTHINVALID,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }

    mocker.patch(
        "ofscraper.utils.download.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)

    username = "test"
    model_id = TEST_ID
    with pytest.raises(Exception):
        t = Post(TIMELINE_EXAMPLE, model_id, username)
        assert placeholder.Placeholders().createfilename(
            t.media[0], username, model_id, "mkv"
        )


def test_create_txt(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    mocker.patch(
        "ofscraper.utils.download.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)
    logger.init_stdout_logger()

    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    print(t.media[0].filename)
    assert (
        placeholder.Placeholders().createfilename(t.media[0], username, model_id, "mkv")
    ) == f"{t.media[0].text}_1.mkv"


# Test postid counter
def test_create_postid_counter(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_POSTID,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    mocker.patch(
        "ofscraper.utils.download.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)

    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    logger.init_stdout_logger()
    assert (len(t.media)) > 1


def test_create_postid_name(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_POSTID,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    mocker.patch(
        "ofscraper.utils.download.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)
    logger.init_stdout_logger()

    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)

    assert (
        placeholder.Placeholders().createfilename(t.media[0], username, model_id, "mkv")
    ) == f"{t.media[0].id}_1.mkv"


def test_create_postid_name2(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_POSTID,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    mocker.patch(
        "ofscraper.utils.download.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)
    logger.init_stdout_logger()

    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mocker.patch("ofscraper.classes.posts.Post.post_media", new=[t.post_media[0]])
    assert (
        placeholder.Placeholders().createfilename(t.media[0], username, model_id, "mkv")
    ) == f"{t.media[0].id}.mkv"


# Test text counter
def test_create_text_counter(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    mocker.patch(
        "ofscraper.utils.download.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)

    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    assert (len(t.media)) > 1


def test_create_text_name(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    mocker.patch(
        "ofscraper.utils.download.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)
    logger.init_stdout_logger()

    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)

    assert (
        placeholder.Placeholders().createfilename(t.media[0], username, model_id, "mkv")
    ) == f"{t.media[0].text}_1.mkv"


def test_create_text_name2(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_PATH_DEFAULT,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_TEXT,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DEFAULT,
        "filter": FILTER_DEFAULT,
    }
    mocker.patch(
        "ofscraper.utils.download.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)
    logger.init_stdout_logger()

    username = "test"
    model_id = TEST_ID
    t = Post(TIMELINE_EXAMPLE, model_id, username)
    mocker.patch("ofscraper.classes.posts.Post.post_media", new=[t.post_media[0]])
    assert (
        placeholder.Placeholders().createfilename(t.media[0], username, model_id, "mkv")
    ) == f"{t.media[0].text}.mkv"


def test_settime():
    with tempfile.NamedTemporaryFile() as p:
        test_date = arrow.get("2021")
        downloadbatch.set_time(p.name, convert_local_time(test_date))
        assert (arrow.get(os.path.getmtime(p.name)).year) == test_date.year


def test_settime2():
    with tempfile.NamedTemporaryFile() as p:
        test_date = arrow.get("2021")
        downloadbatch.set_time(p.name, convert_local_time(test_date))
        assert (
            arrow.get(os.path.getmtime(p.name)).float_timestamp
        ) == test_date.float_timestamp


def test_convert_byte_large():
    size = 1 * 10**12
    assert (downloadbatch.convert_num_bytes(size)) == f"{1*10**(12-9)}.0 GB"


def test_test(mocker):
    return


def test_metadatesavelocation(mocker):
    migrationConfig = {
        "main_profile": PROFILE_DEFAULT,
        "save_location": SAVE_LOCATION_DC,
        "file_size_limit": FILE_SIZE_LIMIT_DEFAULT,
        "dir_format": DIR_FORMAT_DEFAULT,
        "file_format": FILEFORMAT_POSTID,
        "textlength": TEXTLENGTH_DEFAULT,
        "date": DATE_DEFAULT,
        "metadata": METADATA_DC,
        "filter": FILTER_DEFAULT,
        "mp4decrypt": MP4DECRYPT_DEFAULT,
    }
    logger.init_stdout_logger()

    mocker.patch(
        "ofscraper.utils.paths.config_.read_config", return_value=migrationConfig
    )
    mocker.patch("ofscraper.utils.paths.profiles.get_my_info", return_value=ME)

    username = "test"
    id = "111"
    assert (
        str(placeholder.databasePlaceholder().databasePathHelper(id, username))
    ) == str(pathlib.Path(SAVE_LOCATION_DC, "test", "metadata", "user_data.db"))
