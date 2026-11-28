import logging
from types import SimpleNamespace

import pytest

import ofscraper.scripts.after_action_script as after_action
from ofscraper.scripts.after_download_action_script import after_download_action_script
from ofscraper.scripts.after_like_action_script import after_like_action_script


@pytest.mark.parametrize(
    "fn",
    [after_download_action_script, after_like_action_script],
    ids=["download", "like"],
)
def test_missing_username_key_logs_error_instead_of_unbound_local(
    monkeypatch, tmp_path, caplog, fn
):
    script = tmp_path / "after.py"
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        after_action.settings,
        "get_settings",
        lambda: SimpleNamespace(after_action_script=str(script)),
    )
    monkeypatch.setattr(after_action.dry_run, "active", lambda: False)
    monkeypatch.setattr(
        after_action.manager,
        "Manager",
        SimpleNamespace(
            current_model_manager=SimpleNamespace(get_model=lambda name: {"id": 42})
        ),
    )

    logger = logging.getLogger("shared")
    monkeypatch.setattr(logger, "traceback_", lambda *a, **k: None, raising=False)
    with caplog.at_level(logging.INFO, logger="shared"):
        fn("creator_a", [])

    assert any(
        "unexpected error" in rec.getMessage() and "creator_a" in rec.getMessage()
        for rec in caplog.records
    )


def test_none_media_does_not_crash_and_runs_script(monkeypatch, tmp_path, caplog):
    import json

    script = tmp_path / "after.py"
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        after_action.settings,
        "get_settings",
        lambda: SimpleNamespace(after_action_script=str(script)),
    )
    monkeypatch.setattr(after_action.dry_run, "active", lambda: False)
    monkeypatch.setattr(
        after_action.manager,
        "Manager",
        SimpleNamespace(
            current_model_manager=SimpleNamespace(
                get_model=lambda name: {"username": name, "id": 42}
            )
        ),
    )
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["payload"] = json.loads(kwargs["input"])

    monkeypatch.setattr(after_action, "run", fake_run)
    with caplog.at_level(logging.INFO, logger="shared"):
        after_download_action_script("creator_a", None)

    assert captured["cmd"] == [str(script)]
    assert captured["payload"]["media"] == []
    assert captured["payload"]["posts"] == []
    assert any("after download action script" in rec.getMessage().lower() for rec in caplog.records)


def test_called_process_error_with_none_stdout_stderr(monkeypatch, tmp_path, caplog):
    import subprocess

    script = tmp_path / "after.py"
    script.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        after_action.settings,
        "get_settings",
        lambda: SimpleNamespace(after_action_script=str(script)),
    )
    monkeypatch.setattr(after_action.dry_run, "active", lambda: False)
    monkeypatch.setattr(
        after_action.manager,
        "Manager",
        SimpleNamespace(
            current_model_manager=SimpleNamespace(
                get_model=lambda name: {"username": name, "id": 42}
            )
        ),
    )

    def fail_run(*args, **kwargs):
        raise subprocess.CalledProcessError(2, [str(script)], output=None, stderr=None)

    monkeypatch.setattr(after_action, "run", fail_run)
    with caplog.at_level(logging.DEBUG, logger="shared"):
        after_like_action_script("creator_a", [])

    assert any(
        "failed for creator_a with exit code 2" in rec.getMessage()
        for rec in caplog.records
    )

