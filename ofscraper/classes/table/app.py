import logging
import queue
import re
import arrow
from rich.text import Text
from textual import events
from textual.app import App
from textual.widgets import Button, ContentSwitcher
from ofscraper.classes.table.utils.names import get_col_names, get_input_names
from ofscraper.classes.table.utils.lock import mutex
from ofscraper.classes.table.sections.table_console import OutConsole
from ofscraper.classes.table.sections.table import get_styled
from textual.widgets import SelectionList
from ofscraper.classes.table.css import CSS
from ofscraper.classes.table.const import AMOUNT_PER_PAGE, START_PAGE
from ofscraper.classes.table.compose import composer
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.settings as settings

log = logging.getLogger("shared")
app = None
row_queue = queue.Queue()


class InputApp(App):
    BINDINGS = [
        ("ctrl+t", "toggle_page_sidebar"),
        ("ctrl+s", "toggle_options_sidebar"),
        ("ctrl+d", "toggle_download_sidebar"),
        ("a", "select_current_page", "Select Current Page"),
        ("ctrl+a", "select_all_filtered", "Select All Filtered"),
    ]
    CSS = CSS

    def __init__(self, *args, **kwargs) -> None:
        self.sidebar = None
        self._filtered_rows = []
        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        self.table_data = kwargs.pop("table_data", [])
        self._sortkey = None
        self._reverse = False
        self._download_cart_toggle = False
        self.run()

    def compose(self):
        try:
            return composer()
        except Exception as e:
            pass

    def on_ready(self) -> None:
        self.init_table()
        logger.add_widget(self.query_one("#console_page").query_one(OutConsole))

    # --- UI Events ---
    def on_data_table_header_selected(self, event):
        key = re.sub(" ", "_", event.label.plain).lower()
        if key == "download_cart":
            self.action_select_current_page() # Default header click to current page only
        else:
            self.update_table_sort(key)
            self.update_search_info()

    def on_data_table_cell_selected(self, event):
        col_name = self.table.ordered_columns_keys[event.coordinate.column]
        if col_name == "download_cart":
            row_key = event.cell_key.row_key.value
            
            # Update the Native Data State
            for row in self._filtered_rows:
                if str(row["index"]) == row_key:
                    current = row["download_cart"]
                    if current == "[]":
                        row["download_cart"] = "[added]"
                    elif current == "[added]":
                        row["download_cart"] = "[]"
                    elif current in ["[downloaded]", "[failed]"]:
                        row["download_cart"] = "[added]"
                    
                    # Update UI directly for instant feedback
                    styled_text = Text(row["download_cart"], style="bold light_goldenrod2")
                    self.table.update_cell_at_coord(event.coordinate, styled_text)
                    break
                    
            self.update_cart_info()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "reset":
            self.reset_table()
        elif event.button.id == "send_downloads":
            log.info("Adding Downloads to queue")
            self.add_to_row_queue()
            self.query_one(ContentSwitcher).current = "console_page"
        elif event.button.id in ["filter", "filter2"]:
            self.query_one("#options_sidebar").toggle_hidden()
            self.filter_table()
        elif event.button.id in ["page_enter", "page_enter2"]:
            self.query_one("#page_option_sidebar").toggle_hidden()
            self.filter_table()
        elif event.button.id in ["console", "table"]:
            self.query_one(ContentSwitcher).current = f"{event.button.id}_page"

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.exit()
        if event.character in {";", "'"}:
            table = self.table
            cursor_coordinate = table.cursor_coordinate
            _, col = cursor_coordinate
            if len(table.ordered_rows) == 0:
                return
            col_name = table.ordered_columns_keys[col]
            if col_name not in {"other_posts_with_media", "download_cart"}:
                self.update_input(col_name, table.get_cell_at(cursor_coordinate))

    # --- Actions ---
    def action_toggle_options_sidebar(self) -> None:
        for ele in filter(lambda x: x.id != "options_sidebar", self.query("Sidebar.-show")):
            ele.toggle_hidden()
        self.query_one("#options_sidebar").toggle_hidden()

    def action_toggle_page_sidebar(self) -> None:
        for ele in filter(lambda x: x.id != "page_option_sidebar", self.query("Sidebar.-show")):
            ele.toggle_hidden()
        self.query_one("#page_option_sidebar").toggle_hidden()

    def action_toggle_download_sidebar(self) -> None:
        for ele in filter(lambda x: x.id != "download_option_sidebar", self.query("Sidebar.-show")):
            ele.toggle_hidden()
        self.query_one("#download_option_sidebar").toggle_hidden()

    def action_select_current_page(self) -> None:
        """
        Toggles only the items currently visible on the active page.
        """
        valid_states = {"[]", "[added]", "[downloaded]", "[failed]"}
        rows = self._filtered_rows
        num_page = int(self.query_one("#num_per_page_input").value or AMOUNT_PER_PAGE)
        
        # Safe page boundary math
        total_pages = max((len(rows) + num_page - 1) // num_page, 1)
        page = min(int(self.query_one("#page_input").value) or 1, total_pages)
        
        start = (page - 1) * num_page
        current_page_rows = rows[start : start + num_page]

        if not current_page_rows:
            return

        all_selected = True
        for row in current_page_rows:
            if row["download_cart"] == "[]":
                all_selected = False
                break

        new_val = "[]" if all_selected else "[added]"

        for row in current_page_rows:
            if row["download_cart"] in valid_states:
                row["download_cart"] = new_val

        self.set_page()
        self.update_cart_info()

    def action_select_all_filtered(self) -> None:
        """
        Modifies the underlying dicts across all pages instantly (Ctrl+A).
        """
        valid_states = {"[]", "[added]", "[downloaded]", "[failed]"}
        
        all_selected = True
        for row in self._filtered_rows:
            if row["download_cart"] == "[]":
                all_selected = False
                break
                
        new_val = "[]" if all_selected else "[added]"
        
        for row in self._filtered_rows:
            if row["download_cart"] in valid_states:
                row["download_cart"] = new_val
                
        self.set_page() 
        self.update_cart_info()

    # --- Cart Management ---
    def add_to_row_queue(self):
        cart = []
        for row in self.table_data:
            if row["download_cart"] == "[added]":
                row["download_cart"] = "[downloading]" 
                cart.append((str(row["index"]), row))
                
        self.set_page() 
        self.update_cart_info()
        
        for ele in cart:
            row_queue.put(ele)
        log.info(f"Number of Downloads sent to queue {len(cart)}")

    # --- Native Python Sorting ---
    def init_sort(self):
        self._reverse = settings.get_settings().desc or False
        self._sortkey = settings.get_settings().db_sort or "number"
        self._sort_runner(key=self._sortkey)

    def reset_sort(self):
        self._reverse = False
        self._sortkey = "number"
        self._sort_runner(key=self._sortkey)

    def set_sort(self, label):
        with mutex:
            self.set_reverse(key=label)
            self._sort_runner(label)

    def _sort_runner(self, key):
        def sort_key_func(x):
            if key == "number": return int(x.get("number", 0))
            if key == "post_media_count": return int(x.get("post_media_count", 0))
            if key == "price": return 0 if str(x.get("price")).lower() == "free" else float(x.get("price", 0))
            if key == "length": 
                return arrow.get(x.get("length", "0:0:0"), ["h:m:s"]).timestamp() if x.get("length") not in {"N/A", "N\\A"} else 0
            if key == "post_date": 
                return arrow.get(x.get("post_date")).timestamp() if str(x.get("post_date")) != "Probably Deleted" else 0
            if key in {"post_id", "media_id"}: return int(x.get(key, 0))
            if key == "other_posts_with_media": return len(x.get("other_posts_with_media", []))
            return str(x.get(key, ""))
            
        self.table_data.sort(key=sort_key_func, reverse=self._reverse)

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

    # --- Native Python Filtering ---
    def init_filtered_rows(self):
        self._filter_runner()

    def set_filtered_rows(self):
        self._filter_runner()

    def _filter_runner(self):
        with mutex:
            filter_rows = self.table_data
            for name in get_col_names():
                if name in {"number", "download_cart", "other_posts_with_media"}:
                    continue
                try:
                    filter_node = self.query_one(f"#{name}")
                    filter_rows = [row for row in filter_rows if filter_node.compare(str(row.get(name, "")))]
                except Exception as E:
                    log.debug(f"Error filtering {name}: {str(E)}")
            self._filtered_rows = filter_rows

    # --- Inputs ---
    def update_input(self, col_name, value):
        try:
            value = value.plain if isinstance(value, Text) else value
            targetNode = self.query_one(f"#{col_name}")
            targetNode.update_table_val(value)
        except:
            pass

    def reset_all_inputs(self):
        for ele in get_input_names():
            try:
                self.query_one(f"#{ele}").reset()
            except:
                continue

    def init_download_filter(self):
        if settings.get_settings().size_max:
            self.query_one("#download_size_max").update_table_val(settings.get_settings().size_max)
        if settings.get_settings().size_min:
            self.query_one("#download_size_min").update_table_val(settings.get_settings().size_min)

    # --- Table Layout & Pagination ---
    def reset_table(self):
        self.reset_all_inputs()
        self.reset_sort()
        self.set_filtered_rows()
        self.set_page()
        self.update_search_info()

    def update_table_sort(self, key):
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
            rows = self._filtered_rows
            num_page = int(self.query_one("#num_per_page_input").value or AMOUNT_PER_PAGE)
            
            # FIXED PAGINATION MATH
            total_pages = max((len(rows) + num_page - 1) // num_page, 1)
            page = min(int(self.query_one("#page_input").value) or 1, total_pages)
            
            start = (page - 1) * num_page
            
            for count, row_dict in enumerate(rows[start : start + num_page]):
                styled_row = get_styled(row_dict)
                key = str(row_dict["index"])
                self.table.add_row(*styled_row, height=None, key=key, label=str(start + count + 1))

    def init_table(self):
        self._insert_visible_table()
        self.init_sort()
        self.init_filtered_rows()
        self.init_download_filter()
        self.set_page()
        self.update_search_info()

    def _insert_visible_table(self):
        table = self.table
        table.clear(True)
        table.fixed_rows = 0
        table.zebra_stripes = True
        for ele in get_col_names():
            width = 18
            width = 50 if ele == "text" else width
            width = 30 if ele == "other_posts_with_media" else width
            table.add_column(re.sub("_", " ", ele).title(), key=str(ele), width=width)

    # --- Stats ---
    def update_search_info(self):
        page = self.query_one("#page").integer_input.value
        num_page = self.query_one("#num_per_page").integer_input.value
        sort_key = self._sortkey or "number"
        reverse = str(self._reverse)
        self.query(".search_info")[0].update(
            f"[bold blue]Page Info[/bold blue]: \[Page: {page}] \[Num_per_page: {num_page}] [Total With Filters: {len(self._filtered_rows)}] [Total: {len(self.table_data)}]"
        )
        self.query(".search_info")[1].update(
            f"[bold blue]Sort Info[/bold blue]: \[Sort: {sort_key}] \[Reversed: {reverse}]"
        )
        if len(self._filtered_rows) == 0:
            self.query(".search_info")[2].update(
                "[bold blue]Additional Info[/bold blue]: All Items Filtered"
            )

    def update_cart_info(self):
        download_cart = sum(1 for row in self.table_data if row["download_cart"] == "[added]")
        self.query(".search_info")[2].update(
            f"[bold blue]Items in Cart[/bold blue]: {download_cart}"
        )

    @property
    def table(self):
        return self.query_one("#data_table")

app = InputApp()