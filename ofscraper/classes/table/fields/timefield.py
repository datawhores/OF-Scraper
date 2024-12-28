import arrow
from textual.containers import Container, Horizontal
from textual.widgets import Label

from ofscraper.classes.table.inputs.intergerinput import IntegerInput


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
    def compare(self,value):

        max_val=arrow.get(
                "{hour}:{minute}:{second}".format(
                    hour= self.query_one("#max_hour").value or 0,
                    minute= self.query_one("#max_minute").value or 0,
                    second= self.query_one("#max_second").value or 0,
                ),
                ["h:m:s"],
            )
        min_val=arrow.get(
                "{hour}:{minute}:{second}".format(
                    hour= self.query_one("#min_hour").value or 0,
                    minute= self.query_one("#min_minute").value or 0,
                    second= self.query_one("#min_second").value or 0,
                ),
                ["h:m:s"],
            )
        if min_val==max_val and min_val==arrow.get("0:0:0",["h:m:s"]):
            return True
        elif max_val==arrow.get("0:0:0",["h:m:s"]):
            return arrow.get(value,["h:m:s"])>min_val
        elif min_val==arrow.get("0:0:0",["h:m:s"]):
            return arrow.get(value,["h:m:s"])<max_val
        else:
            return arrow.get("0:0:0" if value in {"N\A","N/A"} else value,["h:m:s"]).is_between(min_val,max_val,bounds="[]")

    @property
    def key(self):
        return self.id.replace("_input", "")
