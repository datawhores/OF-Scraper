import re
import arrow
from textual.containers import Container, Horizontal
from textual.widgets import Input
import ofscraper.utils.settings as settings  # Reconnect to truth


class DateField(Container):
    DEFAULT_CSS = """
    #minDate{
        width:50%;
    }

    #maxDate{
        width:50%;
    }
    
    DateField{
        row-span:2;
    }
    """

    def __init__(self, name: str) -> None:
        name = name.lower()
        super().__init__(id=name, classes="container")
        self.filter_name = name

    def compose(self):
        with Horizontal():
            yield Input(placeholder="Earliest Date", id="minDate")
            yield Input(placeholder="Latest Date", id="maxDate")

    def on_mount(self):
        """
        Self-Aware Logic: Maps 'post_date' to settings 'posted_after' / 'posted_before'
        Runs immediately after the widget is drawn.
        """
        # Map filter_name to the config prefix (e.g., 'post_date' becomes 'posted')
        prefix = "posted" if self.filter_name == "post_date" else self.filter_name

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
        if val != "":
            self.query_one("#minDate").value = arrow.get(val).format("YYYY.MM.DD")
        else:
            self.query_one("#minDate").value = ""

    def update_max_val(self, val):
        val = self.convertString(val)
        if val != "":
            self.query_one("#maxDate").value = arrow.get(val).format("YYYY.MM.DD")
        else:
            self.query_one("#maxDate").value = ""

    def reset(self):
        for ele in self.query(Input):
            ele.value = ""

    def convertString(self, val):
        val = str(val)
        match = re.search(r"[0-9-/\.]+", val)
        if not match:
            return ""
        return match.group(0)

    def compare(self, value):
        value = arrow.get(value).floor("day")
        min_val = (
            arrow.get(self.query_one("#minDate").value)
            if self.query_one("#minDate").value
            else arrow.get(0)
        )
        max_val = (
            arrow.get(self.query_one("#maxDate").value)
            if self.query_one("#maxDate").value
            else arrow.now()
        )
        return arrow.get(value).is_between(min_val, max_val, bounds="[]")
