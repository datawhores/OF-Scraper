from ofscraper.classes.table.inputs.filterinput import FilterInput
from ofscraper.classes.table.status import status


class IntegerInput(FilterInput):
    def __init__(self,*args, **kwargs):
        super().__init__(*args,type="integer",**kwargs)

    def on_input_changed(self):
        status[self.key] = int(self.value) if self.value else ""

    def on_input_submitted(self):
        status[self.key] = int(self.value) if self.value else ""