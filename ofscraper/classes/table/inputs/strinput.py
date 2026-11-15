from ofscraper.classes.table.inputs.filterinput import FilterInput


class StrInput(FilterInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, type="text", **kwargs)

    def update_table_val(self, val):
        self.value = val

    def reset(self):
        self.value = ""

    def compare(self, value):
        if self.value == "":
            return True
        # part of a name is enough
        return self.value.strip().lower() in str(value).lower()
