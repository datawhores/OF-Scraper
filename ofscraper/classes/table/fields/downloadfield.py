from ofscraper.utils import settings
from textual.widgets import Label, SelectionList

from ofscraper.classes.table.fields.selectfield import SelectField
from textual.widgets.selection_list import Selection


class DownloadField(SelectField):
    DEFAULT_CSS = """
    DownloadField {
        column-span: 3;
        row-span: 4;
        height: auto;
    }
    """

    def __init__(self, name: str, label: str | None = None) -> None:
        name = name.lower()
        super().__init__(name=name, classes="container")
        self.filter_name = name
        self.label_text = label or "Download Type (Normal vs DRM/Protected)"
        dl_type = settings.get_settings().download_type
        normal_state = dl_type in ["normal", None]
        protected_state = dl_type in ["protected", None]

        self._normal = Selection(
            "Normal Download",
            value="normal",
            id=f"{self.filter_name}_normal",
            initial_state=normal_state,
        )
        self._protected = Selection(
            "Protected Download",
            value="protected",
            id=f"{self.filter_name}_protected",
            initial_state=protected_state,
        )

    def compose(self):
        yield Label(self.label_text)
        yield SelectionList(self._normal, self._protected)

    def update_table_val(self, val):
        self.query_one(SelectionList).deselect_all()
        if val == "normal":
            self.query_one(SelectionList).select(self._normal)
        elif val == "protected":
            self.query_one(SelectionList).select(self._protected)
        elif val == "n/a":
            self.query_one(SelectionList).select(self._protected)
            self.query_one(SelectionList).select(self._normal)

    def select_protected(self):
        self.query_one(SelectionList).deselect_all()
        self.query_one(SelectionList).select(self._protected)

    def select_normal(self):
        self.query_one(SelectionList).deselect_all()
        self.query_one(SelectionList).select(self._normal)

    def compare(self, value):
        if self._protected.value not in self.query_one(SelectionList).selected:
            return value in self.query_one(SelectionList).selected
        elif self._normal.value not in self.query_one(SelectionList).selected:
            return value in self.query_one(SelectionList).selected
        return True
