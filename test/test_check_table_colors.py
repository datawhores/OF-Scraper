"""Check table: the header labels use the terminal's palette colours.

Since textual 2, Static parses Textual markup, where blue, green, red, yellow
and cyan are fixed truecolours (#0000ff, ...), not the terminal's ANSI colours
that Rich markup gave on textual 1.0. Bold-blue labels came out dark blue on
the near-black background, and with NO_COLOR they turned the background's
colour and disappeared. The ansi_* names give the ANSI colours back.
"""

import asyncio
from types import SimpleNamespace

from textual.style import Style

import ofscraper.classes.table.app as table_app

# ANSI colour numbers
RED, GREEN, YELLOW, BLUE, CYAN = 1, 2, 3, 4, 6


class _Settings(SimpleNamespace):
    def __getattr__(self, name):
        return None


def test_header_labels_use_palette_colours(monkeypatch):
    monkeypatch.setattr(
        table_app.settings,
        "get_settings",
        lambda *a, **k: _Settings(db_sort="number", desc=False),
    )
    monkeypatch.setattr(
        table_app.settings,
        "get_args",
        lambda *a, **k: SimpleNamespace(text=False, text_only=False),
    )
    monkeypatch.setattr(table_app.settings, "update_args", lambda *a, **k: None)

    async def drive():
        app = table_app.InputApp()
        app.table_data = []  # also shows "All Items Filtered Out"
        app._sortkey = None
        app._reverse = False
        async with app.run_test(size=(240, 60)) as pilot:
            await pilot.pause()
            # the headers of the table, cart and console pages, after the
            # info and toggle labels have been filled in
            found = []
            for widget in app.query(".header_top_row Static"):
                content = widget.visual
                for span in getattr(content, "spans", []):
                    style = span.style
                    if isinstance(style, str):
                        style = Style.parse(style)
                    if style.foreground is not None:
                        label = str(content)[span.start : span.end]
                        found.append((label, style.foreground.ansi))
            return found

    found = asyncio.run(drive())
    assert [label for label, ansi in found if ansi is None] == []
    assert {ansi for _, ansi in found} == {RED, GREEN, YELLOW, BLUE, CYAN}
