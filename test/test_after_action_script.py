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
