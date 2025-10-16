import tempfile

from pytest_check import check

import ofscraper.utils.paths.paths as paths_
from ofscraper.config.config import *
from ofscraper.config.data import *
from ofscraper.const.test_constants import *
from ofscraper.utils.profiles2.profiles import *


def test_configarg_path_single_file(mocker):
    with tempfile.TemporaryDirectory() as p:
        mocker.patch("pathlib.Path.home", return_value=pathlib.Path(p))
        mocker.patch(
            "ofscraper.utils.args.getargs",
            return_value=args_.getargs(["--config", "test.json"]),
        )
        assert (paths_.get_config_path()) == pathlib.Path(
            p, ".config/ofscraper", "test.json"
        )


def test_configarg_file_within_dir(mocker):
    with tempfile.TemporaryDirectory() as p:
        configFile = pathlib.Path(p, "test.json")
        mocker.patch(
            "ofscraper.utils.args.getargs",
            return_value=args_.getargs(["--config", str(configFile)]),
        )
        assert (paths_.get_config_path()) == configFile


def test_configarg_directory(mocker):
    with tempfile.TemporaryDirectory() as p:
        configFile = pathlib.Path(p)
        mocker.patch(
            "ofscraper.utils.args.getargs",
            return_value=args_.getargs(["--config", str(configFile)]),
        )
        assert (paths_.get_config_path()) == pathlib.Path(p, "config.json")


def test_configarg_nested_directory(mocker):
    with tempfile.TemporaryDirectory() as p:
        configFile = pathlib.Path(p, "test")
        mocker.patch(
            "ofscraper.utils.args.getargs",
            return_value=args_.getargs(["--config", str(configFile)]),
        )
        assert (paths_.get_config_path()) == pathlib.Path(p, "test", "config.json")


def test_configarg_empty_(mocker):
    with tempfile.TemporaryDirectory() as p:
        mocker.patch("pathlib.Path.home", return_value=pathlib.Path(p))
        mocker.patch(
            "ofscraper.utils.args.getargs", return_value=args_.getargs(["--config", ""])
        )
        assert (paths_.get_config_path()) == pathlib.Path(
            p, ".config/ofscraper/config.json"
        )


def test_configarg_none(mocker):
    with tempfile.TemporaryDirectory() as p:
        mocker.patch("pathlib.Path.home", return_value=pathlib.Path(p))
        mocker.patch(
            "ofscraper.utils.args.getargs",
            return_value=args_.getargs(["--config", None]),
        )
        assert (paths_.get_config_path()) == pathlib.Path(
            p, ".config/ofscraper/config.json"
        )


def test_profile_count(mocker):
    with tempfile.TemporaryDirectory() as p:
        mocker.patch(
            "ofscraper.utils.args.getargs", return_value=args_.getargs(["--config", p])
        )
        configdir = paths_.get_config_home()
        (configdir / "1").mkdir()
        (configdir / "2").mkdir()
        (configdir / "3").mkdir()
        assert (len(get_profiles())) == 0


def test_profile_count2(mocker):
    with tempfile.TemporaryDirectory() as p:
        mocker.patch(
            "ofscraper.utils.args.getargs", return_value=args_.getargs(["--config", p])
        )
        configdir = paths_.get_config_home()
        (configdir / "1_profile").mkdir()
        (configdir / "2_profile").mkdir()
        (configdir / "3_profile").mkdir()
        assert (len(get_profiles())) == 3


def test_profile_count_empty_config(mocker):
    with tempfile.TemporaryDirectory() as p:
        mocker.patch("pathlib.Path.home", return_value=pathlib.Path(p))
        mocker.patch(
            "ofscraper.utils.args.getargs",
            return_value=args_.getargs(["--config", "", "--profile", "test_profile"]),
        )
        create_profile_path()
        with check():
            assert (
                pathlib.Path(
                    p, constants.getattr(".configPath"), "test_profile"
                ).exists()
            ) is True
        with check():
            assert (len(get_profiles())) == 1


def test_profile_count_empty_config_multiple(mocker):
    with tempfile.TemporaryDirectory() as p:
        mocker.patch("pathlib.Path.home", return_value=pathlib.Path(p))
        mocker.patch(
            "ofscraper.utils.args.getargs", return_value=args_.getargs(["--config", ""])
        )
        create_profile_path("test_profile")
        create_profile_path("test2_profile")
        create_profile_path("test3_profile")
        assert (len(get_profiles())) == 3


def test_profile_count_json_config_multiple(mocker):
    with tempfile.TemporaryDirectory() as p:
        mocker.patch("pathlib.Path.home", return_value=pathlib.Path(p))
        mocker.patch(
            "ofscraper.utils.args.getargs",
            return_value=args_.getargs(["--config", "test.json"]),
        )
        create_profile_path()
        create_profile_path("test_profile")
        create_profile_path("test2_profile")
        create_profile_path("test3_profile")
        assert (len(get_profiles())) == 4


def test_profile_count_json_config_badinput(mocker):
    with tempfile.TemporaryDirectory() as p:
        mocker.patch("pathlib.Path.home", return_value=pathlib.Path(p))
        mocker.patch(
            "ofscraper.utils.args.getargs",
            return_value=args_.getargs(["--config", "test.json"]),
        )
        create_profile_path()
        create_profile_path("test_profile2")
        create_profile_path("test2_profile3")
        create_profile_path("test3_profile4")
        assert (len(get_profiles())) == 1


def test_profile_count_nested_config_multiple(mocker):
    with tempfile.TemporaryDirectory() as p:
        configPath = pathlib.Path(p) / "test/me/config.json"
        mocker.patch(
            "ofscraper.utils.args.getargs",
            return_value=args_.getargs(["--config", str(configPath)]),
        )
        create_profile_path()
        create_profile_path("test_profile")
        create_profile_path("test2_profile")
        create_profile_path("test3_profile")
        assert (len(get_profiles())) == 4


def test_profile_count_nested_config_badinput(mocker):
    with tempfile.TemporaryDirectory() as p:
        configPath = pathlib.Path(p) / "test/me/config.json"
        mocker.patch(
            "ofscraper.utils.args.getargs",
            return_value=args_.getargs(["--config", str(configPath)]),
        )
        create_profile_path()
        create_profile_path("test_profile2")
        create_profile_path("test2_profile3")
        create_profile_path("test3_profile4")
        assert (len(get_profiles())) == 1
