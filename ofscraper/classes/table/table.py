import logging
import queue
import re

import arrow
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, Label, Rule

import ofscraper.utils.logs.logger as logger
from ofscraper.classes.table.components.button import StyledButton
from ofscraper.classes.table.components.datatable import DataTable

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
from ofscraper.classes.table.components.table_console import OutConsole
from textual.widgets import SelectionList

log = logging.getLogger("shared")
global app
app = None
row_queue = queue.Queue()


class TableRow:
    def __init__(self, table_row):
        self._table_row = table_row
        self._other_styled = None
        self.text={"length","text","username"}

    def get_styled(self, count):
        styled_row = [Text(str(count + 1))]
        styled_row.extend([ Text(str(self._table_row[key.lower()]) ,style="italic #03AC13") if key in self.text else self._table_row[key.lower()]
for key in row_names() ])
        # for key in row_names():
        #     if key in self.text:
        #         row=Text(str(self.get_val(key)), style="italic #03AC13", overflow="fold")
        #         if key=="text":
        #             row=self.split_join_max_len(row, 30)
        #     else:
        #         row=(self.get_val(key))
        #     styled_row.append(row)
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
        self.reverse=None
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
        self._init_args = kwargs.pop("args", None)
        self.run()


    def reset_table(self, reset=False):
        self.query_one(DataTable).reset(refresh=True)
    def update_table(self, reset=False):
        self.run_worker(self.set_filtered_rows(reset=reset))

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
            self.reset_table()

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
        self._set_media_type()
        self._set_id()
        self._set_sort()
        self._set_length()
        self.query_one(Sidebar).toggle_class("-hidden")
        self.set_cart_toggle(init=True)
        self.make_table()
        # self.set_filtered_rows(reset=False)
        logger.add_widget(self.query_one("#console_page").query_one(OutConsole))
    def _set_length(self):
        if self._init_args.length_max:
            self.query_one("#length").update_table_max(self._init_args.length_max)
        if self._init_args.length_min:
            self.query_one("#length").update_table_min(self._init_args.length_min)
    def _set_sort(self):
        self.sort_helper(reverse=self._init_args.media_desc,label=self._init_args.media_sort)
    def _set_id(self):
        self.query_one("#post_id").update_table_val(self._init_args.post_id or "")
        self.query_one("#media_id").update_table_val(self._init_args.media_id or "")

    def _set_media_type(self):
        mediatype = (
            self._init_args.media_type
            if bool(self._init_args.media_type)
            else ["Audios", "Videos", "Images"]
        )
        self.query_one("#mediatype").query_one(SelectionList).deselect_all()
        for ele in mediatype:
            self.query_one("#mediatype").query_one(SelectionList).select(ele.lower())


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
    def sort_helper(self, label=None,reverse=None):
        self.run_worker(self._sort_helper(label,reverse), thread=True, exclusive=True)

    async def _sort_helper(self, label=None,reverse=None):
        with self.mutex:
            if label is None:
                self._sorted_reversed(self.table_data) if reverse else  self.table_data
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

            self.set_reverse(key=key,reverse=reverse)
            if key == "number":
                self.query_one(DataTable).sort("number",key=lambda x:int(x.plain),reverse=self.reverse)
            elif key == "username":
                self.query_one(DataTable).sort("username",key=lambda x:x.plain,reverse=self.reverse)
            elif key == "downloaded":
                self.query_one(DataTable).sort("downloaded",key=lambda x:x,reverse=self.reverse)

            elif key == "unlocked":
                self.query_one(DataTable).sort("unlocked",key=lambda x:x,reverse=self.reverse)
            elif key == "other_posts_with_media":
                self.query_one(DataTable).sort("other_posts_with_media",key=lambda x:len(x),reverse=self.reverse)
            elif key == "length":
                self.query_one(DataTable).sort("length",key=lambda x: arrow.get(x.plain, "h:m:s") if x.plain not in {"N/A","N\A"} else arrow.get("0:0:0", "h:m:s") ,reverse=self.reverse)
            elif key == "mediatype":
                self.query_one(DataTable).sort("mediatype",key=lambda x:x,reverse=self.reverse)
            elif key == "post_date":
                self.query_one(DataTable).sort("post_date",key=lambda x:arrow.get(x),reverse=self.reverse)
            elif key == "post_media_count":
                self.query_one(DataTable).sort("post_media_count",key=lambda x:x,reverse=self.reverse)

            elif key == "responsetype":
                 self.query_one(DataTable).sort("responsetype",key=lambda x:x,reverse=self.reverse)

            elif key == "price":
                self.query_one(DataTable).sort("price",key=lambda x:0 if x=="free" else x,reverse=self.reverse)

            elif key == "post_id":
                self.query_one(DataTable).sort("post_id",key=lambda x:x,reverse=self.reverse)
            elif key == "media_id":
                self.query_one(DataTable).sort("media_id",key=lambda x:x,reverse=self.reverse)
            elif key == "text":
               self.query_one(DataTable).sort("text",key=lambda x:x.plain,reverse=self.reverse)

    def set_reverse(self, key=None, init=False,reverse=None):
        if reverse:
            self.reverse = False
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
                self.reset_table()
        else:
            with self.mutex:
                self.reset_table()
                for name in row_names():
                    try:
                        self._filtered_rows_helper(name)
                    except Exception as _:
                        pass
        try:
            self.query_one(DataTable).refresh()
        except Exception as E:
            log.debug(f"Failed to refresh table: {E}")
    def _filtered_rows_helper(self,key):
            key = key.lower()
            if key=="dd":
                pass
            # if key == "number":
            #     self.query_one(DataTable).filter("number",key=lambda x:int(x.plain))
            # elif key == "username":
            #     self.query_one(DataTable).filter("username",key=lambda x:x.plain)
            # elif key == "downloaded":
            #     self.query_one(DataTable).filter("downloaded",key=lambda x:x)

            # elif key == "unlocked":
            #     self.query_one(DataTable).sort("unlocked",key=lambda x:x)
            # elif key == "other_posts_with_media":
            #     self.query_one(DataTable).filter("other_posts_with_media",key=lambda x:len(x))
            # elif key == "length":
            #     self.query_one(DataTable).filter("length",key=lambda x: arrow.get(x.plain, "h:m:s") if x.plain not in {"N/A","N\A"} else arrow.get("0:0:0", "h:m:s") )
            # elif key == "mediatype":
            #     self.query_one(DataTable).filter("mediatype",key=lambda x:x)
            # elif key == "post_date":
            #     self.query_one(DataTable).filter("post_date",key=lambda x:arrow.get(x))
            elif key == "post_media_count":
                self.query_one(DataTable).filter("post_media_count",key=self.query_one("#post_media_count").key())

            # elif key == "responsetype":
            #      self.query_one(DataTable).filter("responsetype",key=lambda x:x)

            # elif key == "price":
            #     self.query_one(DataTable).filter("price",key=lambda x:0 if x=="free" else x)

            # elif key == "post_id":
            #     self.query_one(DataTable).filter("post_id",key=lambda x:x)
            # elif key == "media_id":
            #     self.query_one(DataTable).filter("media_id",key=lambda x:x)
            # elif key == "text":
            #    self.query_one(DataTable).filter("text",key=lambda x:x.plain)

                      
    
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
            table.add_column("number",key="number")
            [
                table.add_column(re.sub("_", " ", ele), key=str(ele))
                for ele in row_names()
            ]
            rows=[]
            for count, row in enumerate(self.table_data):
                print(count)
                table_row = row.get_styled(count)
                rows.append(table_row)
            table.add_rows(rows)
            if len(table.rows) == 0:
                table.add_row("All Items Filtered")
            table.save_table()


app = InputApp()
