from textual.widgets import SelectionList

from ofscraper.classes.table.fields.selectfield import SelectField
from textual.widgets.selection_list import Selection


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
        self._normal=Selection("Normal Download",value="normal",disabled=False,id=f"{self.filter_name}_normal",initial_state=True)
        self._protected=Selection("Protected Download",value="protected",disabled=False,id=f"{self.filter_name}_protected",initial_state=True)

    def compose(self):
        yield SelectionList(
                self._normal,self._protected
        )

    def update_table_val(self, val):
        self.query_one(SelectionList).deselect_all()
        if val == "normal":
            self.query_one(SelectionList).select(self._normal)
        elif val == "protected":
            self.query_one(SelectionList).select(self._protected)
        elif val=="n/a":
            self.query_one(SelectionList).select(self._protected)
            self.query_one(SelectionList).select(self._normal)


    def compare(self, value):
        if not self._protected.value in self.query_one(SelectionList).selected:
            return value in self.query_one(SelectionList).selected
        elif not self._normal.value in self.query_one(SelectionList).selected:
            return value in self.query_one(SelectionList).selected
        return True
