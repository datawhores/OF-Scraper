from textual.widgets import SelectionList

from ofscraper.classes.table.fields.selectfield import SelectField
from textual.widgets.selection_list import Selection


class MediaField(SelectField):
    DEFAULT_CSS = """
    MediaField {
    column-span:3;
    row-span:3;
    }
    """
    def __init__(self, name: str) -> None:
        name = name.lower()
        super().__init__(name=name, classes="container")
        self.filter_name = name
        self._videos=Selection("Videos",value="videos",disabled=False,id=f"{self.filter_name}_videos",initial_state=True)
        self._audios=Selection("Audios",value="audios",disabled=False,id=f"{self.filter_name}_audios",initial_state=True)
        self._images=Selection("Images",value="images",disabled=False,id=f"{self.filter_name}_images",initial_state=True)

    def compose(self):
        yield SelectionList(
                self._videos, self._images,self._audios
        )

    def update_table_val(self, val):
        self.query_one(SelectionList).deselect_all()
        if val == "videos":
            self.query_one(SelectionList).select(self._videos)
        elif val == "audios":
            self.query_one(SelectionList).select(self._audios)

        elif val == "images":
            self.query_one(SelectionList).select(self._images)