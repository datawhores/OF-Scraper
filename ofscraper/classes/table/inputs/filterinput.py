from typing import Any

from textual.widgets import Input

from ofscraper.classes.table.status import status


class FilterInput(Input):
    def __init__(self, *args: Any, placeholder=None, **kwargs: Any) -> None:
        """Initialise the input."""
        placeholder = placeholder or kwargs.get("id") or "placeholder"
        super().__init__(*args, placeholder=placeholder, **kwargs)
        # TODO: Workaround for https://github.com/Textualize/textual/issues/1216
        self.value = self.validate_value(self.value)

    def validate_value(self, value: str) -> str:
        """Validate the input.

        Args:
            value: The value to validate.

        Returns:
            The acceptable value.
        """
        # If the input field isn't empty...
        if value.strip():
            try:
                # ...run it through the casting function. We don't care
                # about what comes out of the other end, we just case that
                # it makes it through at all.
                _ = self.CAST(value)
            except ValueError:
                # It's expected that the casting function will throw a
                # ValueError if there's a problem with the conversion (see
                # int and float for example) so, here we are. Make a
                # noise...
                self.app.bell()
                # ...and return what's in the input now because we're
                # rejecting the new value.
                return self.value
        # The value to test is either empty, or valid. Let's accept it.
        return value

    def update_table_val(self, val):
        self.value = self.validate_value(val)

    def on_input_changed(self):
        status[self.key] = self.value

    def on_input_submitted(self):
        status[self.key] = self.value

    @property
    def key(self):
        return self.id.replace("_input", "")
