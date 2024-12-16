from ofscraper.classes.table.inputs.filterinput import FilterInput
from ofscraper.classes.table.status import status


class StrInput(FilterInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, type="text", **kwargs)

    def on_input_changed(self):
        status[self.key] = self.value

    def on_input_submitted(self):
        status[self.key] = self.value
