import re
import arrow
from textual.containers import Container, Horizontal
from textual.widgets import Input, Label
import ofscraper.utils.settings as settings  # Reconnect to truth


class DateField(Container):
    DEFAULT_CSS = """
    DateField {
        column-span: 4;
        height: auto;
    }

    DateField Horizontal {
        height: auto;
    }

    DateField Input {
        width: 50%;
    }
    """

    def __init__(self, name: str, label: str | None = None) -> None:
        name = name.lower()
        super().__init__(id=name, classes="container")
        self.filter_name = name
        self.label_text = label or "Post Date (YYYY.MM.DD or YYYY-MM-DD)"

    def compose(self):
        yield Label(self.label_text)
        with Horizontal():
            min_id = "minDate" if self.filter_name == "post_date" else f"{self.filter_name}_minDate"
            max_id = "maxDate" if self.filter_name == "post_date" else f"{self.filter_name}_maxDate"
            yield Input(placeholder="Earliest (e.g. 2025.01.01)", id=min_id)
            yield Input(placeholder="Latest (e.g. 2026.12.31)", id=max_id)

    def on_mount(self):
        """
        Self-Aware Logic: Maps 'post_date' to settings 'posted_after' / 'posted_before'
        Runs immediately after the widget is drawn.
        """
        prefix = "posted" if self.filter_name in {"post_date", "post_post_date"} else self.filter_name

        min_val = getattr(settings.get_settings(), f"{prefix}_after", None)
        max_val = getattr(settings.get_settings(), f"{prefix}_before", None)

        if min_val:
            self.update_min_val(min_val)
        if max_val:
            self.update_max_val(max_val)

    def update_table_val(self, val):
        val = self.convertString(val)
        for ele in self.query(Input):
            if val != "":
                ele.value = arrow.get(val).format("YYYY.MM.DD")
            else:
                ele.value = ""

    def update_min_val(self, val):
        val = self.convertString(val)
        target = "#minDate" if self.filter_name == "post_date" else f"#{self.filter_name}_minDate"
        self.query_one(target).value = arrow.get(val).format("YYYY.MM.DD") if val != "" else ""

    def update_max_val(self, val):
        val = self.convertString(val)
        target = "#maxDate" if self.filter_name == "post_date" else f"#{self.filter_name}_maxDate"
        self.query_one(target).value = arrow.get(val).format("YYYY.MM.DD") if val != "" else ""

    def reset(self):
        for ele in self.query(Input):
            ele.value = ""

    def convertString(self, val):
        val = str(val)
        match = re.search(r"[0-9-/\.]+", val)
        if not match:
            return ""
        return match.group(0)

    def _parse_bound(self, raw):
        raw = str(raw or "").strip()
        if not raw:
            return None
        try:
            return arrow.get(self.convertString(raw) or raw).floor("day")
        except Exception:
            return None

    def compare(self, value):
        min_id = "#minDate" if self.filter_name == "post_date" else f"#{self.filter_name}_minDate"
        max_id = "#maxDate" if self.filter_name == "post_date" else f"#{self.filter_name}_maxDate"
        min_val = self._parse_bound(self.query_one(min_id).value)
        max_val = self._parse_bound(self.query_one(max_id).value)
        # an empty or unreadable bound is no limit; with neither set the
        # filter is off and keeps rows without a date
        if min_val is None and max_val is None:
            return True
        raw_val = str(value or "").strip()
        if not raw_val or raw_val == "Probably Deleted":
            return False
        try:
            parsed = arrow.get(raw_val).floor("day")
        except Exception:
            extracted = self.convertString(raw_val)
            if not extracted:
                return False
            try:
                parsed = arrow.get(extracted).floor("day")
            except Exception:
                return False
        if min_val is not None and parsed < min_val:
            return False
        if max_val is not None and parsed > max_val:
            return False
        return True

