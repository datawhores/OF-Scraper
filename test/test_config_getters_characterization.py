"""Pins what every getter in ofscraper/utils/config/data.py returns.

auto_update_config rebuilds config.json from these getters and writes it
back, so a getter that returns something different for any input changes
users' files on disk. Each getter is run over a matrix of configs (missing
key, top-level value, nested value, both, None, falsy values, wrong types,
older key names, broken sections) and the results are compared, as a digest,
with the ones recorded from the code before the getters were refactored. The
written config is pinned the same way for a few representative files.

A deliberate behaviour change updates the digests: dump the results before
and after it, diff them, check every changed row comes from that change, and
record the new digests in the same commit.

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
    "get_database_url_note": ["database_url", "advanced_options.database_url"],
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
# the refactor and updated only by deliberate fixes
EXPECTED_GETTERS = {
    "get_main_profile": (25, "13e26f74f27d2d82"),
    # a note, not a setting: the same text whatever the file holds
    "get_database_url_note": (166, "547aefc30f48fa7d"),
    "get_filesize_max": (712, "b813936078f849ae"),
    "get_filesize_min": (403, "fba4568c65171252"),
    "get_min_length": (403, "b6017c91205f6c89"),
    "get_max_length": (403, "0fc6df1c5c397ced"),
    "get_system_freesize": (166, "2976375f5c7ed168"),
    "get_dirformat": (166, "a98c32de7d434761"),
    "get_fileformat": (166, "df593acb238c4e09"),
    "get_textlength": (166, "8952bb91a9c802a4"),
    "get_date": (166, "915bf3a3ccf54ecf"),
    "get_InfiniteLoop": (166, "47da2a266f2fb14a"),
    "get_incremental_downloads": (379, "36f831d66c82762a"),
    "get_default_userlist": (166, "e126bfc743c978c2"),
    "get_default_blacklist": (166, "9b8e95a97c907b6f"),
    "get_logs_expire": (166, "7d69eaa69b9ac057"),
    "get_ssl_verify": (166, "eb0d01bd3b25af97"),
    "get_after_action_script": (403, "ad7fdaf7391c96f9"),
    "get_post_script": (736, "a9b5f1c70ee0e89b"),
    "get_naming_script": (736, "81bb95241465f41a"),
    "get_skip_download_script": (736, "c11cf8e1d3e2c615"),
    "get_after_download_script": (736, "e3f2a5ce42744547"),
    "get_env_files": (736, "d0e4591d14ceb82e"),
    "get_metadata": (25, "ecd7e87b9954b3f6"),
    "get_download_limit": (166, "0f6815c9c7e420eb"),
    "get_ffmpeg": (166, "7944e02855f7ab6a"),
    "get_discord": (25, "4a67da123ed05ee2"),
    "get_filter": (403, "ff590fc36291677e"),
    "responsetype": (25, "53a4934f2f2dd932"),
    "get_timeline_responsetype": (706, "9e1867e8daabe60b"),
    "get_post_responsetype": (706, "1bfbaf9b9704c59a"),
    "get_archived_responsetype": (166, "007d63e19bf58af0"),
    "get_stories_responsetype": (166, "2eed61853558e2fa"),
    "get_highlights_responsetype": (166, "62e1650feb87e50f"),
    "get_paid_responsetype": (166, "9341b22b958926aa"),
    "get_messages_progress_responsetype": (166, "80471ba5cd211a19"),
    "get_profile_responsetype": (166, "9ccfae453e5b4441"),
    "get_pinned_responsetype": (166, "8104e2e0361df31c"),
    "get_streams_responsetype": (166, "306ad50c9ba6bfd2"),
    "get_spacereplacer": (379, "1d5fb59f35b02f64"),
    "get_private_key": (166, "0b8c2980d5203ba5"),
    "get_client_id": (166, "c47f6c3ad54ad06f"),
    # default cdrm -> manual: cdrm is deprecated
    "get_key_mode": (166, "47f07a3be33295dc"),
    "get_dynamic": (166, "5d329d06d09f54c6"),
    "get_dynamic_configured": (166, "cb19e4e268db322e"),
    "get_part_file_clean": (397, "2d28652912f25bcc"),
    "get_download_semaphores": (166, "8ae57a60bc5a0948"),
    "get_show_downloadprogress": (166, "235cf0a39a14098d"),
    "get_cache_mode": (166, "a0450f7f49077c85"),
    "cache_mode_helper": (166, "ae4c59ee2a88fc50"),
    "get_rotate_logs": (166, "d1be220bf0aaec16"),
    "get_sanitizeDB": (166, "d278d06c49ae2110"),
    "get_textType": (166, "0c8fc144f2a029de"),
    "get_TempDir": (166, "660c4409002ec9ae"),
    "get_filename_collision": (166, "70646025830a0396"),
    "get_truncation": (166, "c47fe1c30e91f54e"),
    "get_max_post_count": (166, "bb95b231004fd78e"),
    "get_hash": (166, "d94ff68a8e2de411"),
    "get_block_ads": (166, "78fead4ec1ca7144"),
    "get_skip_unavailable_content": (166, "4e72972e29925cd3"),
    "get_verify_all_integrity": (166, "46f2b559a75fcef2"),
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
            "file_size_min": "",
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


# flat_legacy sets its key mode; the others take the default, now manual
EXPECTED_SCHEMA = {
    "false": "25df51e4abe3c47b",
    "empty": "25df51e4abe3c47b",
    "empty:written": "25df51e4abe3c47b",
    "flat_legacy": "384d63ec957bf2ed",
    "flat_legacy:written": "384d63ec957bf2ed",
    "nested_legacy": "757f497b89ca2989",
    "nested_legacy:written": "757f497b89ca2989",
    "explicit_falsy": "13578dd7de7e4174",
    "explicit_falsy:written": "13578dd7de7e4174",
}


def test_written_config_is_unchanged(builtin):
    results = _schema_results(builtin)
    _dump("schema", results)
    got = {name: _digest(text) for name, text in results.items()}
    assert got == EXPECTED_SCHEMA
