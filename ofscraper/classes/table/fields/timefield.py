from textual.containers import Container, Horizontal
from textual.widgets import Label

from ofscraper.classes.table.inputs.intergerinput import IntegerInput
from ofscraper.classes.table.status import status


class TimeField(Container):
    DEFAULT_CSS = """
    TimeField{
    column-span:4;
    row-span:2;
    }

    TimeField Label{
    width:2fr;
    }

    .min_length,.max_length{
    width:1fr;
    }

    
"""

    def __init__(self, name: str) -> None:
        name = name.lower()
        super().__init__(id=name)
        self.filter_name = name
        self.timeconversions = [60 * 60, 60, 1]

    def compose(self):
        with Horizontal(id="minContainer"):
            yield Label("MinLength")
            yield IntegerInput(placeholder="Hour", classes="min_length", id="min_hour")
            yield IntegerInput(placeholder="Min", classes="min_length", id="min_minute")
            yield IntegerInput(placeholder="Sec", classes="min_length", id="min_second")
        with Horizontal(id="maxContainer"):
            yield Label("MaxLength")
            yield IntegerInput(placeholder="Hour", classes="max_length", id="max_hour")
            yield IntegerInput(placeholder="Min", classes="max_length", id="max_minute")
            yield IntegerInput(placeholder="Sec", classes="max_length", id="max_second")

    def empty(self):
        return len(list(filter(lambda x: x.value != "", self.query(IntegerInput)))) == 0

    def update_table_val(self, val):
        self.update_table_min(val)
        self.update_table_max(val)

    def update_table_min(self, val):
        minLenthInputs = list(self.query_one("#minContainer").query(IntegerInput))
        if isinstance(val, int) or str(val).isnumeric():
            val = int(val)
            hours = val // 3600
            minutes = (val % 3600) // 60
            seconds = val % 60

        elif val != "N/A" and val != "N\A":
            valArray = val.split(":")
            hours, minutes, seconds = valArray
        else:
            hours, minutes, seconds = 0, 0, 0
        for pack in zip(minLenthInputs, [hours, minutes, seconds]):
            pack[0].value = str(pack[1])

    def update_table_max(self, val):
        maxLenthInputs = list(self.query_one("#maxContainer").query(IntegerInput))
        if isinstance(val, int) or str(val).isnumeric():
            val = int(val)
            hours = val // 3600
            minutes = (val % 3600) // 60
            seconds = val % 60

        elif val != "N/A" and val != "N\A":
            valArray = val.split(":")
            hours, minutes, seconds = valArray
        else:
            hours, minutes, seconds = 0, 0, 0
        for pack in zip(maxLenthInputs, [hours, minutes, seconds]):
            pack[0].value = str(pack[1])

    def reset(self):
        for ele in self.query(IntegerInput):
            ele.value = ""

    def on_input_changed(self, input):
        key = input.input.id.lower()
        out_key = next(
            (x for x in input.input.classes if x in {"max_length", "min_length"}), None
        )
        status[out_key][key] = input.input.value

    @property
    def key(self):
        return self.id.replace("_input", "")
