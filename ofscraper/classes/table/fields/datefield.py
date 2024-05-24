import re

import arrow
from textual.containers import Container, Horizontal
from textual.widgets import Input

from ofscraper.classes.table.status import status


class DateField(Container):
    DEFAULT_CSS = """
    #minDate{
        width:50%;
    }

    #maxDate{
        width:50%;

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

    def empty(self):
        return self.query(Input)[0].value == "" and self.query(Input)[1].value == ""

    def update_table_val(self, val):
        val = self.convertString(val)
        for ele in self.query(Input):
            if val != "":
                ele.value = arrow.get(val).format("YYYY.MM.DD")
            else:
                ele.value = ""

    def reset(self):
        for ele in self.query(Input):
            ele.value = ""

    def on_input_changed(self, input):
        key = input.input.id.lower()
        status.status[key] = input.input.value

    def convertString(self, val):
        match = re.search("[0-9-/\.]+", val)
        if not match:
            return ""
        return match.group(0)
