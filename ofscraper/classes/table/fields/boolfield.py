from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Checkbox


class BoolField(Widget):
    def __init__(self, name: str) -> None:
        name = name.lower()
        super().__init__(id=name, classes="container")
        self.filter_name = name

    def compose(self):
        with Horizontal():
            yield Checkbox(
                f"{self.filter_name.capitalize()} True",
                True,
                id=f"{self.filter_name}_true",
            )
            yield Checkbox(
                f"{self.filter_name.capitalize()} False",
                True,
                id=f"{self.filter_name}_false",
            )

    def reset(self):
        for ele in self.query(Checkbox):
            ele.value = True

    def update_table_val(self, val):
        if val == "True":
            self.query_one(f"#{self.filter_name}_true").value = True
            self.query_one(f"#{self.filter_name}_false").value = False
        elif val == "False":
            self.query_one(f"#{self.filter_name}_false").value = True
            self.query_one(f"#{self.filter_name}_true").value = False

