import re

from textual.containers import Horizontal, Vertical
from textual.widgets import Checkbox, Input, Label


class TextSearch(Vertical):
    DEFAULT_CSS = """
    TextSearch {
        column-span: 4;
        height: auto;
    }

    TextSearch Horizontal {
        height: auto;
    }

    TextSearch Input {
        width: 3fr;
    }

    TextSearch Checkbox {
        width: 2fr;
    }
    """

    def __init__(self, name: str, label: str | None = None) -> None:
        name = name.lower()
        super().__init__(id=name)
        self.filter_name = name
        self.label_text = label or "Post Text (partial/regex; Exact = full text)"

    def compose(self):
        yield Label(self.label_text)
        with Horizontal():
            yield Input(
                placeholder=f"{self.filter_name.replace('post_', '').capitalize()} Search (e.g. solo or vid.*)",
                id=f"{self.filter_name}_search",
            )
            exact_id = "exact_match" if self.filter_name == "text" else f"{self.filter_name}_exact_match"
            yield Checkbox("Exact Match", False, id=exact_id)

    def update_table_val(self, val):
        self.query_one(Input).value = val

    def reset(self):
        self.query_one(f"#{self.filter_name}_search").value = ""
        self.query_one("#exact_match" if self.filter_name == "text" else f"#{self.filter_name}_exact_match").value = False

    def compare(self, value):
        search_val = self.query_one(f"#{self.filter_name}_search").value
        if search_val == "":
            return True
        exact = self.query_one("#exact_match" if self.filter_name == "text" else f"#{self.filter_name}_exact_match").value
        if exact:
            return search_val.lower() == value.lower()
        return re.search(search_val, value, flags=re.IGNORECASE) is not None
