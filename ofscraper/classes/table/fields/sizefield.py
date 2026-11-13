from textual.widgets import Label

from ofscraper.classes.table.fields.numfield import PostiveNumField
import ofscraper.utils.settings as settings


class SizeField(PostiveNumField):
    """A download size limit in bytes, 0 for no limit.

    The label stays when the box has a value, unlike the placeholder.
    """

    DEFAULT_CSS = """
    SizeField Label {
        width: 18;
        padding: 1 1 0 1;
    }

    SizeField Input {
        width: 1fr;
    }
    """

    LABEL = ""
    SETTING = ""

    def compose(self):
        yield Label(self.LABEL)
        yield self.Field(
            placeholder=self.filter_name.capitalize().replace("_", " "),
            id=f"{self.filter_name}_input",
            value=self.default,
        )

    def on_input_changed(self, event):
        value = event.value if event.value else "0"
        args = settings.get_args()
        setattr(args, self.SETTING, int(value))
        settings.update_args(args)


class SizeMaxField(SizeField):
    LABEL = "Max size (bytes)"
    SETTING = "size_max"


class SizeMinField(SizeField):
    LABEL = "Min size (bytes)"
    SETTING = "size_min"
