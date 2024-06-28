import asyncio
import logging
import queue
import re

import arrow
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, DataTable, Label, Rule

import ofscraper.utils.logs.logger as logger
from ofscraper.classes.table.button import StyledButton
from ofscraper.classes.table.fields.datefield import DateField
from ofscraper.classes.table.fields.mediafield import MediaField
from ofscraper.classes.table.fields.numfield import NumField, OtherMediaNumField
from ofscraper.classes.table.fields.pricefield import PriceField
from ofscraper.classes.table.fields.responsefield import ResponseField
from ofscraper.classes.table.fields.selectfield import SelectField
from ofscraper.classes.table.fields.textsearch import TextSearch
from ofscraper.classes.table.fields.timefield import TimeField
from ofscraper.classes.table.inputs.strinput import StrInput
from ofscraper.classes.table.row_names import row_names, row_names_all
from ofscraper.classes.table.status import status
from ofscraper.classes.table.table_console import OutConsole

log = logging.getLogger("shared")
global app
app = None
row_queue = queue.Queue()


class TableRow:
    def __init__(self, table_row):
        self._table_row = table_row
        self._other_styled = None

    def get_styled(self, count):
        styled_row = [Text(str(count + 1))]
        if not self._other_styled:
            other_styled_row = [
                Text(str(self.get_val(key)), style="italic #03AC13", overflow="fold")
                for key in row_names()
            ]
            other_styled_row = [
                self.split_join_max_len(ele, 30) for ele in other_styled_row
            ]
            self._other_styled = other_styled_row
        styled_row.extend(self._other_styled)
        return styled_row

    def split_join_max_len(self, text, max_len):
        current_line = ""
        result = ""
        for word in str(text).split():
            if len(current_line + word) <= max_len:
                current_line += " " + word
            else:
                result += current_line.strip() + "\n"
                current_line = word
        result += current_line.strip()
        result = re.sub("^\s+", "", result)
        result = re.sub("\s+$", "", result)
        return Text(result)

    def get_val(self, name):
        name = name.lower()
        name = name if name != "number" else "index"
        return self._table_row[name]

    def get_compare_val(self, name):
        if name == "length":
            return self._get_length_val(name)
        if name == "post_date":
            return self._get_post_date_val(name)
        if name == "other_posts_with_media":
            return self._get_list_length(name)
        else:
            return self.get_val(name)

    def _get_post_date_val(self, name):
        return arrow.get(self._table_row[name]).floor("day")

    def _get_length_val(self, name):
        timestr = self._table_row[name]
        if timestr == "N\A" or timestr == "N/A":
            timestr = "0:0:0"
        return arrow.get(timestr, "h:m:s")

    def _get_list_length(self, name):
        return len(self._table_row[name])

    def set_val(self, key, val):
        self._table_row[key.lower()] = val
        self._other_styled = None


class Sidebar(Container):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class InputApp(App):
    CSS = """
    Screen {
       layers: sidebar;
       overflow: hidden;
    }

    Sidebar {
        width: 45%;
        dock: left;
        layer: sidebar;
        overflow-y:scroll;
        overflow-x:scroll;

    }


    #options{
        height:120;
        layout: grid;
        grid-size: 4 50;
        margin-top:2;
    }

#buttons{
height:15vh;
}
 
    Sidebar.-hidden {
        display: none;
    }

    #data_table {
    margin-bottom:2;
    height:95%

    }


    #data_table_holder {
         overflow-x:scroll;
        overflow-y:scroll;
        width:80%;
        height:80%;
    }

    Widget {
    column-span:4;
    row-span:2;
    }
    NumField {
    column-span:3;
    }

SelectField,DateField,TimeField {
    row-span:3;
    }

    SelectField{
    column-span:2;
    }

    MediaField {
    column-span:3;
    row-span:3;
    }
   

    ResponseField {
    column-span:4;
    row-span:4;
    }
   
    #other_posts_with_media{
    column-span:1;
    }
    #Post_Media_Count{
    column-span:1;
    }
    #table_main{
    height:6fr;
    }
    """

    BINDINGS = [("ctrl+s", "toggle_sidebar")]

    def action_toggle_sidebar(self) -> None:
        self.query_one(Sidebar).toggle_class("-hidden")

    def __init__(self, *args, **kwargs) -> None:
        self._status = status
        super().__init__(*args, **kwargs)

    @property
    def status(self):
        return self._status._status

    @status.setter
    def status(self, val):
        self._status._status = val

    def __call__(self, *args, **kwargs):
        self.table_data_original = kwargs.pop("table_data", None)
        self.table_data = [TableRow(ele) for ele in self.table_data_original[1:]]
        self._sorted_hash = {}
        self._sortkey = None
        self.mutex = kwargs.pop("mutex", None)
        self._sorted_rows = self.table_data
        self._filtered_rows = self.table_data
        self._init_mediatype = kwargs.pop("mediatype", None)
        self.run()

    def update_table(self, reset=False):
        self.run_worker(self._update_table(reset=reset))

    async def _update_table(self, reset=False):
        self.set_filtered_rows(reset=reset)
        self.make_table()

    def on_data_table_header_selected(self, event):
        self.sort_helper(event.label.plain)

    def on_data_table_cell_selected(self, event):
        table = self.query_one(DataTable)
        cursor_coordinate = table.cursor_coordinate
        if list(row_names_all())[cursor_coordinate.column] == "download_cart":
            self.change_download_cart(event.coordinate)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "reset":
            self.reset_all_inputs()
            self.set_reverse(init=True)
            self.update_table(reset=True)

        elif event.button.id == "send_downloads":
            log.info("Adding Downloads to queue")
            self.add_to_row_queue()
            self.query_one(ContentSwitcher).current = "console_page"

        elif event.button.id == "filter":
            self.update_table()
        elif event.button.id in ["console", "table"]:
            self.query_one(ContentSwitcher).current = f"{event.button.id}_page"

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.exit()
        if event.character in set([";", "'"]):
            table = self.query_one(DataTable)
            cursor_coordinate = table.cursor_coordinate
            if len(table._data) == 0:
                return
            cell_key = table.coordinate_to_cell_key(cursor_coordinate)
            event = DataTable.CellSelected(
                self,
                table.get_cell_at(cursor_coordinate),
                coordinate=cursor_coordinate,
                cell_key=cell_key,
            )
            row_name = list(row_names_all())[event.coordinate[1]]
            if row_name != "download_cart":
                self.update_input(row_name, event.value.plain)
            else:
                self.change_download_cart(event.coordinate)

    # Main
    def compose(self) -> ComposeResult:
        with Horizontal(id="buttons"):
            yield Button("DataTable", id="table")
            yield Button("Console", id="console")

        with ContentSwitcher(initial="table_page"):
            with Vertical(id="table_page"):
                with Horizontal(id="data"):
                    yield StyledButton("Reset", id="reset")
                    yield StyledButton("Filter", id="filter")
                    yield StyledButton(
                        ">> Send Downloads to OF-Scraper", id="send_downloads"
                    )
                yield Label("Ctrl+S: Toggle Sidebar for search")
                yield Label("Arrows: Navigate Table")
                yield Label('";" or "\'": Filter Table via Cell')
                yield Label("Add to Cart: Click cell in 'Download Cart' Column")
                with Container(id="table_main"):
                    with Sidebar():
                        with Container(id="options"):
                            for ele in ["Text"]:
                                yield TextSearch(ele)
                            yield Rule()
                            for ele in ["other_posts_with_media"]:
                                yield OtherMediaNumField(ele)

                            for ele in ["Media_ID"]:
                                yield NumField(ele)
                            yield Rule()
                            for ele in ["Post_ID", "Post_Media_Count"]:
                                yield NumField(ele)
                            yield Rule()
                            for ele in ["Price"]:
                                yield PriceField(ele)
                            yield Rule()
                            for ele in ["Post_Date"]:
                                yield DateField(ele)
                            yield Rule()
                            for ele in ["Length"]:
                                yield TimeField(ele)
                            yield Rule()
                            yield SelectField("Downloaded")
                            yield SelectField("Unlocked")
                            yield Rule()
                            for ele in ["Mediatype"]:
                                yield MediaField(ele)
                            for ele in ["Responsetype"]:
                                yield ResponseField(ele)
                            yield Rule()

                            for ele in ["username"]:
                                yield StrInput(id=ele)
                    yield DataTable(id="data_table")
                    yield Container()
            with Vertical(id="console_page"):
                yield OutConsole()

    def on_mount(self) -> None:
        self.query_one(Sidebar).toggle_class("-hidden")
        self.set_reverse(init=True)
        self.set_cart_toggle(init=True)
        self.update_table(reset=True)
        logger.add_widget(self.query_one("#console_page").query_one(OutConsole))

    def _set_and_sort_media_type(self):
        mediatype = (
            self._init_mediatype
            if bool(self._init_mediatype)
            else ["Audios", "Videos", "Images"]
        )

        self.query_one("#Mediatype_audios").value = (
            mediatype is None or "Audios" in mediatype
        )
        self.query_one("#Mediatype_videos").value = (
            mediatype is None or "Videos" in mediatype
        )
        self.query_one("#Mediatype_images").value = (
            mediatype is None or "Images" in mediatype
        )

    # Cart
    def change_download_cart(self, coord):
        table = self.query_one(DataTable)
        download_cart = table.get_cell_at(coord)

        if download_cart.plain == "Not Unlocked":
            return
        elif download_cart.plain == "[]":
            self.update_cell_at_coords(coord, "[added]")

        elif download_cart.plain == "[added]":
            self.update_cell_at_coords(coord, "[]")

        elif download_cart.plain == "[downloaded]" or "[failed]":
            self.update_cell_at_coords(coord, "[]")

    def add_to_row_queue(self):
        table = self.query_one(DataTable)
        row_keys = [str(ele.get_val("index")) for ele in self._filtered_rows]
        cart_index = list(row_names_all()).index("download_cart")
        filter_row_keys = list(
            filter(lambda x: table.get_row(x)[cart_index].plain == "[added]", row_keys)
        )
        self.update_downloadcart_cells(filter_row_keys, "[downloading]")
        log.info(f"Number of Downloads sent to queue {len(filter_row_keys)}")
        [
            row_queue.put(ele)
            for ele in map(lambda x: (table.get_row(x), x), filter_row_keys)
        ]

    def update_downloadcart_cells(self, keys, value):
        self.update_cell(keys, "download_cart", value)

    def update_cell_at_coords(self, coords, value, persist=True):
        with self.mutex:
            for coord in coords if isinstance(coords, list) else [coords]:
                try:
                    table = self.query_one(DataTable)
                    table.update_cell_at(coord, Text(value))
                    key = list(row_names_all())[coord.column]
                    if persist:
                        self.table_data[coord.row].set_val(key, value)
                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)

    def update_cell(self, keys, name, value, persist=True):
        if not isinstance(keys, list):
            keys = [keys]
        with self.mutex:
            for key in keys:
                try:
                    if persist:
                        self.table_data[int(key)].set_val(name, value)
                    table = self.query_one(DataTable)
                    table.update_cell(key, name, Text(str(value)))
                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)

    # Table Functions
    def sort_helper(self, label):
        self.run_worker(self._sort_helper(label), thread=True, exclusive=True)

    async def _sort_helper(self, label=None):
        with self.mutex:
            if label is None:
                return
            key = re.sub(" ", "_", label).lower()
            if key == "download_cart":
                index = list(row_names_all()).index(key)
                filtered_status = {"[downloading]", "Not Unlocked", "[downloaded]"}
                table = self.query_one(DataTable)
                self.set_cart_toggle()
                filter_keys = list(
                    filter(
                        lambda x: table.get_row(x)[index].plain not in filtered_status,
                        map(lambda x: x.value, table.rows.keys()),
                    )
                )
                log.debug(f"set cart toggle to {self.cart_toggle.plain}")
                [
                    table.update_cell(key, "download_cart", self.cart_toggle)
                    for key in filter_keys
                ]
                return

            self.set_reverse(key=key)
            if self._get_sorted_hash(key):
                self._sorted_rows = self._get_sorted_hash(key)
            elif key == "number":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: x.get_compare_val(key),
                    reverse=self.reverse,
                )
            elif key == "username":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: (x.get_compare_val(key), x.get_compare_val("number")),
                    reverse=self.reverse,
                )
            elif key == "downloaded":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: 1 if x.get_compare_val(key) is True else 0,
                    reverse=self.reverse,
                )

            elif key == "unlocked":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: 1 if x.get_compare_val(key) is True else 0,
                    reverse=self.reverse,
                )
            elif key == "other_posts_with_media":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: x.get_compare_val(key) or 0,
                    reverse=self.reverse,
                )
            elif key == "length":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: (
                        x.get_compare_val(key) if x.get_compare_val(key) != "N/A" else 0
                    ),
                    reverse=self.reverse,
                )
            elif key == "mediatype":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: x.get_compare_val(key),
                    reverse=self.reverse,
                )
            elif key == "post_date":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: x.get_compare_val(key),
                    reverse=self.reverse,
                )
            elif key == "post_media_count":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: x.get_compare_val(key),
                    reverse=self.reverse,
                )

            elif key == "responsetype":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: x.get_compare_val(key),
                    reverse=self.reverse,
                )
            elif key == "price":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: (
                        int(float(x.get_compare_val(key)))
                        if x.get_compare_val(key) != "Free"
                        else 0
                    ),
                    reverse=self.reverse,
                )

            elif key == "post_id":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: (
                        x.get_compare_val(key) if x.get_compare_val(key) else 0
                    ),
                    reverse=self.reverse,
                )
            elif key == "media_id":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: (
                        x.get_compare_val(key) if x.get_compare_val(key) else 0
                    ),
                    reverse=self.reverse,
                )
            elif key == "text":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: x.get_compare_val(key),
                    reverse=self.reverse,
                )
            self._set_sorted_hash(key, self._sorted_rows)
        await asyncio.get_event_loop().run_in_executor(None, self.update_table)

    def _get_sorted_hash(self, key):
        return self._sorted_hash.get(f"{key}_{self.reverse}")

    def _set_sorted_hash(self, key, val):
        self._sorted_hash[f"{key}_{self.reverse}"] = val

    def set_reverse(self, key=None, init=False):
        if init:
            self.reverse = None
            self._sortkey = "number"
        elif key != self._sortkey:
            self._sortkey = key
            self.reverse = False

        elif self._sortkey == key and not self.reverse:
            self.reverse = True

        elif self._sortkey == key and self.reverse:
            self.reverse = False

    def set_cart_toggle(self, init=False):
        if init:
            self.cart_toggle = Text("[]")
        elif self.cart_toggle.plain == "[added]":
            self._current_added = []
            self.cart_toggle = Text("[]")
        elif self.cart_toggle.plain == "[]":
            self.cart_toggle = Text("[added]")

    def set_filtered_rows(self, reset=False):
        if reset is True:
            with self.mutex:
                self._filtered_rows = self.table_data
        else:
            with self.mutex:
                filter_rows = self._sorted_rows
                for name in row_names():
                    name = name.lower()
                    try:
                        filter_rows = list(
                            filter(
                                lambda x: self._status.validate(
                                    name, x.get_compare_val(name)
                                ),
                                filter_rows,
                            )
                        )
                    except Exception:
                        pass
                self._filtered_rows = filter_rows

    def update_input(self, row_name, value):
        try:
            targetNode = self.query_one(f"#{row_name}")
            targetNode.update_table_val(value)
        except:
            None

    def reset_all_inputs(self):
        for ele in list(row_names())[1:]:
            try:
                self.query_one(f"#{ele}").reset()
            except:
                continue

    def make_table(self):
        with self.mutex:
            table = self.query_one(DataTable)
            table.clear(True)
            table.fixed_rows = 0
            table.zebra_stripes = True
            table.add_column("number")
            [
                table.add_column(re.sub("_", " ", ele), key=str(ele))
                for ele in row_names()
            ]
            for count, row in enumerate(self._filtered_rows):
                table_row = row.get_styled(count)
                table.add_row(*table_row, key=str(row.get_val("index")), height=None)
            if len(table.rows) == 0:
                table.add_row("All Items Filtered")


app = InputApp()
