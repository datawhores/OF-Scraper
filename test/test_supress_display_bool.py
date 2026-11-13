"""SUPRESS_*_DISPLAY set to False shows the display (#256).

Environment values are text, and the text "False" is truthy, so any value
hid the display. Unset still leaves the console as the output options set it.
"""

import pytest
from rich.console import Console

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.console as console
import ofscraper.utils.live.screens as screens
import ofscraper.utils.of_env.of_env as of_env

KEYS = [
    "SUPRESS_API_DISPLAY",
    "SUPRESS_DOWNLOAD_DISPLAY",
    "SUPRESS_SUBSCRIPTION_DISPLAY",
    "SUPRESS_LIKE_DISPLAY",
]
VALUES = [("False", False), ("false", False), ("0", False), ("True", True), ("1", True)]


class _Live:
    renderable = None
    is_started = True

    def update(self, *a, **k):
        pass


@pytest.fixture
def env(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(f"OFSC_{key}", raising=False)
    of_env.get_all_configs(forced=True)
    monkeypatch.setattr(screens, "get_live", lambda: _Live())
    yield monkeypatch
    monkeypatch.undo()
    of_env.get_all_configs(forced=True)


def _quiet_after_entering(monkeypatch, key, start=None):
    """Enter a screen with this suppress key; return the console's quiet."""
    con = Console(quiet=bool(start))
    monkeypatch.setattr(console, "shared_console", con)
    with screens.ProgressLayoutManager(layout=None, supress_key=key):
        return con.quiet


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("text,hidden", VALUES)
def test_ofsc_variable(env, key, text, hidden):
    env.setenv(f"OFSC_{key}", text)
    of_env.get_all_configs(forced=True)
    assert of_env.getattr(key) is hidden
    assert _quiet_after_entering(env, key) is hidden


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("text,hidden", VALUES)
def test_bare_key_variable(env, key, text, hidden):
    env.setenv(key, text)
    assert of_env.getattr(key) is hidden
    assert _quiet_after_entering(env, key) is hidden


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("start", [False, True])
def test_unset_leaves_console_as_it_was(env, key, start):
    assert of_env.getattr(key) is None
    assert _quiet_after_entering(env, key, start) is start
