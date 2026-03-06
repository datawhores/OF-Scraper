from textual.widgets import SelectionList

from ofscraper.classes.table.fields.selectfield import SelectField

from textual.widgets.selection_list import Selection


class ResponseField(SelectField):
    DEFAULT_CSS = """

    ResponseField {
    column-span:4;
    row-span:4;
    }
   

"""

    def __init__(self, name: str) -> None:
        name = name.lower()
        super().__init__(name=name, classes="container")
        self.filter_name = name
        self._pinned = Selection(
            "Pinned",
            value="Pinned",
            disabled=False,
            id=f"{self.filter_name}_pinned",
            initial_state=True,
        )
        self._archived = Selection(
            "Archived",
            value="Archived",
            disabled=False,
            id=f"{self.filter_name}_archived",
            initial_state=True,
        )
        self._timeline = Selection(
            "Timeline",
            value="Timeline",
            disabled=False,
            id=f"{self.filter_name}_timeline",
            initial_state=True,
        )
        self._stories = Selection(
            "Stories",
            value="Stories",
            disabled=False,
            id=f"{self.filter_name}_stories",
            initial_state=True,
        )
        self._highlights = Selection(
            "Highlights",
            value="Highlights",
            disabled=False,
            id=f"{self.filter_name}_highlights",
            initial_state=True,
        )
        self._streams = Selection(
            "Streams",
            value="Streams",
            disabled=False,
            id=f"{self.filter_name}_stream",
            initial_state=True,
        )
        self._messages = Selection(
            "Messages",
            value="Messages",
            disabled=False,
            id=f"{self.filter_name}_message",
            initial_state=True,
        )

    def compose(self):
        yield SelectionList(
            self._timeline,
            self._archived,
            self._pinned,
            self._streams,
            self._stories,
            self._highlights,
            self._messages,
        )

    def update_table_val(self, val):
        self.query_one(SelectionList).deselect_all()
        val = val.capitalize()
        if val == "Pinned":
            self.query_one(SelectionList).select(self._pinned)
        elif val == "Archived":
            self.query_one(SelectionList).select(self._archived)
        elif val == "Timeline":
            self.query_one(SelectionList).select(self._timeline)
        elif val == "Stories":
            self.query_one(SelectionList).select(self._stories)
        elif val == "Highlights":
            self.query_one(SelectionList).select(self._highlights)
        elif val == "Stream":
            self.query_one(SelectionList).select(self._streams)
        elif val == "Messages":
            self.query_one(SelectionList).select(self._messages)
