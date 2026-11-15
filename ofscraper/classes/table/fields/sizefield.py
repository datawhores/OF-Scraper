from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Static

import ofscraper.utils.settings as settings
from ofscraper.utils.sizes import TB, UNITS, format_size, parse_whole_number, split_size

HINT = "Whole numbers only. Empty or 0 = no limit."
# a single file can't sensibly be larger than this
MAX_SIZE = TB


class SizeField(Vertical):
    """A download size limit: a whole number and a Bytes/KB/MB/GB button.

    The setting is still saved in bytes (0 for no limit), as soon as the box
    or the unit changes. Only a size over 1 TB is refused (shown as an error,
    and the previous value stays in effect). A minimum above the maximum is
    applied with a warning: the number is often typed before its unit, so the
    two boxes pass through such a state while they're being filled in.
    """

    DEFAULT_CSS = """
    SizeField {
        height: auto;
    }

    SizeField .size_row, SizeField .size_units {
        height: auto;
    }

    SizeField Label {
        width: 10;
        padding: 1 1 0 1;
    }

    SizeField Input {
        width: 1fr;
    }

    SizeField .size_units {
        padding-left: 10;
    }

    SizeField .size_units Button {
        min-width: 7;
        margin-right: 1;
    }

    SizeField .size_hint {
        padding-left: 10;
        color: $text-muted;
    }

    SizeField .size_hint.-error {
        color: $error;
        text-style: bold;
    }

    SizeField .size_hint.-warning {
        color: $warning;
        text-style: bold;
    }
    """

    LABEL = ""
    SETTING = ""
    OTHER = None

    def __init__(self, name: str) -> None:
        self.filter_name = name.lower()
        super().__init__(id=self.filter_name)
        current = getattr(settings.get_settings(), self.SETTING, None)
        self.default_number, self.default_unit = split_size(current)
        self.unit = self.default_unit
        self.applied = self.default_number * self.default_unit

    def compose(self):
        with Horizontal(classes="size_row"):
            yield Label(self.LABEL)
            yield Input(
                value=str(self.default_number) if self.default_number else "",
                placeholder="0 = no limit",
                id=f"{self.filter_name}_input",
                restrict=r"[0-9]*",
                max_length=13,
            )
        with Horizontal(classes="size_units"):
            for label, unit in UNITS:
                yield Button(
                    label,
                    id=self._button_id(unit),
                    compact=True,
                    variant="primary" if unit == self.unit else "default",
                )
        yield Static(HINT, classes="size_hint")

    # --- values -----------------------------------------------------------

    def _button_id(self, unit):
        return f"{self.filter_name}_unit_{unit}"

    @property
    def input(self):
        return self.query_one(Input)

    def requested_size(self):
        """The size the box and the unit button ask for, in bytes, or None."""
        number = parse_whole_number(self.input.value)
        return None if number is None else number * self.unit

    def error_for(self, size):
        """Why ``size`` can't be applied at all, or None."""
        if size is None:
            return "Enter a whole number (0, 1, 2, ...)."
        if size > MAX_SIZE:
            return f"At most {format_size(MAX_SIZE)}; {format_size(size)} is too large."
        return None

    def range_warning(self, size):
        """Why ``size`` together with the other box downloads nothing, or None."""
        return None

    def _other(self):
        if self.OTHER is None:
            return None
        try:
            return self.app.query_one(self.OTHER)
        except Exception:
            return None

    def _show(self, text, state=None):
        hint = self.query_one(".size_hint", Static)
        hint.set_class(state == "error", "-error")
        hint.set_class(state == "warning", "-warning")
        hint.update(text)

    def show_range(self):
        warning = self.range_warning(self.applied)
        if warning:
            self._show(warning, "warning")
        else:
            self._show(HINT)

    def apply(self):
        size = self.requested_size()
        error = self.error_for(size)
        if error:
            self._show(f"{error} Not applied.", "error")
            return
        self.applied = size
        args = settings.get_args()
        setattr(args, self.SETTING, size)
        settings.update_args(args)
        self.show_range()
        # the warning on the other box may have changed too
        other = self._other()
        if other is not None and other.applied == other.requested_size():
            other.show_range()

    def set_unit(self, unit):
        self.unit = unit
        for _, value in UNITS:
            button = self.query_one(f"#{self._button_id(value)}", Button)
            button.variant = "primary" if value == unit else "default"

    # --- events -----------------------------------------------------------

    def on_input_changed(self, event):
        event.stop()
        self.apply()

    def on_button_pressed(self, event):
        # the unit buttons are handled here, not by the app's button handler
        event.stop()
        self.set_unit(int(event.button.id.rsplit("_", 1)[1]))
        self.apply()

    # --- what the table calls -----------------------------------------------

    def update_table_val(self, val):
        try:
            size = int(val)
        except (TypeError, ValueError):
            return
        number, unit = split_size(size)
        self.set_unit(unit)
        self.input.value = str(number) if number else ""
        return val

    def reset(self):
        self.set_unit(self.default_unit)
        self.input.value = str(self.default_number) if self.default_number else ""


class SizeMaxField(SizeField):
    LABEL = "Max size"
    SETTING = "size_max"

    def range_warning(self, size):
        other = self._other()
        low = other.applied if other is not None else 0
        if size and low and size < low:
            return f"Max is below the min ({format_size(low)}); nothing will download."
        return None


class SizeMinField(SizeField):
    LABEL = "Min size"
    SETTING = "size_min"

    def range_warning(self, size):
        other = self._other()
        high = other.applied if other is not None else 0
        if size and high and size > high:
            return f"Min is above the max ({format_size(high)}); nothing will download."
        return None


SizeMaxField.OTHER = SizeMinField
SizeMinField.OTHER = SizeMaxField
