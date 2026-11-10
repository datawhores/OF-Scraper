"""The status line printed before a scrape says what the auth check found."""

import pytest

import ofscraper.data.api.init as init


@pytest.mark.parametrize(
    "status, shown, not_shown",
    [
        ("UP", "UP", "DOWN"),
        ("DOWN", "DOWN", "UP"),
        # a network or server problem says nothing about the auth
        ("UNAVAILABLE", "Couldn't check", "DOWN"),
    ],
)
def test_status_line(monkeypatch, status, shown, not_shown):
    printed = []
    monkeypatch.setattr(init, "getstatus", lambda: status)
    monkeypatch.setattr(
        init.console,
        "get_shared_console",
        lambda: type("Console", (), {"print": lambda self, text: printed.append(text)})(),
    )
    init.print_sign_status()
    assert len(printed) == 1
    assert shown in printed[0]
    assert not_shown not in printed[0]
