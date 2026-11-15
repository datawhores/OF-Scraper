"""Pins what every getter in ofscraper/utils/config/data.py returns.

auto_update_config rebuilds config.json from these getters and writes it
back, so a getter that returns something different for any input changes
users' files on disk. Each getter is run over a matrix of configs (missing
key, top-level value, nested value, both, None, falsy values, wrong types,
older key names, broken sections) and the results are compared, as a digest,
with the ones recorded from the code before the getters were refactored. The
written config is pinned the same way for a few representative files.

The built-in defaults are used throughout (of_env.builtin_defaults), so the
environment doesn't change the results. To see the full results, e.g. to diff
two versions of the code, set CONFIG_GETTER_SNAPSHOT_DUMP to a file path.
"""

import ast
import copy
import hashlib
import json
import os
import pathlib

import pytest

import ofscraper.utils.config.data as data
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.schema as schema
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.paths.common as common_paths

# getter -> the config paths it reads ("section.key" for a nested key)
GETTER_PATHS = {
    "get_main_profile": ["main_profile"],
    "get_filesize_max": [
        "file_size_max",
        "download_options.file_size_max",
        "download_options.file_size_limit",
        "content_filter_options.file_size_max",
    ],
    "get_filesize_min": [
        "file_size_min",
        "download_options.file_size_min",
        "content_filter_options.file_size_min",
    ],
    "get_min_length": [
        "length_min",
        "download_options.length_min",
        "content_filter_options.length_min",
    ],
    "get_max_length": [
        "length_max",
        "download_options.length_max",
        "content_filter_options.length_max",
    ],
    "get_system_freesize": ["system_free_min", "download_options.system_free_min"],
    "get_dirformat": ["dir_format", "file_options.dir_format"],
    "get_fileformat": ["file_format", "file_options.file_format"],
    "get_textlength": ["textlength", "file_options.textlength"],
    "get_date": ["date", "file_options.date"],
    "get_InfiniteLoop": [
        "infinite_loop_action_mode",
        "advanced_options.infinite_loop_action_mode",
    ],
    "get_incremental_downloads": [
        "incremental_downloads",
        "advanced_options.incremental_downloads",
        "advanced_options.enable_auto_after",
    ],
    "get_default_userlist": ["default_user_list", "advanced_options.default_user_list"],
    "get_default_blacklist": [
        "default_black_list",
        "advanced_options.default_black_list",
    ],
    "get_logs_expire": ["logs_expire_time", "advanced_options.logs_expire_time"],
    "get_ssl_verify": ["ssl_verify", "advanced_options.ssl_verify"],
    "get_after_action_script": [
        "after_action_script",
        "advanced_options.after_action_script",
        "script_options.after_action_script",
    ],
    "get_post_script": [
        "post_script",
        "advanced_options.post_script",
        "scripts.post_script",
        "script_options.post_script",
    ],
    "get_naming_script": [
        "naming_script",
        "advanced_options.naming_script",
        "scripts.naming_script",
        "script_options.naming_script",
    ],
    "get_skip_download_script": [
        "skip_download_script",
        "advanced_options.skip_download_script",
        "scripts.skip_download_script",
        "script_options.skip_download_script",
    ],
    "get_after_download_script": [
        "after_download_script",
        "advanced_options.after_download_script",
        "scripts.after_download_script",
        "script_options.after_download_script",
    ],
    "get_env_files": [
        "env_files",
        "advanced_options.env_files",
        "scripts.env_files",
        "script_options.env_files",
    ],
    "get_metadata": ["metadata"],
    "get_download_limit": ["download_limit", "performance_options.download_limit"],
    "get_ffmpeg": ["ffmpeg", "binary_options.ffmpeg"],
    "get_discord": ["discord"],
    "get_filter": [
        "filter",
        "download_options.filter",
        "content_filter_options.filter",
    ],
    "responsetype": ["responsetype"],
    "get_timeline_responsetype": [
        "timeline",
        "post",
        "responsetype.timeline",
        "responsetype.post",
    ],
    "get_post_responsetype": [
        "post",
        "timeline",
        "responsetype.post",
        "responsetype.timeline",
    ],
    "get_archived_responsetype": ["archived", "responsetype.archived"],
    "get_stories_responsetype": ["stories", "responsetype.stories"],
    "get_highlights_responsetype": ["highlights", "responsetype.highlights"],
    "get_paid_responsetype": ["paid", "responsetype.paid"],
    "get_messages_progress_responsetype": ["message", "responsetype.message"],
    "get_profile_responsetype": ["profile", "responsetype.profile"],
    "get_pinned_responsetype": ["pinned", "responsetype.pinned"],
    "get_streams_responsetype": ["streams", "responsetype.streams"],
    "get_spacereplacer": [
        "space_replacer",
        "file_options.space_replacer",
        "file_options.space-replacer",
    ],
    "get_private_key": ["private-key", "cdm_options.private-key"],
    "get_client_id": ["client-id", "cdm_options.client-id"],
    "get_key_mode": ["key-mode-default", "cdm_options.key-mode-default"],
    "get_dynamic": ["dynamic-mode-default", "advanced_options.dynamic-mode-default"],
    "get_dynamic_configured": [
        "dynamic-mode-default",
        "advanced_options.dynamic-mode-default",
    ],
    "get_part_file_clean": [
        "auto_resume",
        "download_options.auto_resume",
        "partfileclean",
    ],
    "get_download_semaphores": ["download_sems", "performance_options.download_sems"],
    "get_show_downloadprogress": ["downloadbars", "advanced_options.downloadbars"],
    "get_cache_mode": ["cache-mode", "advanced_options.cache-mode"],
    "cache_mode_helper": ["cache-mode", "advanced_options.cache-mode"],
    "get_rotate_logs": ["rotate_logs", "advanced_options.rotate_logs"],
    "get_sanitizeDB": ["sanitize_text", "advanced_options.sanitize_text"],
    "get_textType": ["text_type_default", "file_options.text_type_default"],
    "get_TempDir": ["temp_dir", "advanced_options.temp_dir"],
    "get_filename_collision": [
        "filename_collision",
        "file_options.filename_collision",
    ],
    "get_truncation": ["truncation_default", "file_options.truncation_default"],
    "get_max_post_count": ["max_post_count", "download_options.max_post_count"],
    "get_hash": ["remove_hash_match", "advanced_options.remove_hash_match"],
    "get_block_ads": ["block_ads", "content_filter_options.block_ads"],
    "get_skip_unavailable_content": [
        "skip_unavailable_content",
        "advanced_options.skip_unavailable_content",
    ],
    "get_verify_all_integrity": [
        "verify_all_integrity",
        "download_options.verify_all_integrity",
    ],
}

VALUES = [
    None,
    False,
    True,
    0,
    1,
    -3,
    2.5,
    "",
    "  ",
    "abc",
    ' "quoted path" ',
    "10MB",
    "Images, videos",
    "CDRM",
    "word",
    "json",
    "disabled",
    [],
    ["images", "Videos"],
    {},
    {"timeline": "x"},
]
FALSY = [None, False, 0, "", [], {}]
SECOND = [None, False, 0, "", True, 1, "abc", ["a"]]
BAD_SECTIONS = [None, [], "text", 0, 5, True]

# the config the wrapper reads from disk when a getter gets config=None
FILE_CONFIG = {
    "file_options": {"dir_format": "from-file", "textlength": 7},
    "advanced_options": {"cache-mode": "json", "ssl_verify": "certifi"},
    "responsetype": {"timeline": "from-file"},
    "metadata": "from-file",
}


def _put(config, path, value):
    if "." in path:
        section, key = path.split(".", 1)
        if not isinstance(config.get(section), dict):
            config[section] = {}
        config[section][key] = value
    else:
        config[path] = value


def _cases(paths):
    yield False
    yield {}
    yield None
    for path in paths:
        for value in VALUES:
            config = {}
            _put(config, path, value)
            yield config
    for first in paths:
        for second in paths:
            if first == second:
                continue
            for a in FALSY:
                for b in SECOND:
                    config = {}
                    _put(config, first, a)
                    _put(config, second, b)
                    yield config
    config = {}
    for i, path in enumerate(paths):
        _put(config, path, f"v{i}")
    yield config
    sections = list(dict.fromkeys(p.split(".")[0] for p in paths if "." in p))
    tops = [p for p in paths if "." not in p]
    for section in sections:
        for bad in BAD_SECTIONS:
            yield {section: bad}
            for top in tops:
                for value in (None, False, "abc"):
                    yield {section: bad, top: value}


def _outcome(func, config):
    try:
        value = func(config=copy.deepcopy(config))
    except Exception as E:  # noqa: BLE001 - the exception type is the result
        return f"raises {type(E).__name__}"
    if isinstance(value, type):
        return f"class {value.__module__}.{value.__qualname__}"
    return f"{type(value).__name__} {value!r}"


def _case_text(config):
    return (
        json.dumps(config, sort_keys=True)
        if config not in (None, False)
        else repr(config)
    )


@pytest.fixture
def builtin(monkeypatch, tmp_path):
    monkeypatch.setattr(config_file, "open_config", lambda: copy.deepcopy(FILE_CONFIG))
    path = tmp_path / "config.json"
    monkeypatch.setattr(common_paths, "get_config_path", lambda: path)
    with of_env.builtin_defaults():
        yield path


def _getter_results():
    results = {}
    for name, paths in GETTER_PATHS.items():
        func = getattr(data, name)
        results[name] = [(_case_text(c), _outcome(func, c)) for c in _cases(paths)]
    return results


def _digest(obj):
    text = json.dumps(obj, sort_keys=False, ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _dump(name, obj):
    target = os.environ.get("CONFIG_GETTER_SNAPSHOT_DUMP")
    if target:
        with open(f"{target}.{name}.json", "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, ensure_ascii=True)


# getter -> (number of cases, digest of the results), from the code before
# the refactor
EXPECTED_GETTERS = {
    "get_main_profile": (25, "13e26f74f27d2d82"),
    "get_filesize_max": (712, "c3896826372763a5"),
    "get_filesize_min": (403, "ebc7652106fd54eb"),
    "get_min_length": (403, "4d5a30e8d85d9401"),
    "get_max_length": (403, "4cc84ab46714f702"),
    "get_system_freesize": (166, "a94114f1b528c78b"),
    "get_dirformat": (166, "f0cf87305a683b76"),
    "get_fileformat": (166, "4a0c2e21968ceab4"),
    "get_textlength": (166, "89ed486c626f9c93"),
    "get_date": (166, "cda54b47fc30776d"),
    "get_InfiniteLoop": (166, "1dac68fc766735bd"),
    "get_incremental_downloads": (379, "df55671f18096147"),
    "get_default_userlist": (166, "a528ef52b683eccd"),
    "get_default_blacklist": (166, "d76edbc57d873f16"),
    "get_logs_expire": (166, "8c7607fc9ed39baa"),
    "get_ssl_verify": (166, "ac437e1b1e186242"),
    "get_after_action_script": (403, "8ffa1f6112d305ee"),
    "get_post_script": (736, "deebe6b9ee60a8e9"),
    "get_naming_script": (736, "772324531b16ed92"),
    "get_skip_download_script": (736, "7ed79e8d0e73fcb9"),
    "get_after_download_script": (736, "8578bb0b73fc1479"),
    "get_env_files": (736, "ecffce695e5a1442"),
    "get_metadata": (25, "ecd7e87b9954b3f6"),
    "get_download_limit": (166, "ef32a9dd29869cb8"),
    "get_ffmpeg": (166, "2fe9cf18a0e4fce1"),
    "get_discord": (25, "4a67da123ed05ee2"),
    "get_filter": (403, "fcb037445d933184"),
    "responsetype": (25, "53a4934f2f2dd932"),
    "get_timeline_responsetype": (706, "9ee9f943e2e7dab7"),
    "get_post_responsetype": (706, "22cb7745e614f2a7"),
    "get_archived_responsetype": (166, "a7d879c0fc302ea3"),
    "get_stories_responsetype": (166, "147b4ce95139a027"),
    "get_highlights_responsetype": (166, "7b282b0424605398"),
    "get_paid_responsetype": (166, "f4cf8ffd811f58f2"),
    "get_messages_progress_responsetype": (166, "802489556c125e62"),
    "get_profile_responsetype": (166, "46c47a276861b6d6"),
    "get_pinned_responsetype": (166, "45fcd4fe31552de5"),
    "get_streams_responsetype": (166, "d003d61d4a14a281"),
    "get_spacereplacer": (379, "7b37dc89c0ef33b5"),
    "get_private_key": (166, "b35f6a59cc89ceb3"),
    "get_client_id": (166, "e9d7934b1c88dd81"),
    "get_key_mode": (166, "d7f8d7f937b29f28"),
    "get_dynamic": (166, "23711f9469ff33b0"),
    "get_dynamic_configured": (166, "cdfa21fa8a1688d0"),
    "get_part_file_clean": (397, "0a08b3d8c53aef97"),
    "get_download_semaphores": (166, "18b0040aa0eca54f"),
    "get_show_downloadprogress": (166, "abacad2fe22cad70"),
    "get_cache_mode": (166, "606291f700fe6bbb"),
    "cache_mode_helper": (166, "fe42cd345eee53fb"),
    "get_rotate_logs": (166, "16c6ae58e71a9e0d"),
    "get_sanitizeDB": (166, "99a67ae918b185ba"),
    "get_textType": (166, "e48765bf59f67a15"),
    "get_TempDir": (166, "3e5547e911964e20"),
    "get_filename_collision": (166, "9ab67ece2fcf4cf0"),
    "get_truncation": (166, "b66318ce67a1c35f"),
    "get_max_post_count": (166, "ae055fbbd5df493d"),
    "get_hash": (166, "6e0444691733f47c"),
    "get_block_ads": (166, "e3a3bd517645b913"),
    "get_skip_unavailable_content": (166, "4f4076024cebec8a"),
    "get_verify_all_integrity": (166, "f59b6c34e3f5133e"),
}


def test_every_getter_is_pinned():
    # the decorated getters report the wrapper's module, so read the source
    tree = ast.parse(pathlib.Path(data.__file__).read_text(encoding="utf-8"))
    public = {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and not node.name.startswith("_")
        and node.name != "strip_path_quotes"
    }
    assert public == set(GETTER_PATHS)


def test_getter_results_are_unchanged(builtin):
    results = _getter_results()
    _dump("getters", results)
    got = {name: (len(rows), _digest(rows)) for name, rows in results.items()}
    changed = {
        name: (EXPECTED_GETTERS.get(name), value)
        for name, value in got.items()
        if EXPECTED_GETTERS.get(name) != value
    }
    assert changed == {}


# representative config.json files, as written by older and current versions
SCHEMA_CONFIGS = {
    "false": False,
    "empty": {},
    "flat_legacy": {
        "main_profile": "other",
        "save_location": "/data/save",
        "dir_format": "{model_username}",
        "file_format": "{filename}.{ext}",
        "textlength": "12",
        "space-replacer": "_",
        "date": "YYYY",
        "file_size_limit": "1GB",
        "file_size_min": 1000,
        "system_free_min": "5GB",
        "filter": "images,videos",
        "partfileclean": True,
        "download_sems": "4",
        "download_limit": "2MB",
        "ffmpeg": '"C:/tools/ffmpeg.exe"',
        "private-key": "/keys/pk.pem",
        "client-id": "/keys/cid.bin",
        "key-mode-default": "Manual",
        "dynamic-mode-default": "Digitalcriminals",
        "cache-mode": "json",
        "ssl_verify": True,
        "enable_auto_after": False,
        "post_script": "echo",
        "timeline": "posts",
        "post": "timeline2",
        "archived": "arch",
        "discord": "https://example.invalid/hook",
    },
    "nested_legacy": {
        "config": {
            "main_profile": "main_profile",
            "file_options": {
                "save_location": "/data/save",
                "space-replacer": "-",
                "text_type_default": "word",
            },
            "download_options": {
                "file_size_max": "100MB",
                "length_min": 5,
                "filter": ["images"],
                "auto_resume": False,
                "max_post_count": "9",
            },
            "advanced_options": {
                "after_action_script": "a.sh",
                "naming_script": "n.sh",
                "logs_expire_time": "3",
                "ssl_verify": "certifi",
                "default_user_list": "main",
                "temp_dir": "'/tmp dir/'",
            },
            "scripts": {"skip_download_script": "s.sh"},
            "responsetype": {"post": "p", "message": "m"},
        }
    },
    "explicit_falsy": {
        "main_profile": "",
        "metadata": None,
        "discord": "",
        "file_options": {
            "save_location": "/data/save",
            "dir_format": "",
            "textlength": 0,
            "space_replacer": "",
            "date": "",
            "text_type_default": "",
            "truncation_default": False,
            "filename_collision": "",
        },
        "download_options": {
            "filter": [],
            "auto_resume": False,
            "system_free_min": 0,
            "max_post_count": 0,
            "verify_all_integrity": False,
        },
        "binary_options": {"ffmpeg": ""},
        "cdm_options": {"private-key": "", "client-id": None, "key-mode-default": ""},
        "performance_options": {"download_sems": 0, "download_limit": 0},
        "content_filter_options": {
            "block_ads": False,
            "file_size_max": 0,
            # "" would raise humanfriendly.InvalidSize, which isn't caught
            "file_size_min": 0,
            "length_max": 0,
            "length_min": False,
        },
        "advanced_options": {
            "dynamic-mode-default": "",
            "skip_unavailable_content": False,
            "downloadbars": False,
            "cache-mode": "",
            "rotate_logs": False,
            "sanitize_text": False,
            "temp_dir": "",
            "remove_hash_match": False,
            "infinite_loop_action_mode": False,
            "incremental_downloads": False,
            "default_user_list": [],
            "default_black_list": "",
            "logs_expire_time": 0,
            "ssl_verify": False,
            "env_files": [],
        },
        "script_options": {
            "after_action_script": "",
            "post_script": None,
            "naming_script": "",
            "after_download_script": False,
            "skip_download_script": "",
        },
        "responsetype": {"timeline": "", "message": None, "paid": False},
    },
}


def _schema_text(config, written=None):
    out = written if written is not None else schema.get_current_config_schema(config)
    out = copy.deepcopy(out)
    # the save location default is under the home folder
    default = of_env.getattr("SAVE_PATH_DEFAULT")
    if out["file_options"]["save_location"] == default:
        out["file_options"]["save_location"] = "<SAVE_PATH_DEFAULT>"
    return json.dumps(out, indent=4, sort_keys=False, default=repr)


def _schema_results(path):
    results = {}
    for name, config in SCHEMA_CONFIGS.items():
        results[name] = _schema_text(copy.deepcopy(config))
        if config is not False:
            config_file.auto_update_config(copy.deepcopy(config))
            written = json.loads(path.read_text(encoding="utf-8"))
            results[name + ":written"] = _schema_text(None, written)
    return results


EXPECTED_SCHEMA = {
    "false": "f0b5994259e22ccb",
    "empty": "f0b5994259e22ccb",
    "empty:written": "f0b5994259e22ccb",
    "flat_legacy": "b8cb0ac1bb9e775e",
    "flat_legacy:written": "b8cb0ac1bb9e775e",
    "nested_legacy": "feb9fce2a65c72e5",
    "nested_legacy:written": "feb9fce2a65c72e5",
    "explicit_falsy": "e727b5815322a045",
    "explicit_falsy:written": "e727b5815322a045",
}


def test_written_config_is_unchanged(builtin):
    results = _schema_results(builtin)
    _dump("schema", results)
    got = {name: _digest(text) for name, text in results.items()}
    assert got == EXPECTED_SCHEMA
