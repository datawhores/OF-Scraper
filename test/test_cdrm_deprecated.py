"""Key mode cdrm is deprecated: its service, cdrm-project.com, no longer works
(and it was sent the OnlyFans cookies).

New configs default to manual, and a run that still uses cdrm warns on the
console and in the log. A config that already says cdrm keeps it.
"""

import io
import logging
from types import SimpleNamespace

import pytest
from rich.console import Console

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.config.data as data
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.system.network as network


def test_default_key_mode_is_manual(monkeypatch):
    monkeypatch.delenv("OFSC_KEY_DEFAULT", raising=False)
    assert of_env.getattr("KEY_DEFAULT") == "manual"
    assert data.get_key_mode(config={"cdm_options": {}}) == "manual"


def test_a_config_that_says_cdrm_keeps_it():
    assert data.get_key_mode(config={"cdm_options": {"key-mode-default": "cdrm"}}) == "cdrm"


class _Records(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def screen(monkeypatch):
    import ofscraper.sites as sites

    monkeypatch.setattr(sites, "is_fansly", lambda: False)
    buf = io.StringIO()
    con = Console(file=buf, width=300)
    monkeypatch.setattr(network.console_, "get_console", lambda: con)
    monkeypatch.setattr(network.console_, "get_shared_console", lambda: con)
    handler = _Records()
    shared = logging.getLogger("shared")
    shared.addHandler(handler)
    # setLevel, not the attribute: it also clears the logger's level cache
    level, disabled = shared.level, shared.disabled
    shared.setLevel(logging.DEBUG)
    shared.disabled = False
    yield SimpleNamespace(buf=buf, records=handler.records)
    shared.removeHandler(handler)
    shared.setLevel(level)
    shared.disabled = disabled


def _key_mode(monkeypatch, mode):
    monkeypatch.setattr(
        network.settings,
        "get_settings",
        lambda: SimpleNamespace(key_mode=mode, client_id=None, private_key=None),
    )


def test_cdrm_warns_once_and_does_not_probe_the_service(monkeypatch, screen):
    _key_mode(monkeypatch, "cdrm")
    assert network.check_cdm() is False
    out = screen.buf.getvalue()
    assert out.count("cdrm is deprecated") == 1
    assert "CDM service" not in out  # the service isn't asked
    # in the log at debug: a warning record would print it on the console again
    assert not [r for r in screen.records if r.levelno >= logging.WARNING]
    assert any("cdrm is deprecated" in r.getMessage() for r in screen.records)


def test_check_mode_does_not_call_the_deprecation_an_error(monkeypatch, screen):
    import ofscraper.commands.check as check

    _key_mode(monkeypatch, "cdrm")

    class _Stop(Exception):
        pass

    def stop(**kwargs):  # the first step after the CDM check
        raise _Stop

    monkeypatch.setattr(check.operations, "table_init_create", stop)
    monkeypatch.setattr(check._process_user_batch, "counter", 0)
    with pytest.raises(_Stop):
        check._process_user_batch("a", 1, [], [], [])
    messages = [r.getMessage() for r in screen.records]
    assert any(m.startswith("CDM check failed;") for m in messages)
    assert not any("raised an error" in m for m in messages)


def test_manual_does_not_warn(monkeypatch, screen):
    _key_mode(monkeypatch, "manual")
    assert network.check_cdm() is True
    assert "deprecated" not in screen.buf.getvalue()
    assert not [r for r in screen.records if r.levelno >= logging.WARNING]
