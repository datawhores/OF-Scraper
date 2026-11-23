import pytest

import ofscraper.utils.config.data as data


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('"C:\\keys\\private_key.pem"', "C:\\keys\\private_key.pem"),
        ("'/keys/private_key.pem'", "/keys/private_key.pem"),
        ('  "/keys/a b.pem"  ', "/keys/a b.pem"),
        ("/keys/private_key.pem", "/keys/private_key.pem"),
        ('"', '"'),
        (None, None),
    ],
)
def test_strip_path_quotes(raw, expected):
    assert data.strip_path_quotes(raw) == expected


def test_cdm_paths_are_unquoted():
    config = {
        "cdm_options": {
            "private-key": '"C:\\keys\\private_key.pem"',
            "client-id": '"C:\\keys\\client_id.bin"',
        }
    }
    assert data.get_private_key(config=config) == "C:\\keys\\private_key.pem"
    assert data.get_client_id(config=config) == "C:\\keys\\client_id.bin"


def test_ffmpeg_path_is_unquoted():
    config = {"binary_options": {"ffmpeg": '"C:\\ffmpeg\\bin\\ffmpeg.exe"'}}
    assert data.get_ffmpeg(config=config) == "C:\\ffmpeg\\bin\\ffmpeg.exe"


@pytest.fixture
def ffmpeg_env(monkeypatch):
    real = data.of_env.getattr
    monkeypatch.setattr(
        data.of_env,
        "getattr",
        lambda key, *a: "/opt/ffmpeg" if key == "FFMPEG_DEFAULT" else real(key),
    )


def test_empty_ffmpeg_is_not_replaced_by_env_default(ffmpeg_env):
    assert data.get_ffmpeg(config={"binary_options": {"ffmpeg": ""}}) == ""


def test_config_rewrite_keeps_empty_ffmpeg(ffmpeg_env):
    # auto_update_config writes this schema back to config.json
    import ofscraper.utils.config.schema as schema

    new = schema.get_current_config_schema({"binary_options": {"ffmpeg": ""}})
    assert new["binary_options"]["ffmpeg"] == ""


def test_settings_falls_back_to_env_default_for_empty_ffmpeg(ffmpeg_env, monkeypatch, tmp_path):
    import ofscraper.utils.config.config as config_
    import ofscraper.utils.paths.common as common_paths
    import ofscraper.utils.settings as settings

    # fresh config path with no config.json yet (#692)
    monkeypatch.setattr(common_paths, "get_config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr(config_, "config", None)
    monkeypatch.setattr(settings.config_data, "get_ffmpeg", lambda config=None: "")
    assert settings.merged_settings().ffmpeg == "/opt/ffmpeg"


def test_save_location_is_unquoted():
    import ofscraper.utils.paths.common as common_paths

    config = {"file_options": {"save_location": r'"D:\Media\OnlyFans"'}}
    assert common_paths.get_save_location(config=config) == r"D:\Media\OnlyFans"


def test_tests_never_use_the_real_config_folder():
    # conftest.py gives each test session (each xdist worker) its own empty
    # home folder in the system temp folder, so the user's real
    # ~/.config/ofscraper is never read or written.
    import os
    import pathlib
    import tempfile

    import ofscraper.utils.paths.common as common_paths

    temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
    home = pathlib.Path.home().resolve()
    assert home.is_relative_to(temp_root)
    assert common_paths.get_config_path().resolve().is_relative_to(home)
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker:
        assert worker in home.name
