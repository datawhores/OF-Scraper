from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Label, SelectionList
from textual.widgets.selection_list import Selection

import ofscraper.utils.settings as settings  # Bring in the source of truth


class SelectField(Widget):
    DEFAULT_CSS = """
    SelectField {
        column-span: 4;
        height: auto;
    }
    SelectField SelectionList {
        height: auto;
    }
    /* Vertical defaults to height 1fr, which inside an auto-height field
       made each filter about 70 rows tall */
    SelectField Vertical, SelectField Horizontal {
        height: auto;
    }
    """

    def __init__(self, name: str, classes=None, label: str | None = None) -> None:
        name = name.lower()
        super().__init__(id=name, classes=classes)
        self.filter_name = name
        clean_name = name.replace("post_", "").capitalize()
        self.label_text = label or f"{clean_name} Status"

        setting_val = getattr(settings.get_settings(), self.filter_name, None)
        true_state = (setting_val is True) or (setting_val is None)
        false_state = (setting_val is False) or (setting_val is None)

        self._true = Selection(
            f"{self.filter_name.capitalize()} True",
            value="True",
            disabled=False,
            id=f"{self.filter_name}_true",
            initial_state=true_state,
        )
        self._false = Selection(
            f"{self.filter_name.capitalize()} False",
            value="False",
            disabled=False,
            id=f"{self.filter_name}_false",
            initial_state=false_state,
        )

    def compare(self, value):
        return value in self.query_one(SelectionList).selected

    def compose(self):
        with Vertical():
            yield Label(self.label_text)
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
        self.query_one(SelectionList).select("True")

    def select_false(self):
        self.query_one(SelectionList).deselect_all()
        self.query_one(SelectionList).select("False")
