"""What the startup rewrite of config.json drops or replaces is logged.

When config.json doesn't match what the getters make of it, the start
rewrites it from them. A key no getter reads (a misspelling, auth values
pasted in) was dropped, and a value a getter can't use (a size it can't
parse, a key mode it doesn't know) was replaced by the default, both
without a word. Each is now one warning naming the key.
"""

import json
import logging

import pytest

import ofscraper.main.open.load as load
import ofscraper.utils.config.config as config_
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.schema as schema
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths


class Collect(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    monkeypatch.setattr(config_, "config", None)  # read_config's cache
    monkeypatch.setattr(config_file, "_notes", [], raising=False)
    with of_env.builtin_defaults():
        yield


@pytest.fixture
def config_path(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    monkeypatch.setattr(common_paths, "get_config_path", lambda: path)
    return path


@pytest.fixture
def logged(monkeypatch):
    """The shared log, set up, with only a collecting handler on it."""
    shared = logging.getLogger("shared")
    handler = Collect()
    monkeypatch.setattr(shared, "handlers", [handler])
    monkeypatch.setattr(shared, "level", logging.DEBUG)
    return handler.lines


def defaults():
    return schema.get_current_config_schema(config=False)


def start_with(config_path, config):
    config_path.write_text(json.dumps(config), encoding="utf-8")
    config_.read_config()
    return json.loads(config_path.read_text(encoding="utf-8"))


def notes(lines):
    return [line for line in lines if "config.json" in line]


def test_keys_nothing_reads_are_named_without_their_values(config_path, logged):
    config = defaults()
    config["file_size_mx"] = "1GB"
    config["sess"] = "s3cr3t-cookie"
    config["download_options"]["filtre"] = ["Images"]

    saved = start_with(config_path, config)

    said = " ".join(notes(logged))
    for key in ("file_size_mx", "sess", "download_options.filtre"):
        assert f'"{key}"' in said
    assert "s3cr3t" not in said
    assert len(notes(logged)) == 3
    # the rewrite itself is as before
    assert "sess" not in saved and "filtre" not in saved["download_options"]


def test_values_replaced_by_the_default_are_named_by_type_not_value(config_path, logged):
    """The old value isn't repeated: an auth value pasted into the wrong key
    would end up in the log people send when asking for help."""
    config = defaults()
    config["cdm_options"]["key-mode-default"] = "manaul"
    config["performance_options"]["download_sems"] = "s3cr3t-cookie-value"
    config["content_filter_options"]["file_size_max"] = "ten GB"
    config["file_options"]["text_type_default"] = "words"

    saved = start_with(config_path, config)

    said = notes(logged)
    assert len(said) == 4
    for path, new in (
        ("cdm_options.key-mode-default", '"manual"'),
        ("performance_options.download_sems", "6"),
        ("content_filter_options.file_size_max", "0"),
        ("file_options.text_type_default", '"letter"'),
    ):
        assert any(f'"{path}"' in line and "a string" in line and new in line for line in said), path
    joined = " ".join(said)
    for old in ("manaul", "s3cr3t", "ten GB", "words"):
        assert old not in joined
    assert saved["cdm_options"]["key-mode-default"] == "manual"


def test_a_section_that_isnt_an_object_is_named(config_path, logged):
    config = defaults()
    config["file_options"] = None

    start_with(config_path, config)

    assert any('"file_options"' in line and "null" in line for line in notes(logged))


def older_name(section, key, older, value):
    """the setting under an older top-level name instead of its own"""

    def change(config):
        del config[section][key]
        config[older] = value

    return change


def setting(section, key, value):
    def change(config):
        config[section][key] = value

    return change


def missing(section, key):
    def change(config):
        del config[section][key]

    return change


@pytest.mark.parametrize(
    "change",
    [
        # older names that are read: moved to the current name, value kept
        older_name("content_filter_options", "file_size_max", "file_size_max", "1GB"),
        older_name("download_options", "auto_resume", "partfileclean", True),
        older_name("file_options", "save_location", "save_location", "saved"),
        # the same value in the form it's saved in
        setting("cdm_options", "key-mode-default", "Manual"),
        setting("performance_options", "download_sems", "6"),
        setting("download_options", "filter", "Images,Audios,Videos"),
        setting("download_options", "filter", "images, audios, videos"),
        setting("download_options", "filter", ["images", "audios", "videos"]),
        setting("content_filter_options", "file_size_max", "0GB"),
        setting("content_filter_options", "file_size_max", "0"),
        setting("advanced_options", "rotate_logs", "true"),
        # unset
        setting("file_options", "textlength", None),
        setting("content_filter_options", "file_size_max", ""),
        missing("advanced_options", "ssl_verify"),
    ],
)
def test_nothing_is_said_for_what_isnt_a_mistake(config_path, logged, change):
    config = defaults()
    change(config)

    start_with(config_path, config)

    assert notes(logged) == []


def test_an_address_in_database_url_keeps_only_its_own_warning(config_path, logged):
    config = defaults()
    config["advanced_options"]["database_url"] = "postgresql://u:s3cr3t@h/db"

    start_with(config_path, config)

    assert len(notes(logged)) == 1
    assert "database_url in config.json is not read" in notes(logged)[0]
    assert "s3cr3t" not in " ".join(logged)


def test_an_address_in_the_older_top_level_database_url_has_one_warning(config_path, logged):
    config = defaults()
    config["database_url"] = "postgresql://u:s3cr3t@h/db"

    start_with(config_path, config)

    assert len(notes(logged)) == 1
    assert "database_url in config.json is not read" in notes(logged)[0]
    assert "s3cr3t" not in " ".join(logged)


def test_an_empty_section_nothing_reads_is_named(config_path, logged):
    config = defaults()
    config["unknown_options"] = {}

    saved = start_with(config_path, config)

    said = notes(logged)
    assert len(said) == 1 and '"unknown_options"' in said[0]
    assert "unknown_options" not in saved


def test_an_empty_section_that_is_a_setting_is_filled_in_without_a_word(config_path, logged):
    config = defaults()
    config["file_options"] = {}

    saved = start_with(config_path, config)

    assert notes(logged) == []
    assert saved["file_options"] == defaults()["file_options"]


def test_a_current_name_hidden_by_an_older_one_is_named(config_path, logged):
    # the older top-level name is looked at first, so its value wins
    config = defaults()
    config["content_filter_options"]["file_size_max"] = "2GB"
    config["file_size_max"] = "1GB"

    saved = start_with(config_path, config)

    said = notes(logged)
    assert len(said) == 1 and '"content_filter_options.file_size_max"' in said[0]
    assert "older name" in said[0]
    assert saved["content_filter_options"]["file_size_max"] == 1_000_000_000


def test_notes_from_before_the_log_is_set_up_are_written_once_it_is(config_path, monkeypatch):
    config = defaults()
    config["file_size_mx"] = "1GB"
    config["advanced_options"]["database_url"] = "postgresql://u:s3cr3t@h/db"
    shared = logging.getLogger("shared")
    monkeypatch.setattr(shared, "handlers", [])

    start_with(config_path, config)

    handler = Collect()
    monkeypatch.setattr(load.logger, "get_shared_logger", lambda *a, **k: shared.handlers.append(handler))
    monkeypatch.setattr(load.logs, "discord_warning", lambda: None)
    monkeypatch.setattr(load.paths_manage, "cleanup_logs", lambda: None)
    monkeypatch.setattr(shared, "level", logging.DEBUG)
    load.setLogger()
    load.setLogger()

    said = notes(handler.lines)
    assert len(said) == 2
    assert "database_url in config.json is not read" in said[0]
    assert '"file_size_mx"' in said[1]
    assert "s3cr3t" not in " ".join(handler.lines)
