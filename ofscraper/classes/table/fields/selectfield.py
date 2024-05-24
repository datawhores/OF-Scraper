from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import SelectionList

from ofscraper.classes.table.status import status


class SelectField(Widget):
    def __init__(self, name: str, classes=None) -> None:
        name = name.lower()
        super().__init__(id=name, classes=classes)
        self.filter_name = name

    def compose(self):
        with Horizontal():
            yield SelectionList(
                *[
                    (f"{self.filter_name.capitalize()} True", True, True),
                    (f"{self.filter_name.capitalize()} False", False, True),
                ]
            )

    def reset(self):
        for ele in self.query(SelectionList):
            ele.select_all()

    def update_table_val(self, val):
        if val == "True":
            self.query_one(f"#{self.filter_name}_true").value = True
            self.query_one(f"#{self.filter_name}_false").value = False
        elif val == "False":
            self.query_one(f"#{self.filter_name}_false").value = True
            self.query_one(f"#{self.filter_name}_true").value = False

    def on_selection_list_selected_changed(self, checkbox):
        key = self.id.lower()
        status.status[key] = checkbox.selection_list.selected

    def update_table_val(self, val):
        select = self.query(SelectionList)[0]
        select.deselect_all()
        select.select(val)
