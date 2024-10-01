from textual.containers import Horizontal

from ofscraper.classes.table.inputs.intergerinput import IntegerInput
from ofscraper.classes.table.status import status



class NumField(Horizontal):
    def __init__(self, name: str) -> None:
        name = name.lower()
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield IntegerInput(
            placeholder=self.filter_name.capitalize().replace("_", " "),
            id=f"{self.filter_name}_input",
        )

    def empty(self):
        status[self.filter_name] = ""
        return self.query_one(IntegerInput).value == ""


    def update_table_val(self, val):
        if isinstance(val,list):
            val=",".join(val)
        val=self.query_one(IntegerInput).validate_value(val)
        self.query_one(IntegerInput).value = val
        status[self.filter_name] = val
        return val


    def reset(self):
        self.query_one(IntegerInput).value = ""
        status[self.filter_name] = ""


class OtherMediaNumField(NumField):
    def empty(self):
        status[self.filter_name] = ""
        return self.query_one(IntegerInput).value == ""

    def update_table_val(self, val):
        val = str(len(eval(val)))
        self.query_one(IntegerInput).value = val
        status[self.filter_name] = val


    def reset(self):
        self.query_one(IntegerInput).value = ""
        status[self.filter_name] = ""

