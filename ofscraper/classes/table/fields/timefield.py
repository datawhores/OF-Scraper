from textual.containers import Container, Horizontal
from textual.widgets import Label

from ofscraper.classes.table.inputs.intergerinput import IntegerInput
import ofscraper.utils.settings as settings  # Reconnect to the source of truth


class TimeField(Container):
    DEFAULT_CSS = """
    TimeField {
        column-span: 4;
        height: auto;
    }

    TimeField Horizontal {
        height: auto;
    }

    /* as tall as the boxes, text on their middle line */
    TimeField .length_label {
        width: 2fr;
        height: 3;
        content-align: left middle;
    }

    .min_length, .max_length {
        width: 1fr;
    }
    """

    def __init__(self, name: str, label: str | None = None) -> None:
        name = name.lower()
        super().__init__(id=name)
        self.filter_name = name
        self.label_text = label or "Media Length (Hours 0-23, Min 0-59, Sec 0-59)"
        self.timeconversions = [60 * 60, 60, 1]

    def compose(self):
        yield Label(self.label_text)
        with Horizontal(id="minContainer"):
            yield Label("Min length", classes="length_label")
            yield IntegerInput(placeholder="Hours (0-23)", classes="min_length", id="min_hour")
            yield IntegerInput(placeholder="Min (0-59)", classes="min_length", id="min_minute")
            yield IntegerInput(placeholder="Sec (0-59)", classes="min_length", id="min_second")
        with Horizontal(id="maxContainer"):
            yield Label("Max length", classes="length_label")
            yield IntegerInput(placeholder="Hours (0-23)", classes="max_length", id="max_hour")
            yield IntegerInput(placeholder="Min (0-59)", classes="max_length", id="max_minute")
            yield IntegerInput(placeholder="Sec (0-59)", classes="max_length", id="max_second")

    def on_mount(self):
        min_val = getattr(settings.get_settings(), f"{self.filter_name}_min", None)
        max_val = getattr(settings.get_settings(), f"{self.filter_name}_max", None)

        if min_val is not None:
            self.update_table_min(min_val)
        if max_val is not None:
            self.update_table_max(max_val)

    def update_table_val(self, val):
        self.update_table_min(val)
        self.update_table_max(val)

    def update_table_min(self, val):
        self._fill("#minContainer", val)

    def update_table_max(self, val):
        self._fill("#maxContainer", val)

    def _fill(self, container, val):
        inputs = list(self.query_one(container).query(IntegerInput))
        if isinstance(val, (int, float)) or str(val).isnumeric():
            val = int(val)
            parts = [val // 3600, (val % 3600) // 60, val % 60]
        elif val != "N/A" and val != "N\\A":
            parts = [int(x) for x in str(val).split(":")]
        else:
            parts = [0, 0, 0]
        for box, part in zip(inputs, parts):
            box.value = str(part) if part else ""

    def reset(self):
        for ele in self.query(IntegerInput):
            ele.value = ""

    @staticmethod
    def _hms_to_seconds(value) -> int:
        if value in (None, "", "N\\A", "N/A"):
            return 0
        parts = [int(p) for p in str(value).split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return parts[0]

    def compare(self, value):
        min_sec = (
            int(self.query_one("#min_hour").value or 0) * 3600
            + int(self.query_one("#min_minute").value or 0) * 60
            + int(self.query_one("#min_second").value or 0)
        )
        max_sec = (
            int(self.query_one("#max_hour").value or 0) * 3600
            + int(self.query_one("#max_minute").value or 0) * 60
            + int(self.query_one("#max_second").value or 0)
        )
        if min_sec == 0 and max_sec == 0:
            return True
        try:
            cur_sec = self._hms_to_seconds(value)
        except (TypeError, ValueError):
            return False
        if max_sec == 0:
            return cur_sec >= min_sec
        if min_sec == 0:
            return cur_sec <= max_sec
        return min_sec <= cur_sec <= max_sec

    @property
    def key(self):
        return self.id.replace("_input", "")
