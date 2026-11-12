import re

from textual import events

from ofscraper.classes.table.inputs.filterinput import FilterInput


class PostiveIntegerInput(FilterInput):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, type="integer", restrict=r"^(?!0+$)\d*$", valid_empty=True, **kwargs
        )

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
