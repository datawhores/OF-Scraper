"""config.json and auth.json load whatever encoding a hand edit saved them in (#691).

They're read as UTF-8 (a BOM is fine), then as the system's local encoding
(Notepad's "ANSI") when that fails, and written as UTF-8. Before, open()'s
default decided: the ANSI code page on Windows with Python 3.11 to 3.14 (a
UTF-8 file came out garbled, a BOM broke the JSON), UTF-8 from 3.15 (an ANSI
file couldn't be read). Each test runs under both defaults with a stand-in
cp1252 code page, so it means the same on any OS and Python version.
"""

import builtins
import json

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.auth.utils.dict as auth_dict
import ofscraper.utils.auth.utils.error as auth_error
import ofscraper.utils.config.config as config_
import ofscraper.utils.config.file as config_file
import ofscraper.utils.config.utils.context as context
import ofscraper.utils.interactive as interactive
import ofscraper.utils.paths.common as common_paths

SAVE_PATH = "C:/T\u00e9l\u00e9chargements/ofs"  # an accented save path
BOM = b"\xef\xbb\xbf"
# saved as: (start of file, how the text is encoded)
SAVED_AS = {
    "utf-8": (b"", "utf-8"),
    "utf-8 with BOM": (BOM, "utf-8"),
    "ANSI (cp1252)": (b"", "cp1252"),
}


def _file(saved_as, key, complete=True):
    start, encoding = SAVED_AS[saved_as]
    text = f'{{"{key}": "{SAVE_PATH}"' + ("}" if complete else "")
    return start + text.encode(encoding)


@pytest.fixture(params=["cp1252", "utf-8"], ids=["windows-py3.11", "windows-py3.15"])
def system_encoding(request, monkeypatch):
    """Windows with a cp1252 code page, whatever this machine is: open()
    defaults to the code page up to Python 3.14 and to UTF-8 from 3.15."""
    real_open = builtins.open

    def default_open(file, mode="r", *args, **kwargs):
        if "b" not in mode and not args:
            kwargs.setdefault("encoding", request.param)
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", default_open)
    monkeypatch.setattr("locale.getencoding", lambda: "cp1252")
    return request.param


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    monkeypatch.setattr(config_, "config", None)  # read_config's cache


@pytest.fixture
def config_path(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    monkeypatch.setattr(common_paths, "get_config_path", lambda: path)
    return path


@pytest.fixture
def auth_path(monkeypatch, tmp_path):
    path = tmp_path / "auth.json"
    monkeypatch.setattr(common_paths, "get_auth_file", lambda: path)
    return path


@pytest.mark.parametrize("saved_as", list(SAVED_AS))
def test_config_loads_with_the_right_characters(config_path, system_encoding, saved_as):
    config_path.write_bytes(_file(saved_as, "save_location"))
    assert config_file.open_config() == {"save_location": SAVE_PATH}


@pytest.mark.parametrize("saved_as", list(SAVED_AS))
def test_auth_loads_with_the_right_characters(auth_path, system_encoding, saved_as):
    auth_path.write_bytes(_file(saved_as, "sess"))
    assert auth_dict.get_auth_dict() == {"sess": SAVE_PATH}


@pytest.mark.parametrize("saved_as", list(SAVED_AS))
def test_invalid_config_still_reaches_the_syntax_error_prompt(
    monkeypatch, config_path, system_encoding, saved_as
):
    config_path.write_bytes(_file(saved_as, "save_location", complete=False))
    asked = []

    def ask():
        asked.append(1)
        raise interactive.NoConsoleError("no console")

    monkeypatch.setattr(context.prompts, "reset_config_prompt", ask)
    with pytest.raises(interactive.NoConsoleError):
        config_file.open_config()
    assert asked == [1]


@pytest.mark.parametrize("saved_as", list(SAVED_AS))
def test_invalid_auth_still_raises_a_json_error(auth_path, system_encoding, saved_as):
    auth_path.write_bytes(_file(saved_as, "sess", complete=False))
    with pytest.raises(json.JSONDecodeError):
        auth_dict.get_auth_dict()


def test_hand_edited_auth_is_written_as_utf8(monkeypatch, auth_path, system_encoding):
    edited = json.dumps({"sess": SAVE_PATH}, ensure_ascii=False)
    monkeypatch.setattr(auth_error.prompts, "manual_auth_prompt", lambda text: edited)
    auth_error._manual_auth("{}")
    assert auth_path.read_bytes() == edited.encode("utf-8")
    assert auth_dict.get_auth_dict() == {"sess": SAVE_PATH}


@pytest.mark.parametrize("saved_as", list(SAVED_AS))
def test_fansly_auth_loads_with_the_right_characters(tmp_path, system_encoding, saved_as):
    import ofscraper.sites.fansly.auth as fansly_auth

    path = tmp_path / "fansly_auth.json"
    path.write_bytes(_file(saved_as, "user_agent"))
    fansly_auth._cache.update(path=None, mtime=None, auth=None)
    assert fansly_auth.read_auth(path)["user_agent"] == SAVE_PATH


@pytest.mark.parametrize("saved_as", list(SAVED_AS))
def test_invalid_fansly_auth_still_raises_a_json_error(tmp_path, system_encoding, saved_as):
    import ofscraper.sites.fansly.auth as fansly_auth

    path = tmp_path / "fansly_auth.json"
    path.write_bytes(_file(saved_as, "user_agent", complete=False))
    fansly_auth._cache.update(path=None, mtime=None, auth=None)
    with pytest.raises(json.JSONDecodeError):
        fansly_auth.read_auth(path)
