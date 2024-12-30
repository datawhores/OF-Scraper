import logging
import queue
import re
import arrow
from rich.text import Text
from textual import events
from textual.app import App
from textual.widgets import Button, ContentSwitcher
from ofscraper.classes.table.utils.names import get_col_names,get_input_names
from ofscraper.classes.table.utils.lock import mutex
from ofscraper.classes.table.sections.table_console import OutConsole
from ofscraper.classes.table.sections.table import get_styled
from textual.widgets import SelectionList
from ofscraper.classes.table.css import CSS
from ofscraper.classes.table.const import AMOUNT_PER_PAGE
from ofscraper.classes.table.compose import composer
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.args.accessors.read as read_args



log = logging.getLogger("shared")
app = None
row_queue = queue.Queue() 





class InputApp(App):
    BINDINGS = [("ctrl+t", "toggle_page_sidebar"), ("ctrl+s", "toggle_options_sidebar")]
    CSS=CSS
    def __init__(self, *args, **kwargs) -> None:
        # self._status = status
        self.sidebar = None
        super().__init__(*args, **kwargs)
    # Main

    def __call__(self, *args, **kwargs):
        self.table_data = kwargs.pop("table_data", None)
        self._sortkey = None
        self._reverse = False       
        self._download_cart_toggle=False 
        self.run()
    
    def compose(self):
        try:
            return composer()
        except Exception as e:
            pass

    def on_ready(self) -> None:
        self.init_table()
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
            if col_name=="other_posts_with_media":
                pass
            elif col_name != "download_cart":
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

<<<<<<< HEAD
   

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



    # sort
    def init_sort(self):
        self._reverse = False if read_args.retriveArgs().desc is None else read_args.retriveArgs().desc
        self._sortkey="number" if read_args.retriveArgs().mediasort is None else read_args.retriveArgs().mediasort
        self._sort_runner(key=self._sortkey)
    def reset_sort(self):
        self._reverse=False
        self._sortkey="number" 
        self._sort_runner(key=self._sortkey)

    
    def set_sort(self, label):
        with mutex:
            self.set_reverse(key=label)
            self._sort_runner(label)

    def _sort_runner(self, key):
            #sort
            if key == "number":
                self.query_one("#data_table_hidden").sort(
                    "number", key=lambda x: int(x.plain), reverse=self._reverse
=======
    def __init__(self, *args, **kwargs) -> None:
        self._status = status
        self.sidebar = None
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
        self._reverse = False
        self.mutex = kwargs.pop("mutex", None)
        self._init_args = kwargs.pop("args", None)
        self.run()

    def update_table_sort(self,label):
        self.set_sort(label)
        self.set_filtered_rows()
        self.set_page()
        self.update_search_info()


    def filter_table(self):
        self.set_filtered_rows()
        self.set_page()
        self.update_search_info()


    def reset_table(self):
        self._sortkey = None
        self._reverse = False
        self.reset_all_inputs()
        self.set_filtered_rows(reset=True)
        self.set_page(reset=True)
        self.update_search_info()




        

    def on_data_table_header_selected(self, event):
        self.update_table_sort(label=event.label.plain)

    def on_data_table_cell_selected(self, event):
        table = self.query_one("#data_table")
        self.change_download_cart(table.cursor_coordinate)

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
            table = self.query_one("#data_table")
            cursor_coordinate = table.cursor_coordinate
            if len(table._data) == 0:
                return
            cell_key = table.coordinate_to_cell_key(cursor_coordinate)
            event = table.CellSelected(
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
                with Horizontal():
                    with Vertical(classes="table_info"):
                        yield Static("[bold blue]Toggle Sidebar for search[/bold blue]: Ctrl+S",markup=True)
                        yield Static("[bold blue]Toggle Page Selection[/bold blue]: Ctrl+T",markup=True)
                    yield Rule( orientation="vertical")
                    with Vertical(classes="table_info"):
                        yield Static("[bold blue]Navigate Table[/bold blue]: Arrows",markup=True)
                        yield Static('[bold blue]Filter Table via Cell[/bold blue]: ; or \'',markup=True)
                        yield Static("[bold blue]Add to Cart[/bold blue]: Click cell in \'download cart\' Column",markup=True)
                yield Rule()
                yield Static("",classes="search_info",shrink=True,markup=True)
                yield Static("",classes="search_info",shrink=True,markup=True)
                yield Rule()
                with Horizontal(id="data"):
                    yield StyledButton("Reset", id="reset")
                    yield StyledButton(
                        ">> Send Downloads to OF-Scraper", id="send_downloads"
                    )

            
                with Container(id="table_main"):
                    with Sidebar(id="page_option_sidebar"):
                        yield StyledButton("Enter", id="page_enter")
                        for ele in ["Page"]:
                            yield NumField(ele, default=START_PAGE)
                        for ele in ["Num_Per_Page"]:
                            yield NumField(ele, default=AMOUNT_PER_PAGE)
                        yield StyledButton("Enter", id="page_enter2")

                    with Sidebar(id="options_sidebar"):
                        with Container(id="main_options"):
                            yield StyledButton("Filter", id="filter")
                            yield Rule()
                            for ele in ["Text"]:
                                yield TextSearch(ele)
                            yield Rule()
                            for ele in ["other_posts_with_media"]:
                                yield OtherMediaNumField(ele)

                            for ele in ["Media_ID"]:
                                yield NumField(ele, default=self._init_args.media_id)
                            yield Rule()
                            for ele in ["Post_ID"]:
                                yield NumField(ele, default=self._init_args.post_id)
                            for ele in ["Post_Media_Count"]:
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
                            yield Rule()
                            yield StyledButton("Filter", id="filter2")
                    yield DataTable(id="data_table")
                    yield DataTable(id="data_table_hidden")

            with Vertical(id="console_page"):
                yield OutConsole()

    def on_mount(self) -> None:
        self.init_table()
        self.query_one("#options_sidebar").toggle_class("-hidden")
        self.query_one("#page_option_sidebar").toggle_class("-hidden")

        self.set_cart_toggle(init=True)
        logger.add_widget(self.query_one("#console_page").query_one(OutConsole))

    def _set_length(self):
        if self._init_args.length_max:
            self.query_one("#length").update_table_max(self._init_args.length_max)
        if self._init_args.length_min:
            self.query_one("#length").update_table_min(self._init_args.length_min)

   

    def set_page(self, reset=False):
        with self.mutex:
            self.query_one("#data_table").clear()
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
                self.query_one("#data_table").add_row(*values,height=None,key=key,label=count+1)
            pass

    def init_table(self):
        self._set_media_type()
        self._set_length()
        self.insert_data_table()
        self.set_filtered_rows()
        self.set_page()
        self.update_search_info()


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
        row,_=coord
        download_cart = self._filtered_rows[row]['download_cart']
        if download_cart.plain == "Not Unlocked":
            return
        elif download_cart.plain == "[]":
            self.update_cell_at_coords(coord, "[added]")
            # self._cart_nums.remove()

        elif download_cart.plain == "[added]":
            self.update_cell_at_coords(coord, "[]")

        elif download_cart.plain == "[downloaded]" or "[failed]":
            self.update_cell_at_coords(coord, "[]")

    def add_to_row_queue(self):
        table = self.query_one("#data_table")
        filter_row_keys = list(
            filter(lambda x: x["download_cart"].plain == "[added]", self._filtered_rows)
        )
        self.update_downloadcart_cells(filter_row_keys, "[downloading]")
        log.info(f"Number of Downloads sent to queue {len(filter_row_keys)}")
        [
            row_queue.put(ele)
            for ele in map(lambda x: (table.get_row(x), x), filter_row_keys)
        ]

    def update_downloadcart_cells(self, keys, value):
        self.update_cell(keys, "download_cart", value)

    def update_cell_at_coords(self, coords, value):
        with self.mutex:
            for coord in coords if isinstance(coords, list) else [coords]:
                try:
                    table = self.query_one("#data_table")
                    table.update_cell_at(coord, Text(value))
                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)


    # def get_row_dict_at(self,coord):
    #     out={}
    #     for key,value in zip(get)
        

    
    def update_cell(self, keys, name, value, persist=True):
        if not isinstance(keys, list):
            keys = [keys]
        with self.mutex:
            for key in keys:
                try:
                    if persist:
                        self.table_data[int(key)].set_val(name, value)
                    table = self.query_one("#data_table")
                    table.update_cell(key, name, Text(str(value)))
                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)

    # Table Functions
    def set_sort(self, label):
        self._sort_runner(label)

    def _sort_runner(self, label):
        with self.mutex:
            key= re.sub(" ", "_", label)
            if key == "download_cart":
                index = list(row_names_all()).index(key)
                filtered_status = {"[downloading]", "Not Unlocked", "[downloaded]"}
                table = self.query_one("#data_table")
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
            #sort
            if key == "number":
                self.query_one("#data_table_hidden").sort(
                    "number", key=lambda x: x, reverse=self._reverse
>>>>>>> fasttable
                )
            elif key == "username":
                self.query_one("#data_table_hidden").sort(
                    "username", key=lambda x: x.plain, reverse=self._reverse
                )
            elif key == "downloaded":
                self.query_one("#data_table_hidden").sort(
<<<<<<< HEAD
                    "downloaded", key=lambda x: x.plain, reverse=self._reverse
=======
                    "downloaded", key=lambda x: x, reverse=self._reverse
>>>>>>> fasttable
                )

            elif key == "unlocked":
                self.query_one("#data_table_hidden").sort(
<<<<<<< HEAD
                    "unlocked", key=lambda x: x.plain, reverse=self._reverse
                )
            elif key == "other_posts_with_media":
                self.query_one("#data_table_hidden").sort(
                    "other_posts_with_media", key=lambda x: len(re.findall(r'\d+', x.plain)), reverse=self._reverse
=======
                    "unlocked", key=lambda x: x, reverse=self._reverse
                )
            elif key == "other_posts_with_media":
                self.query_one("#data_table_hidden").sort(
                    "other_posts_with_media", key=lambda x: len(x), reverse=self._reverse
>>>>>>> fasttable
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
<<<<<<< HEAD
                    "mediatype", key=lambda x: x.plain, reverse=self._reverse
                )
            elif key == "post_date":
                self.query_one("#data_table_hidden").sort(
                    "post_date", key=lambda x: arrow.get(x.plain), reverse=self._reverse
                )
            elif key == "post_media_count":
                self.query_one("#data_table_hidden").sort(
                    "post_media_count", key=lambda x: x.plain, reverse=self._reverse
=======
                    "mediatype", key=lambda x: x, reverse=self._reverse
                )
            elif key == "post_date":
                self.query_one("#data_table_hidden").sort(
                    "post_date", key=lambda x: arrow.get(x), reverse=self._reverse
                )
            elif key == "post_media_count":
                self.query_one("#data_table_hidden").sort(
                    "post_media_count", key=lambda x: x, reverse=self._reverse
>>>>>>> fasttable
                )

            elif key == "responsetype":
                self.query_one("#data_table_hidden").sort(
<<<<<<< HEAD
                    "responsetype", key=lambda x: x.plain, reverse=self._reverse
=======
                    "responsetype", key=lambda x: x, reverse=self._reverse
>>>>>>> fasttable
                )

            elif key == "price":
                self.query_one("#data_table_hidden").sort(
<<<<<<< HEAD
                    "price", key=lambda x: 0 if x.plain.lower() == "free" else float(x.plain), reverse=self._reverse
=======
                    "price", key=lambda x: 0 if x == "free" else x, reverse=self._reverse
>>>>>>> fasttable
                )

            elif key == "post_id":
                self.query_one("#data_table_hidden").sort(
<<<<<<< HEAD
                    "post_id", key=lambda x: x.plain, reverse=self._reverse
                )
            elif key == "media_id":
                self.query_one("#data_table_hidden").sort(
                    "media_id", key=lambda x: x.plain, reverse=self._reverse
=======
                    "post_id", key=lambda x: x, reverse=self._reverse
                )
            elif key == "media_id":
                self.query_one("#data_table_hidden").sort(
                    "media_id", key=lambda x: x, reverse=self._reverse
>>>>>>> fasttable
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
<<<<<<< HEAD
    # filter runner
    def init_filtered_rows(self):
        self._set_media_type()
        self._set_length()
        self._filter_runner()
    def set_filtered_rows(self):
        self._filter_runner()

    def _filter_runner(self):
        with mutex:
            filter_rows=None
            key_order=[str(x.value) for x in self.query_one("#data_table_hidden")._row_locations]
            filter_rows = [self.query_one("#data_table_hidden")._data[ele] for ele in key_order]
            for name in get_col_names():
                if name in {"number","download_cart"}:
                    continue
                try:
                    filter_rows = list(
                        filter(
                            lambda x: self.query_one(f"#{name}").compare(
                                    str(x[name])
                            ),
                            filter_rows,
                        )
                    )
                except Exception:
                    pass
            self._filtered_rows = filter_rows
    #inputs
    def update_input(self, col_name, value):
        try:
            value=value.plain if isinstance(value, Text) else value
            targetNode = self.query_one(f"#{col_name}")
=======

    def set_cart_toggle(self, init=False):
        if init:
            self.cart_toggle = Text("[]")
        elif self.cart_toggle.plain == "[added]":
            self._current_added = []
            self.cart_toggle = Text("[]")
        elif self.cart_toggle.plain == "[]":
            self.cart_toggle = Text("[added]")

    def set_filtered_rows(self, reset=False):
        with self.mutex:
            filter_rows=None
            if reset is True:
                row_order=sorted([str(x.value) for x in self.query_one("#data_table_hidden")._row_locations],key=lambda x:int(x))
                filter_rows = [self.query_one("#data_table_hidden")._data[ele] for ele in row_order]
            else:
                row_order=[str(x.value) for x in self.query_one("#data_table_hidden")._row_locations]
                filter_rows = [self.query_one("#data_table_hidden")._data[ele] for ele in row_order]
                for name in row_names():
                    name = name.lower()    
                    try:
                        filter_rows = list(
                            filter(
                                lambda x: self._status.validate(
                                    name,
                                    self.table_data[int(x.key.value)].get_compare_val(
                                        name
                                    ),
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
>>>>>>> fasttable
            targetNode.update_table_val(value)
        except:
            None

    def reset_all_inputs(self):
<<<<<<< HEAD
        for ele in get_input_names():
=======
        for ele in list(row_names())[1:]:
>>>>>>> fasttable
            try:
                self.query_one(f"#{ele}").reset()
            except:
                continue

<<<<<<< HEAD
    def _set_media_type(self):
        mediatype = (
            read_args.retriveArgs().mediatype
            if bool(read_args.retriveArgs().mediatype)
            else ["Audios", "Videos", "Images"]
        )
        self.query_one("#mediatype").query_one(SelectionList).deselect_all()
        for ele in mediatype:
            self.query_one("#mediatype").query_one(SelectionList).select(ele.lower())


    def _set_length(self):
        if read_args.retriveArgs().length_max:
            self.query_one("#length").update_table_max(read_args.retriveArgs().length_max)
        if read_args.retriveArgs().length_min:
            self.query_one("#length").update_table_min(read_args.retriveArgs().length_min)

    #table 
    def reset_table(self):
        self.reset_all_inputs()
        self.reset_sort()
        self.set_filtered_rows()
        self.set_page()
        self.update_search_info()
    def update_table_sort(self,key):
            self.set_sort(key)
            self.set_filtered_rows()
            self.set_page()


    def filter_table(self):
        self.set_filtered_rows()
        self.set_page()
        self.update_search_info()  
    def set_page(self):
        with mutex:
            self.table.clear()
            rows = list(self._filtered_rows)
            num_page = int(self.query_one("#num_per_page_input").value or AMOUNT_PER_PAGE)
            page = min(int(self.query_one("#page_input").value) or 1, max(len(rows) // num_page,1))
            start = (page - 1) * num_page
            for count, ele in enumerate(rows[start : start + num_page]):
                values=list(ele.values())
                key=str(values[0])
                self.table.add_row(*values,height=None,key=key,label=count+1)

    def init_table(self):
        self.insert_data_table()
        self.init_sort()
        self.init_filtered_rows()
        self.set_page()
        self.update_search_info()

    def insert_data_table(self):
        with mutex:
=======
    def insert_data_table(self):
        with self.mutex:
>>>>>>> fasttable
            self._insert_hidden_table()
            self._insert_visible_table()

    def _insert_hidden_table(self):
            #hidden table as a 'cache'
            table = self.query_one("#data_table_hidden")
            table.clear(True)
            table.fixed_rows = 0
            table.zebra_stripes = True
<<<<<<< HEAD
            [
                table.add_column(re.sub("_", " ", ele), key=str(ele))
                for ele in get_col_names()
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
            for ele in get_col_names():
                width=18
                width=50 if ele=="text" else width
                width=30 if ele=="other_posts_with_media" else width
                table.add_column(re.sub("_", " ", ele), key=str(ele),width=width)

    #stats
    def update_search_info(self):
        page=self.query_one("#page").integer_input.value
        num_page=self.query_one("#num_per_page").integer_input.value
        sort=self._sortkey or "number"
        reverse=str(self._reverse)
        self.query(".search_info")[0].update(f"[bold blue]Page Info[/bold blue]: \[Page: {page}] \[Num_per_page: {num_page}] [Total: {len(self._filtered_rows)}]")
        self.query(".search_info")[1].update(f"[bold blue]Sort Info[/bold blue]: \[Sort: {sort}] \[Reversed: {reverse}]")

    def update_cart_info(self):
        download_cart=len(list(self.table.get_matching_rows("download_cart","[added]")))
        self.query(".search_info")[2].update(f"[bold blue]Items in Cart[/bold blue]: {download_cart}")

    @property
    def table(self):
        return self.query_one("#data_table")
app = InputApp()
=======
            table.add_column(Text("number",style="bold yellow"), key="number")
            [
                table.add_column(re.sub("_", " ", ele), key=str(ele))
                for ele in row_names()
            ]
            for row in self.table_data:
                table_row = row.get_styled()
                table.add_row(*table_row, key=str(row.get_val("index")), height=0)
            if len(table.rows) == 0:
                table.add_row("All Items Filtered")
    def _insert_visible_table(self):
            table = self.query_one("#data_table")
            table.clear(True)
            table.fixed_rows = 0
            table.zebra_stripes = True
            table.add_column("number", key="number")
            for ele in row_names():
                width=18
                width=50 if ele=="text" else width
                width=50 if ele=="other_posts_with_media" else width
                table.add_column(re.sub("_", " ", ele), key=str(ele),width=width)

    def update_search_info(self):
        page=self.query_one("#page").IntegerInput.value
        num_page=self.query_one("#num_per_page").IntegerInput.value
        sort=self._sortkey or "number"
        reverse=str(self._reverse)
        self.query(".search_info")[0].update(f"[bold blue]Page Info[/bold blue]: \[Page: {page}] \[Num_per_page: {num_page}]")
        self.query(".search_info")[1].update(f"[bold blue]Sort Info[/bold blue]: \[Sort: {sort}] \[reverse: {reverse}]")

app = InputApp()

>>>>>>> fasttable
