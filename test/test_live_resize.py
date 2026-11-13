"""Resizing starts the shared live display's next frame on a clean screen."""

import io

import pytest
from rich.console import Console
from rich.panel import Panel

import ofscraper.main.open.load  # noqa: F401 (import order, see conftest)
import ofscraper.utils.live.live as live_mod


@pytest.mark.parametrize("dimension,smaller", [("width", 40), ("height", 10)])
def test_live_clears_once_per_resize(monkeypatch, dimension, smaller):
    monkeypatch.setenv("TERM", "xterm")
    output = io.StringIO()
    console = Console(
        file=output, force_terminal=True, force_interactive=True, width=80, height=24,
        legacy_windows=False,
    )
    monkeypatch.setattr(live_mod.console_, "get_shared_console", lambda: console)
    monkeypatch.setattr(live_mod, "live", None)
    live = live_mod.get_live()
    live.auto_refresh = False  # Drive refreshes deterministically in this test.
    original = getattr(console, dimension)
    try:
        live_mod.start_live(Panel("first line\nsecond line", title="Activity Progress"))
        live.refresh()
        assert "\x1b[2J" not in output.getvalue()

        for size, clears in [(smaller, 1), (original, 2)]:
            offset = len(output.getvalue())
            setattr(console, dimension, size)
            live.refresh()
            frame = output.getvalue()[offset:]
            assert frame.startswith("\x1b[2J\x1b[H")
            assert "\x1b[1A" not in frame  # No stale cursor-up after clearing.
            assert "Activity Progress" in frame
            assert output.getvalue().count("\x1b[2J") == clears
            live.refresh()
            live.refresh()
            assert output.getvalue().count("\x1b[2J") == clears
    finally:
        live_mod.stop_live()
