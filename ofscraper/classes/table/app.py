import logging
import queue
import re
import arrow
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.widgets import Button, ContentSwitcher
from ofscraper.classes.table.utils.row_names import row_names
from ofscraper.classes.table.utils.status import status
from ofscraper.classes.table.utils.lock import mutex
from ofscraper.classes.table.sections.table_console import OutConsole
from ofscraper.classes.table.sections.table import get_styled,get_compare_val
from textual.widgets import SelectionList
from ofscraper.classes.table.css import CSS
from ofscraper.classes.table.const import AMOUNT_PER_PAGE
from ofscraper.classes.table.compose import composer
import ofscraper.utils.logs.logger as logger


log = logging.getLogger("shared")
app = None
row_queue = queue.Queue() 





class InputApp(App):
    BINDINGS = [("ctrl+t", "toggle_page_sidebar"), ("ctrl+s", "toggle_options_sidebar")]
    CSS=CSS
    def __init__(self, *args, **kwargs) -> None:
        self._status = status
        self.sidebar = None
        super().__init__(*args, **kwargs)
    # Main

    def __call__(self, *args, **kwargs):
        self._init_args = kwargs.pop("args", None)
        self.table_data = kwargs.pop("table_data", None)
        self._sorted_hash = {}
        self._sortkey = None
        self._reverse = False       
        self._download_cart_toggle=False 
        self.run()
    def compose(self) -> ComposeResult:
        return composer(self._init_args)
           
    def on_mount(self) -> None:
        self.init_table()
        self.query_one("#options_sidebar").toggle_class("-hidden")
        self.query_one("#page_option_sidebar").toggle_class("-hidden")
        logger.add_widget(self.query_one("#console_page").query_one(OutConsole))



    #events
    def on_data_table_header_selected(self, event):
        key= re.sub(" ", "_", event.label.plain)
        if key == "download_cart":
            self.table.toggle_cart()
            self.update_cart_info()
        else:
            self.update_table_sort(key)
            self.update_search_info()


    def on_data_table_cell_selected(self, event):
        self.change_download_cart(self.table.cursor_coordinate)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "reset":
            self.reset_table()

        elif event.button.id == "send_downloads":
            log.info("Adding Downloads to queue")
            self.add_to_row_queue()
            self.query_one(ContentSwitcher).current = "console_page"

        elif event.button.id == "filter" or event.button.id == "filter2":

            self.query_one("#options_sidebar").toggle_class("-hidden")
            self.filter_table()


        elif event.button.id == "page_enter" or event.button.id == "page_enter2":
            self.query_one("#page_option_sidebar").toggle_class("-hidden")
            self.filter_table()
        elif event.button.id in ["console", "table"]:
            self.query_one(ContentSwitcher).current = f"{event.button.id}_page"

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.exit()
        if event.character in set([";", "'"]):
            table =self.table
            cursor_coordinate = table.cursor_coordinate
            _,col=cursor_coordinate
            if len(table.ordered_rows) == 0:
                return
            col_name =table.ordered_columns_keys[col]
            if col_name != "download_cart":
                self.update_input(col_name,table.get_cell_at(cursor_coordinate) )
            else:
                self.change_download_cart(table.cursor_coordinate)

    def action_toggle_options_sidebar(self) -> None:
        if "page_option_sidebar" not in list(
            map(lambda x: x.id, self.query("Sidebar.-hidden"))
        ):
            self.query_one("#page_option_sidebar").toggle_class("-hidden")
        self.query_one("#options_sidebar").toggle_class("-hidden")

    def action_toggle_page_sidebar(self) -> None:
        if "options_sidebar" not in list(
            map(lambda x: x.id, self.query("Sidebar.-hidden"))
        ):
            self.query_one("#options_sidebar").toggle_class("-hidden")
        self.query_one("#page_option_sidebar").toggle_class("-hidden")
    def _set_length(self):
        if self._init_args.length_max:
            self.query_one("#length").update_table_max(self._init_args.length_max)
        if self._init_args.length_min:
            self.query_one("#length").update_table_min(self._init_args.length_min)

   

    # Cart
    def change_download_cart(self, coord):
        self.table.change_cart_cell(coord)
        self.update_cart_info()

    def add_to_row_queue(self):
        table = self.table
        matching_rows=table.get_matching_rows("download_cart","[added]")
        cart=[]
        for key,value in matching_rows.items():
            table.update_cell_at_key(key,"download_cart",Text("[downloading]",style="bold yellow"))
            cart.append((key,value))
        self.update_cart_info()
        for ele in cart:
            row_queue.put(ele)
        log.info(f"Number of Downloads sent to queue {len([ele for ele in matching_rows.values()])}")



    # sort/filer
    def set_sort(self, label):
        self._sort_runner(label)

    def _sort_runner(self, key):
        with mutex:
            self.set_reverse(key=key)
            #sort
            if key == "number":
                self.query_one("#data_table_hidden").sort(
                    "number", key=lambda x: x, reverse=self._reverse
                )
            elif key == "username":
                self.query_one("#data_table_hidden").sort(
                    "username", key=lambda x: x.plain, reverse=self._reverse
                )
            elif key == "downloaded":
                self.query_one("#data_table_hidden").sort(
                    "downloaded", key=lambda x: x, reverse=self._reverse
                )

            elif key == "unlocked":
                self.query_one("#data_table_hidden").sort(
                    "unlocked", key=lambda x: x, reverse=self._reverse
                )
            elif key == "other_posts_with_media":
                self.query_one("#data_table_hidden").sort(
                    "other_posts_with_media", key=lambda x: len(x), reverse=self._reverse
                )
            elif key == "length":
                self.query_one("#data_table_hidden").sort(
                    "length",
                    key=lambda x: (
                        arrow.get(x.plain, "h:m:s")
                        if x.plain not in {"N/A", "N\A"}
                        else arrow.get("0:0:0", "h:m:s")
                    ),
                    reverse=self._reverse,
                )
            elif key == "mediatype":
                self.query_one("#data_table_hidden").sort(
                    "mediatype", key=lambda x: x, reverse=self._reverse
                )
            elif key == "post_date":
                self.query_one("#data_table_hidden").sort(
                    "post_date", key=lambda x: arrow.get(x), reverse=self._reverse
                )
            elif key == "post_media_count":
                self.query_one("#data_table_hidden").sort(
                    "post_media_count", key=lambda x: x, reverse=self._reverse
                )

            elif key == "responsetype":
                self.query_one("#data_table_hidden").sort(
                    "responsetype", key=lambda x: x, reverse=self._reverse
                )

            elif key == "price":
                self.query_one("#data_table_hidden").sort(
                    "price", key=lambda x: 0 if x == "free" else x, reverse=self._reverse
                )

            elif key == "post_id":
                self.query_one("#data_table_hidden").sort(
                    "post_id", key=lambda x: x, reverse=self._reverse
                )
            elif key == "media_id":
                self.query_one("#data_table_hidden").sort(
                    "media_id", key=lambda x: x, reverse=self._reverse
                )
            elif key == "text":
                self.query_one("#data_table_hidden").sort(
                    "text", key=lambda x: x.plain, reverse=self._reverse
                )


    def set_reverse(self, key=None):
        if not self._sortkey:
            self._reverse = False
            self._sortkey = key
        elif key != self._sortkey:
            self._sortkey = key
            self._reverse = False

        elif self._sortkey == key and not self._reverse:
            self._reverse = True

        elif self._sortkey == key and self._reverse:
            self._reverse = False

    def set_filtered_rows(self, reset=False):
        with mutex:
            filter_rows=None
            if reset is True:
                key_order=sorted([str(x.value) for x in self.query_one("#data_table_hidden")._row_locations],key=lambda x:int(x))
                filter_rows = [self.query_one("#data_table_hidden")._data[ele] for ele in key_order]
            else:
                key_order=[str(x.value) for x in self.query_one("#data_table_hidden")._row_locations]
                filter_rows = [self.query_one("#data_table_hidden")._data[ele] for ele in key_order]
                for name in row_names():
                    try:
                        filter_rows = list(
                            filter(
                                lambda x: self._status.validate(
                                    name,
                                    get_compare_val(
                                        name,x[name]
                                    ),
                                ),
                                filter_rows,
                            )
                        )
                    except Exception:
                        pass

            self._filtered_rows = filter_rows
    #inputs
    def update_input(self, row_name, value):
        try:
            value=value.plain if isinstance(value, Text) else value
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

    def _set_media_type(self):
        mediatype = (
            self._init_args.media_type
            if bool(self._init_args.media_type)
            else ["Audios", "Videos", "Images"]
        )
        self.query_one("#mediatype").query_one(SelectionList).deselect_all()
        for ele in mediatype:
            self.query_one("#mediatype").query_one(SelectionList).select(ele.lower())

    #table     
    def update_table_sort(self,key):
            self.set_sort(key)
            self.set_filtered_rows()
            self.set_page()


    def filter_table(self):
        self.set_filtered_rows()
        self.set_page()
        self.update_search_info()  
    def set_page(self, reset=False):
        with mutex:
            self.table.clear()
            rows = list(self._filtered_rows)
            num_page = self._status["num_per_page"] or AMOUNT_PER_PAGE
            if not reset:
                page = min(self._status["page"], len(rows) // num_page)
                page=max(page, 1)
            else:
                page = 1
            start = (page - 1) * num_page
            for count, ele in enumerate(rows[start : start + num_page]):
                values=list(ele.values())
                key=str(values[0])
                self.table.add_row(*values,height=None,key=key,label=count+1)
            pass

    def init_table(self):
        self._set_media_type()
        self._set_length()
        self.insert_data_table()
        self.set_filtered_rows()
        self.set_page()
        self.update_search_info()

    def insert_data_table(self):
        with mutex:
            self._insert_hidden_table()
            self._insert_visible_table()

    def _insert_hidden_table(self):
            #hidden table as a 'cache'
            table = self.query_one("#data_table_hidden")
            table.clear(True)
            table.fixed_rows = 0
            table.zebra_stripes = True
            [
                table.add_column(re.sub("_", " ", ele), key=str(ele))
                for ele in row_names()
            ]
            for row in self.table_data:
                table_row = get_styled(row)
                table.add_row(*table_row, key=str(row.get("index")), height=0)
            if len(table.rows) == 0:
                table.add_row("All Items Filtered")
    def _insert_visible_table(self):
            table = self.table
            table.clear(True)
            table.fixed_rows = 0
            table.zebra_stripes = True
            for ele in row_names():
                width=18
                width=50 if ele=="text" else width
                width=50 if ele=="other_posts_with_media" else width
                table.add_column(re.sub("_", " ", ele), key=str(ele),width=width)

    #stats
    def update_search_info(self):
        page=self.query_one("#page").IntegerInput.value
        num_page=self.query_one("#num_per_page").IntegerInput.value
        sort=self._sortkey or "number"
        reverse=str(self._reverse)
        self.query(".search_info")[0].update(f"[bold blue]Page Info[/bold blue]: \[Page: {page}] \[Num_per_page: {num_page}]")
        self.query(".search_info")[1].update(f"[bold blue]Sort Info[/bold blue]: \[Sort: {sort}] \[Reversed: {reverse}]")

    def update_cart_info(self):
        download_cart=len(list(self.table.get_matching_rows("download_cart","[added]")))
        self.query(".search_info")[2].update(f"[bold blue]Items in Cart[/bold blue]: {download_cart}")


    @property
    def status(self):
        return self._status._status
    @property
    def table(self):
        return self.query_one("#data_table")
    @status.setter
    def status(self, val):
        self._status._status = val
app = InputApp()
