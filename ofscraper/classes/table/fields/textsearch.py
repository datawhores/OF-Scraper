import re

from textual.containers import Horizontal
from textual.widgets import Checkbox, Input


class TextSearch(Horizontal):
    DEFAULT_CSS = """
        TextSearch Input{
    width:3fr;
    }

    TextSearch Checkbox{
     width:2fr;
    }

     TextSearch {
    column-span:4;
    }
    
"""

    def __init__(self, name: str) -> None:
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield Input(
            placeholder=f"{self.filter_name.capitalize()} Search",
            id=f"{self.filter_name}_search",
        )
        yield Checkbox("FullString", False, id="fullstring_search")

    def empty(self):
        return self.query_one(Input).value == ""

    def update_table_val(self, val):
        self.query_one(Input).value = val

    def reset(self):
        self.query_one(Input).value = ""

    def validate(self, val):
        if self.query_one(Input).value == "" or self.query_one(Input).value is None:
            return True
        elif self.query_one(Checkbox).value and re.fullmatch(
            self.query_one(Input).value,
            str(val),
            (re.IGNORECASE if self.query_one(Input).islower() else 0),
        ):
            return True
        elif not self.query_one(Checkbox).value and re.search(
            self.query_one(Input).value,
            str(val),
            (re.IGNORECASE if self.query_one(Input).value.islower() else 0),
        ):
            return True
        return False
