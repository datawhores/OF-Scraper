from ofscraper.utils import settings
from textual.widgets import SelectionList

from ofscraper.classes.table.fields.selectfield import SelectField
from textual.widgets.selection_list import Selection
import ofscraper.utils.settings as settings


class DownloadField(SelectField):
    DEFAULT_CSS = """
    DownloadField {
    column-span:3;
    row-span:3;
    }
    """

    def __init__(self, name: str) -> None:
        name = name.lower()
        super().__init__(name=name, classes="container")
        self.filter_name = name
        dl_type = settings.get_settings().download_type
        # If None, both are checked. If "normal", only normal is checked, etc.
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
