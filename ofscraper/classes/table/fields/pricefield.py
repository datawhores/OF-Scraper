from textual.containers import Horizontal, Vertical
from textual.widgets import Label
from ofscraper.classes.table.inputs.intergerinput import IntegerInput


class PriceField(Vertical):
    DEFAULT_CSS = """
    PriceField {
        column-span: 4;
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
        cleaned = str(val or "").strip().lstrip("$").replace(",", "")
        if cleaned.lower() in {"free", "unlocked"}:
            cleaned = "0"
        for ele in self.query(IntegerInput):
            ele.value = cleaned

    def reset(self):
        for ele in self.query(IntegerInput):
            ele.value = ""

    def compare(self, value):
        raw_min = self.query_one(f"#{self.filter_name}_min").value.strip()
        raw_max = self.query_one(f"#{self.filter_name}_max").value.strip()
        if not raw_min and not raw_max:
            return True
        val_str = str(value or "").strip().lstrip("$").replace(",", "").lower()
        if val_str in {"free", "unlocked", ""}:
            numeric = 0.0
        else:
            try:
                numeric = float(val_str)
            except ValueError:
                return False
        if raw_min and numeric < float(raw_min):
            return False
        if raw_max and numeric > float(raw_max):
            return False
        return True

