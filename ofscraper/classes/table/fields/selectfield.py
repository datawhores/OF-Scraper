from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import SelectionList
from textual.widgets.selection_list import Selection


class SelectField(Widget):
    DEFAULT_CSS = """
        SelectField{
        row-span:2;
        column-span:2;

        }
    """

    def __init__(self, name: str, classes=None) -> None:
        name = name.lower()
        super().__init__(id=name, classes=classes)
        self.filter_name = name
        self._true = Selection(
            f"{self.filter_name} True",
            value="True",
            disabled=False,
            id=f"{self.filter_name}_true",
            initial_state=True,
        )
        self._false = Selection(
            f"{self.filter_name} False",
            value="False",
            disabled=False,
            id=f"{self.filter_name}_false",
            initial_state=True,
        )

    def compare(self, value):
        return value in self.query_one(SelectionList).selected

    def compose(self):
        with Horizontal():
            yield SelectionList(
                self._true,
                self._false,
            )

    def reset(self):
        for ele in self.query(SelectionList):
            ele.select_all()

    def update_table_val(self, val):
        if val == "True":
            self.select_true()
        elif val == "False":
            self.select_false()

    def select_true(self):
        self.query_one(SelectionList).deselect_all()
        self.query_one(SelectionList).select(self._true)

    def select_false(self):
        self.query_one(SelectionList).deselect_all()
        self.query_one(SelectionList).select(self._false)
