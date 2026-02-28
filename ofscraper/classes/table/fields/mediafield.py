from textual.widgets import SelectionList
from textual.widgets.selection_list import Selection
from ofscraper.classes.table.fields.selectfield import SelectField
import ofscraper.utils.settings as settings  # Reconnect to the source of truth


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

        # 1. Fetch the active media types from the config right now
        active_media = settings.get_settings().mediatypes or [
            "Audios",
            "Videos",
            "Images",
        ]
        # 2. Harden the capitalization
        active_media = [m.capitalize() for m in active_media]

        self._videos = Selection(
            "Videos",
            value="Videos",
            id=f"{self.filter_name}_videos",
            initial_state="Videos" in active_media,
        )
        self._audios = Selection(
            "Audios",
            value="Audios",
            id=f"{self.filter_name}_audios",
            initial_state="Audios" in active_media,
        )
        self._images = Selection(
            "Images",
            value="Images",
            id=f"{self.filter_name}_images",
            initial_state="Images" in active_media,
        )

    def compose(self):
        yield SelectionList(self._videos, self._images, self._audios)

    def compare(self, value):
        if not value:
            return False
        return str(value).capitalize() in self.query_one(SelectionList).selected

    def update_table_val(self, val):
        self.query_one(SelectionList).deselect_all()
        val_cap = str(val).capitalize()
        if val_cap in ["Videos", "Audios", "Images"]:
            self.query_one(SelectionList).select(val_cap)
