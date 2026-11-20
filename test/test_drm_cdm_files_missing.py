"""Manual key mode without usable CDM files.

Each DRM video used to be downloaded in full, then fail to decrypt with
"Is a directory: '.'" (a blank path) or FileNotFoundError, retried, with a
traceback per attempt, and count as failed. Now it isn't downloaded: it's
counted as skipped, with an info line saying the keys are missing, and isn't
saved as done, so it downloads once the keys are set. The startup check says
the keys weren't detected.
"""

import asyncio
import io
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from rich.console import Console

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.commands.scraper.actions.download.managers.alt_download as alt_download
import ofscraper.commands.scraper.actions.download.utils.keyhelpers as keyhelpers
import ofscraper.utils.system.network as network


def _settings(monkeypatch, key_mode="manual", client_id="", private_key=""):
    monkeypatch.setattr(
        keyhelpers.settings,
        "get_settings",
        lambda: SimpleNamespace(key_mode=key_mode, client_id=client_id, private_key=private_key),
    )


def test_names_each_missing_file(monkeypatch, tmp_path):
    _settings(monkeypatch, client_id="", private_key=tmp_path / "missing.pem")
    missing = keyhelpers.missing_cdm_keys()
    assert "client-id is not set" in missing
    assert "private-key file not found" in missing


def test_nothing_missing_when_both_files_exist(monkeypatch, tmp_path):
    for name in ("client_id.bin", "private_key.pem"):
        (tmp_path / name).write_bytes(b"x")
    _settings(monkeypatch, client_id=tmp_path / "client_id.bin", private_key=tmp_path / "private_key.pem")
    assert keyhelpers.missing_cdm_keys() is None


def test_other_key_modes_are_not_checked(monkeypatch):
    _settings(monkeypatch, key_mode="cdrm")
    assert keyhelpers.missing_cdm_keys() is None


def test_drm_video_is_skipped_with_an_info_line(monkeypatch):
    _settings(monkeypatch)
    monkeypatch.setattr(alt_download.stop, "started", lambda ele: None)
    monkeypatch.setattr(alt_download.common_logs, "get_medialog", lambda ele: "media")
    placeholders = Mock(side_effect=AssertionError("download started"))
    monkeypatch.setattr(alt_download.placeholder, "Placeholders", placeholders)
    log = Mock()
    manager = SimpleNamespace(ctx=SimpleNamespace(log=log), _force_download=AsyncMock())

    result = asyncio.run(
        alt_download.AltDownloadManager._alt_download_item(
            manager, None, SimpleNamespace(), "a creator", 1
        )
    )

    assert result == ("forced_skipped", 0)  # counted as skipped, not failed
    placeholders.assert_not_called()
    manager._force_download.assert_not_called()  # not saved as done
    log.info.assert_called_once()
    assert "DRM video skipped: CDM keys not found" in log.info.call_args.args[0]
    log.error.assert_not_called()
    log.warning.assert_not_called()


@pytest.fixture
def screen(monkeypatch):
    import ofscraper.sites as sites

    monkeypatch.setattr(sites, "is_fansly", lambda: False)
    buf = io.StringIO()
    loud = Console(file=buf, width=300)
    quiet = Console(file=io.StringIO(), quiet=True)
    # --no-rich and low output quiet the shared console; the message still shows
    monkeypatch.setattr(network.console_, "get_console", lambda: loud)
    monkeypatch.setattr(network.console_, "get_shared_console", lambda: quiet)
    return buf


def test_startup_says_the_keys_are_not_detected(monkeypatch, screen, caplog):
    _settings(monkeypatch)
    with caplog.at_level(logging.INFO, logger="shared"):
        assert network.check_cdm() is True
    out = screen.getvalue()
    assert "CDM keys not detected" in out
    assert "may affect the download of files with DRM" in out
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_startup_is_silent_when_the_keys_are_there(monkeypatch, screen, tmp_path):
    for name in ("client_id.bin", "private_key.pem"):
        (tmp_path / name).write_bytes(b"x")
    _settings(monkeypatch, client_id=tmp_path / "client_id.bin", private_key=tmp_path / "private_key.pem")
    assert network.check_cdm() is True
    assert "not detected" not in screen.getvalue()
