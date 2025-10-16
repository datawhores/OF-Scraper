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
        name = name.lower()
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield Input(
            placeholder=f"{self.filter_name.capitalize()} Search",
            id=f"{self.filter_name}_search",
        )
        yield Checkbox("Exact Match", False, id="exact_match")


    def update_table_val(self, val):
        self.query_one(Input).value = val

    def reset(self):
        self.query_one(f"#{self.filter_name}_search").value = ""
        self.query_one("#exact_match").value = False
    def compare(self,value):
        if self.query_one(f"#{self.filter_name}_search").value=="":
            return True
        return self.query_one(f"#{self.filter_name}_search").value.lower() ==value.lower() if self.query_one("#exact_match").value else re.search(self.query_one(f"#{self.filter_name}_search").value, value, flags=re.IGNORECASE) is not None
