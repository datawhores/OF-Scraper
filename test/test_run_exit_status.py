import logging

import pytest

import ofscraper.main.open.run as run


def _fail():
    raise RuntimeError("simulated failure")


def test_failed_run_exits_with_status_1_and_logs_the_error(monkeypatch):
    monkeypatch.setattr(run, "start_manager", _fail)
    monkeypatch.setattr(run.exit_manager, "shutdown", lambda: None)
    records = []
    handler = logging.Handler(level=logging.ERROR)
    handler.emit = records.append
    logger = logging.getLogger("shared")
    logger.addHandler(handler)
    try:
        with pytest.raises(SystemExit) as exit_info:
            run.main()
    finally:
        logger.removeHandler(handler)
    assert exit_info.value.code == 1
    assert any("simulated failure" in r.getMessage() for r in records)


def test_successful_run_returns_normally(monkeypatch):
    monkeypatch.setattr(run, "start_manager", lambda: None)
    run.main()
