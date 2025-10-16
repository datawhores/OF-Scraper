from typing import Any

from textual.widgets import Input



class FilterInput(Input):
    def __init__(self, *args: Any, placeholder=None, **kwargs: Any) -> None:
        """Initialise the input."""
        placeholder = placeholder or kwargs.get("id") or "placeholder"
        super().__init__(*args, placeholder=placeholder, **kwargs)
        # TODO: Workaround for https://github.com/Textualize/textual/issues/1216

    @property
    def key(self):
        return self.id.replace("_input", "")
