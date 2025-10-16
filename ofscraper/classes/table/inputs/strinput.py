from ofscraper.classes.table.inputs.filterinput import FilterInput


class StrInput(FilterInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, type="text", **kwargs)
    def compare(self, value):
        if self.value == "":
            return True
        return value.lower() == self.value.lower()