from textual.containers import Horizontal

from ofscraper.classes.table.inputs.intergerinput import IntegerInput
from ofscraper.classes.table.status import status


class NumField(Horizontal):
    def __init__(self, name: str, default=None) -> None:
        name = name.lower()
        super().__init__(id=name)
        self.filter_name = name
        self._set_default(default)

    def _set_default(self, default):
        self.default = str(default if str(default).isnumeric() else "")

    def compose(self):
        yield IntegerInput(
            placeholder=self.filter_name.capitalize().replace("_", " "),
            id=f"{self.filter_name}_input",
            value=self.default,
        )

    def empty(self):
        self.query_one(IntegerInput).value = self.default
        return self.query_one(IntegerInput).value

    def update_table_val(self, val):
        if isinstance(val, list):
            val = ",".join(val)
        if not str(val).isnumeric():
            return
        self.query_one(IntegerInput).value = str(val)
        return val

    def reset(self):
        self.query_one(IntegerInput).value = self.default


class OtherMediaNumField(NumField):
    def empty(self):
        self.query_one(IntegerInput).value = self.default
        return self.query_one(IntegerInput).value

    def update_table_val(self, val):
        val = str(val)
        self.query_one(IntegerInput).value = val

    def reset(self):
        self.query_one(IntegerInput).value = self.default
