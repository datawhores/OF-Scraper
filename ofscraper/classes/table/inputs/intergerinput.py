import re

from textual import events

from ofscraper.classes.table.inputs.filterinput import FilterInput


class PostiveIntegerInput(FilterInput):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, type="integer", restrict=r"^(?!0+$)\d*$", valid_empty=True, **kwargs
        )

    def _on_click(self, event: events.Click) -> None:
        # a right-click pastes what was last copied in the app (a right-click
        # in the table, or Ctrl+C in a text box), in place of the box's
        # value. Other text comes in by the terminal's own paste, which only
        # the terminal can read
        if event.button != 3 or self.id not in ("media_id_input", "post_id_input"):
            return
        event.stop()
        text = self.app.clipboard
        if not text:
            self.app.notify(
                "Nothing copied here yet. "
                "Use your terminal's paste key for other text."
            )
            return
        self.select_all()
        self._on_paste(events.Paste(text))

    def _on_paste(self, event: events.Paste) -> None:
        if self.id not in ("media_id_input", "post_id_input"):
            return

        event.prevent_default()
        event.stop()
        text = event.text.strip()
        # media.py builds tempaudio_{media_id}_{post_id} and tempvid equivalents.
        match = re.search(r"temp(?:audio|vid)_(\d+)_(\d+)", text)
        if match:
            self.value = match.group(1 if self.id == "media_id_input" else 2)
        elif text.isdecimal():
            super()._on_paste(events.Paste(text))
        else:
            self.app.notify("Enter a number or a temp file name.")


class IntegerInput(FilterInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, type="integer", valid_empty=True, **kwargs)
