"""The download log says how many files download at once (#291).

1. Given the default settings, when a download starts, the log says it
   downloads up to 6 files at a time.
2. Given --download-sem 3, the log says 3.
3. Given the MAXFILE_SEMAPHORE override, the log shows that value.
"""

import asyncio
import logging
from types import SimpleNamespace

import pytest

import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.download import download
from ofscraper.utils.args.main import AutoDotDict
from ofscraper.utils.args.parse.commands.main import program


class _Stop(Exception):
    """Stops process_dicts right after the log line, before any download."""


def _settings_from(argv):
    params, _ = program.main(args=argv, standalone_mode=False, prog_name="OF-Scraper")
    args = AutoDotDict(params)
    args.command = "OF-Scraper"
    return args


@pytest.fixture
def start_download(monkeypatch, caplog):
    real_getattr = settings.of_env.getattr
    real_sems = settings.config_data.get_download_semaphores

    def run(argv, maxfile=None):
        def getattr_(key, *a, **k):
            if key == "MAXFILE_SEMAPHORE":
                return maxfile
            return real_getattr(key, *a, **k)

        monkeypatch.setattr(settings.of_env, "getattr", getattr_)
        # no download_sems in config.json, so the built-in default applies
        monkeypatch.setattr(
            settings.config_data,
            "get_download_semaphores",
            lambda *a, **k: real_sems(config={}),
        )
        monkeypatch.setattr(
            settings.read_args, "retriveArgs", lambda *a, **k: _settings_from(argv)
        )
        merged = settings.merged_settings()
        merged.text = False
        merged.text_only = False
        monkeypatch.setattr(settings, "get_settings", lambda: merged)

        def stop():
            raise _Stop

        monkeypatch.setattr(download.common_globals, "mainProcessVariableInit", stop)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with caplog.at_level(logging.INFO, logger="shared"):
                with pytest.raises(_Stop):
                    download.process_dicts("a creator", 1, [SimpleNamespace()], [])
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        return caplog.text

    return run


def test_default_settings_say_six_files(start_download):
    text = start_download([])
    assert "Downloading up to 6 files at a time" in text
    assert "single thread" not in text


def test_download_sem_option_sets_the_number(start_download):
    text = start_download(["--download-sem", "3"])
    assert "Downloading up to 3 files at a time" in text


def test_maxfile_semaphore_override_sets_the_number(start_download):
    text = start_download(["--download-sem", "3"], maxfile=9)
    assert "Downloading up to 9 files at a time" in text
