from textual.containers import Horizontal
from ofscraper.classes.table.inputs.intergerinput import PostiveIntegerInput

class NumField(Horizontal):
    Field=PostiveIntegerInput
    def __init__(self, name: str, default=None) -> None:
        name = name.lower()
        super().__init__(id=name)
        self.filter_name = name
        self._set_default(default)
        

    def _set_default(self, default):
        self.default = str(default if str(default).isnumeric() else "")

    def compose(self):
        yield self.Field(
            placeholder=self.filter_name.capitalize().replace("_", " "),
            id=f"{self.filter_name}_input",
            value=self.default,
        )



    def update_table_val(self, val):
        if isinstance(val, list):
            val = ",".join(val)
        if not str(val).isnumeric():
            return
        self.query_one(self.Field).value = str(val)
        return val

    def reset(self):
        self.query_one(self.Field).value = self.default
    def compare(self, value):
        if self.query_one(self.Field).value=="":
            return True
        return int(self.query_one(self.Field).value)==int(value)
    @property
    def integer_input(self):
        return self.query_one(self.Field)

class PostiveNumField(NumField):
    Field=PostiveIntegerInput
    def compose(self):
        yield self.Field(
            placeholder=self.filter_name.capitalize().replace("_", " "),
            id=f"{self.filter_name}_input",
            value=self.default,
        )
