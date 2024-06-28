from textual.containers import Horizontal

from ofscraper.classes.table.inputs.intergerinput import IntegerInput


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
        return self.query_one(IntegerInput).value == ""

    def update_table_val(self, val):
        self.query_one(IntegerInput).value = val

    def reset(self):
        self.query_one(IntegerInput).value = ""


class OtherMediaNumField(NumField):
    def empty(self):
        return self.query_one(IntegerInput).value == ""

    def update_table_val(self, val):
        val = str(len(eval(val)))
        self.query_one(IntegerInput).value = val

    def reset(self):
        self.query_one(IntegerInput).value = ""
