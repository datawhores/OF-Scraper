from textual.widgets import SelectionList

from ofscraper.classes.table.fields.selectfield import SelectField


class ResponseField(SelectField):
    def __init__(self, name: str) -> None:
        name = name.lower()
        super().__init__(name=name, classes="container")
        self.filter_name = name

    def compose(self):
        yield SelectionList(
            *[
                ("Pinned", "pinned", True),
                ("Archived", "archived", True),
                ("Timeline", "timeline", True),
                ("Stories", "stories", True),
                ("Highlights", "highlights", True),
                ("Streams", "streams", True),
            ]
        )
