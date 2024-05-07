from textual.containers import Horizontal

from ofscraper.classes.table.inputs.intergerinput import IntegerInput


class PriceField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield IntegerInput(placeholder="Min Price", id=f"{self.filter_name}_search")
        yield IntegerInput(placeholder="Max Price", id=f"{self.filter_name}_search2")

    def empty(self):
        return (
            self.query(IntegerInput)[0].value == ""
            and self.query(IntegerInput)[1].value == ""
        )

    def update_table_val(self, val):
        if val.lower() == "free":
            val = "0"
        for ele in self.query(IntegerInput):
            ele.value = val

    def reset(self):
        self.query_one(IntegerInput).value = ""

    def validate(self, val):
        minval = self.query_one(f"#{self.filter_name}_search").value
        maxval = self.query_one(f"#{self.filter_name}_search2").value
        if val.lower() == "free":
            val = 0
        if not maxval and not minval:
            return True
        elif minval and float(val) < float(minval):
            return False
        elif maxval and float(val) > float(maxval):
            return False
        return True
