from textual.containers import Horizontal, Vertical
from textual.widgets import Label
from ofscraper.classes.table.inputs.intergerinput import IntegerInput


class PriceField(Vertical):
    DEFAULT_CSS = """
    PriceField {
        column-span: 4;
        row-span: 2;
        height: auto;
    }

    PriceField Horizontal {
        height: auto;
    }

    PriceField IntegerInput {
        width: 1fr;
    }
    """

    def __init__(self, name: str, label: str | None = None) -> None:
        name = name.lower()
        super().__init__(id=name)
        self.filter_name = name
        self.label_text = label or "Price (USD, e.g. 0 = Free, 5, 20; blank = any)"

    def compose(self):
        yield Label(self.label_text)
        with Horizontal():
            yield IntegerInput(placeholder="Min Price (e.g. 0)", id=f"{self.filter_name}_min")
            yield IntegerInput(placeholder="Max Price (e.g. 25)", id=f"{self.filter_name}_max")

    def update_table_val(self, val):
        if val.lower() == "free":
            val = "0"
        for ele in self.query(IntegerInput):
            ele.value = val

    def reset(self):
        for ele in self.query(IntegerInput):
            ele.value = ""

    def compare(self, value):
        val_lower = str(value).lower()
        if val_lower == "free":
            value = "0"
        maxvalue = float(self.query_one(f"#{self.filter_name}_max").value or 0)
        minvalue = float(self.query_one(f"#{self.filter_name}_min").value or 0)
        if not maxvalue and not minvalue:
            return True
        return float(value) >= minvalue and float(value) <= maxvalue
