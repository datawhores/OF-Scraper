from textual.containers import Vertical
from textual.widgets import Label
from ofscraper.classes.table.inputs.intergerinput import PostiveIntegerInput
import ofscraper.utils.settings as settings


class NumField(Vertical):
    Field = PostiveIntegerInput

    DEFAULT_CSS = """
    NumField {
        height: auto;
    }
    """

    def __init__(self, name: str, default=None, label: str | None = None) -> None:
        name = name.lower()
        super().__init__(id=name)
        self.filter_name = name
        clean_title = name.replace("post_post_", "post_").replace("post_", "").replace("_", " ").title()
        self.label_text = label or f"{clean_title} (exact)"
        setting_val = getattr(settings.get_settings(), self.filter_name, None)
        if setting_val:
            if isinstance(setting_val, list):
                setting_val = ",".join(map(str, setting_val))
            self._set_default(setting_val)
        else:
            self._set_default(default)

    def _set_default(self, default):
        self.default = str(default if str(default).isnumeric() else "")

    def compose(self):
        yield Label(self.label_text)
        clean_placeholder = self.filter_name.replace("post_post_", "post_").replace("post_", "").replace("_", " ").title()
        yield self.Field(
            placeholder=f"{clean_placeholder} (e.g. 12345)",
            id=f"{self.filter_name}_input",
            value=self.default,
        )

    def update_table_val(self, val):
        if isinstance(val, list):
            val = ",".join(val)
        if not str(val).isnumeric():
            return
        self.query_one(self.Field).value = str(val)
        return val

    def reset(self):
        self.query_one(self.Field).value = self.default

    def compare(self, value):
        target = self.query_one(self.Field).value.strip()
        if target == "":
            return True
        try:
            return int(target) == int(value)
        except (TypeError, ValueError):
            return False

    @property
    def integer_input(self):
        return self.query_one(self.Field)


class PostiveNumField(NumField):
    Field = PostiveIntegerInput

    def __init__(self, name: str, default=None, label: str | None = None) -> None:
        super().__init__(name, default=default, label=label or "Min New Media (at least N)")

    def compose(self):
        yield Label(self.label_text)
        yield self.Field(
            placeholder="Min New Media (e.g. 1)",
            id=f"{self.filter_name}_input",
            value=self.default,
        )
