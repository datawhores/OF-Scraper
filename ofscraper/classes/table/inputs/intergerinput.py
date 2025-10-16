from ofscraper.classes.table.inputs.filterinput import FilterInput


class PostiveIntegerInput(FilterInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, type="integer",restrict="^(?!0+$)\d*$",valid_empty=True, **kwargs)
class IntegerInput(FilterInput):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, type="integer",valid_empty=True, **kwargs)
