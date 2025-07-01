from ofscraper.classes.table.fields.numfield import PostiveNumField
import ofscraper.utils.settings as settings


class SizeMaxField(PostiveNumField):
    def compose(self):
        yield self.Field(
            placeholder=self.filter_name.capitalize().replace("_", " "),
            id=f"{self.filter_name}_input",
            value=self.default,
        )

    def on_input_changed(self, event):
        value = event.value if event.value else "0"
        args = settings.get_args()
        args.size_max = int(value)
        settings.update_args(args)


class SizeMinField(PostiveNumField):
    def compose(self):
        yield self.Field(
            placeholder=self.filter_name.capitalize().replace("_", " "),
            id=f"{self.filter_name}_input",
            value=self.default,
        )

    def on_input_changed(self, event):
        value = event.value if event.value else "0"
        args = settings.get_args()
        args.size_min = int(value)
        settings.update_args(args)
