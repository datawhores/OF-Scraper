import logging
import queue
import re
import arrow
from rich.text import Text
from textual import events
from textual.app import App
from textual.widgets import Button, ContentSwitcher, Checkbox, Input
from ofscraper.classes.table.utils.names import get_col_names, get_input_names
from ofscraper.classes.table.utils.lock import mutex
from ofscraper.classes.table.sections.table import get_styled
from ofscraper.classes.table.css import CSS
from ofscraper.classes.table.const import AMOUNT_PER_PAGE
from ofscraper.classes.table.compose import composer
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.settings as settings
import ofscraper.utils.console as console_

log = logging.getLogger("shared")
app = None
row_queue = queue.Queue()


class InputApp(App):
    BINDINGS = [
        ("ctrl+s", "toggle_options_sidebar"),
        ("ctrl+d", "toggle_download_sidebar"),
        ("a", "select_current_page", "Add Page"),
        ("A", "select_all_filtered", "Add All Filtered"),
        ("u", "select_unique_current_page", "Add Unique Page"),
        ("U", "select_unique_all_filtered", "Add All Unique"),
        ("e", "select_page_undownloaded", "Add Page New"),
        ("E", "select_all_undownloaded", "Add All New"),
        ("c", "clear_current_page", "Clear Page"),
        ("C", "clear_all_filtered", "Clear All Filtered"),
        ("x", "clear_entire_cart", "Nuke Cart"),
    ]
    CSS = CSS

    def __init__(self, *args, **kwargs) -> None:
        self.sidebar = None
        self._filtered_rows = []
        
        # Dedicated Pagination State
        self.main_page = 1
        self.cart_page = 1
        
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
        self.init_cart_table()   
        self.init_cart_toggles() 
        self.update_toggle_labels()
        self.set_active_tab("table")
        self.query_one("#main_per_page_input").value = str(AMOUNT_PER_PAGE)
        self.query_one("#cart_per_page_input").value = str(AMOUNT_PER_PAGE)
        logger.add_widget(self.query_one("#console_page_log"))
        console_.get_shared_console().quiet = True

    # --- UI Events ---
    def on_data_table_header_selected(self, event):
        clean_label = event.label.plain.replace(" ▼", "").replace(" ▲", "")
        key = re.sub(" ", "_", clean_label).lower()
        if key == "download_cart":
            table_id = event.control.id
            if table_id == "data_table":
                self.action_select_current_page()
            elif table_id == "cart_data_table":
                self.action_clear_current_page()
        else:
            self.update_table_sort(key)
            self.update_search_info()

    def on_checkbox_changed(self, event: Checkbox.Changed):
        if event.checkbox.id not in ["cart_text_toggle", "cart_text_only_toggle"]:
            return
            
        args = settings.get_args()
        if event.checkbox.id == "cart_text_toggle":
            args.text = event.checkbox.value
            if event.checkbox.value and self.query_one("#cart_text_only_toggle").value:
                self.query_one("#cart_text_only_toggle").value = False
        elif event.checkbox.id == "cart_text_only_toggle":
            args.text_only = event.checkbox.value
            if event.checkbox.value and self.query_one("#cart_text_toggle").value:
                self.query_one("#cart_text_toggle").value = False
                
        settings.update_args(args)

    def on_data_table_cell_selected(self, event):
        table = event.control
        col_name = table.ordered_columns_keys[event.coordinate.column]
        row_key = event.cell_key.row_key.value

        if col_name == "download_cart":
            if table.id == "data_table":
                for row in self._filtered_rows:
                    if str(row["index"]) == row_key:
                        # Prevent manually clicking locked or unknown media
                        if row.get("download_type") == "unknown" or not row.get("unlocked"):
                            break
                            
                        current = row["download_cart"]
                        if current in {"[]", "[downloaded]", "[failed]"}:
                            row["download_cart"] = "[added]"
                        elif current == "[added]":
                            row["download_cart"] = "[]"

                        styled_text = Text(row["download_cart"], style="bold light_goldenrod2")
                        table.update_cell_at_coord(event.coordinate, styled_text)
                        break
                self.update_cart_info()

            elif table.id == "cart_data_table":
                self.update_cell_state(row_key, "[]", "bold light_goldenrod2")
                self.update_cart_table() 

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        
        # Tabs
        if btn_id in ["console", "table", "cart"]:
            if btn_id == "cart":
                self.update_cart_table() 
            self.query_one(ContentSwitcher).current = f"{btn_id}_page"
            self.set_active_tab(btn_id)
            
        # Top level controls
        elif btn_id == "reset":
            self.reset_table()
        elif btn_id in ["send_downloads", "send_downloads_main"]:
            log.info("Adding Downloads to queue")
            self.add_to_row_queue()
            self.query_one(ContentSwitcher).current = "console_page"
            
        # Filter triggers
        elif btn_id in ["filter", "filter2"]:
            self.query_one("#options_sidebar").toggle_hidden()
            self.filter_table()
            self.update_toggle_labels()
            
        # Pagination Logic
        elif btn_id in ["main_first", "main_prev", "main_next", "main_last", "main_go"]:
            self.handle_pagination("main", btn_id)
        elif btn_id in ["cart_first", "cart_prev", "cart_next", "cart_last", "cart_go"]:
            self.handle_pagination("cart", btn_id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Allows user to hit Enter in the pagination boxes instead of clicking Go"""
        input_id = event.input.id
        if input_id in ["main_page_input", "main_per_page_input"]:
            self.handle_pagination("main", "main_go")
        elif input_id in ["cart_page_input", "cart_per_page_input"]:
            self.handle_pagination("cart", "cart_go")

    def on_key(self, event: events.Key) -> None:
        if event.character in {";", "'"}:
            table = self.table
            cursor_coordinate = table.cursor_coordinate
            _, col = cursor_coordinate
            if len(table.ordered_rows) == 0:
                return
            col_name = table.ordered_columns_keys[col]
            if col_name not in {"other_posts_with_media", "download_cart"}:
                self.update_input(col_name, table.get_cell_at(cursor_coordinate))

    # --- Sidebars Actions ---
    def action_toggle_options_sidebar(self) -> None:
        if self.query_one(ContentSwitcher).current != "table_page": return
        for ele in filter(lambda x: x.id != "options_sidebar", self.query("Sidebar.-show")):
            ele.toggle_hidden()
        self.query_one("#options_sidebar").toggle_hidden()
        self.update_toggle_labels()

    def action_toggle_download_sidebar(self) -> None:
        if self.query_one(ContentSwitcher).current != "table_page": return
        for ele in filter(lambda x: x.id != "download_option_sidebar", self.query("Sidebar.-show")):
            ele.toggle_hidden()
        self.query_one("#download_option_sidebar").toggle_hidden()
        self.update_toggle_labels()

    def update_toggle_labels(self) -> None:
        try:
            opt_open = self.query_one("#options_sidebar").has_class("-show")
            dl_open = self.query_one("#download_option_sidebar").has_class("-show")

            self.query_one("#label_opt_sidebar").update(f"Options Menu:  [bold cyan]Ctrl+S[/bold cyan] [bold]({'Open' if opt_open else 'Closed'})[/bold]")
            self.query_one("#label_dl_sidebar").update(f"Download Menu: [bold cyan]Ctrl+D[/bold cyan] [bold]({'Open' if dl_open else 'Closed'})[/bold]")
        except:
            pass

    def set_active_tab(self, active_btn_id: str):
        """Highlights the active tab button using Textual's native variants."""
        for btn_id in ["table", "cart", "console"]:
            try:
                btn = self.query_one(f"#{btn_id}", Button)
                if btn_id == active_btn_id:
                    btn.variant = "primary"  # Natively turns the button blue!
                else:
                    btn.variant = "default"  # Returns the button to standard gray
            except Exception:
                pass

    # ==========================================
    # --- Pagination Controller ---
    # ==========================================
    def update_pagination_btns(self, prefix: str, current_page: int, total_pages: int):
        """Dynamically hides/shows pagination buttons based on current page"""
        try:
            # .display = False completely removes the arrows from the screen!
            # We use > 1 so they only show up if you are on Page 2 or higher.
            self.query_one(f"#{prefix}_first").display = (current_page > 1)
            self.query_one(f"#{prefix}_prev").display = (current_page > 1)
            
            # We use < total_pages so they vanish when you hit the last page.
            self.query_one(f"#{prefix}_next").display = (current_page < total_pages)
            self.query_one(f"#{prefix}_last").display = (current_page < total_pages)
        except Exception as e:
            log.debug(f"Error updating pagination buttons: {e}")

    def handle_pagination(self, prefix, btn_id):
        # 1. Select the correct data source based on tab
        rows = self._filtered_rows if prefix == "main" else [r for r in self.table_data if r.get("download_cart") == "[added]"]
        
        per_page_node = self.query_one(f"#{prefix}_per_page_input")
        per_page_val = per_page_node.value
        
        if per_page_val and str(per_page_val).isnumeric() and int(per_page_val) > 0:
            num_page = int(per_page_val)
        else:
            # If empty or invalid, force it back to 100
            num_page = AMOUNT_PER_PAGE
            per_page_node.value = str(AMOUNT_PER_PAGE)
        
        # 3. Calculate Boundaries
        total_pages = max((len(rows) + num_page - 1) // num_page, 1)
        current_page = self.main_page if prefix == "main" else self.cart_page

        # 4. Handle Actions
        action = btn_id.replace(f"{prefix}_", "")
        if action == "first":
            current_page = 1
        elif action == "prev":
            current_page = max(1, current_page - 1)
        elif action == "next":
            current_page = min(total_pages, current_page + 1)
        elif action == "last":
            current_page = total_pages
        elif action == "go":
            target_node = self.query_one(f"#{prefix}_page_input")
            target = target_node.value
            if target and str(target).isnumeric():
                current_page = min(total_pages, max(1, int(target)))
                target_node.value = "" # Clear the jump box after action

        # 5. Apply Changes
        current_page = min(total_pages, max(1, current_page))
        if prefix == "main":
            self.main_page = current_page
            self.set_page()
        else:
            self.cart_page = current_page
            self.update_cart_table()

    # ==========================================
    # --- Cart: Add Actions (Additive Only) ---
    # ==========================================
    def action_select_current_page(self) -> None:
        if self.is_sidebar_open or self.query_one(ContentSwitcher).current != "table_page": return
        num_page = int(self.query_one("#main_per_page_input").value or AMOUNT_PER_PAGE)
        start = (self.main_page - 1) * num_page
        self._add_items_to_cart(self._filtered_rows[start : start + num_page])

    def action_select_all_filtered(self) -> None:
        if self.is_sidebar_open or self.query_one(ContentSwitcher).current != "table_page": return
        self._add_items_to_cart(self._filtered_rows)

    def _add_items_to_cart(self, rows_to_evaluate: list):
        if not rows_to_evaluate: return
        for row in rows_to_evaluate:
            # Skip locked or unknown media
            if row.get("download_type") == "unknown" or not row.get("unlocked"):
                continue
            if row["download_cart"] in {"[]", "[downloaded]", "[failed]"}:
                row["download_cart"] = "[added]"
        self.set_page()
        self.update_cart_info()

    def action_select_unique_current_page(self) -> None:
        if self.is_sidebar_open or self.query_one(ContentSwitcher).current != "table_page": return
        num_page = int(self.query_one("#main_per_page_input").value or AMOUNT_PER_PAGE)
        start = (self.main_page - 1) * num_page
        self._run_unique_selection(self._filtered_rows[start : start + num_page])

    def action_select_unique_all_filtered(self) -> None:
        if self.is_sidebar_open or self.query_one(ContentSwitcher).current != "table_page": return
        self._run_unique_selection(self._filtered_rows)

    def _run_unique_selection(self, rows_to_evaluate: list):
        if not rows_to_evaluate: return
        eligible = [
            r for r in rows_to_evaluate 
            if r["download_cart"] in {"[]", "[downloaded]", "[failed]"}
            and r.get("download_type") != "unknown"
            and r.get("unlocked")
        ]
        if not eligible: return

        global_cart_ids = {r["media_id"] for r in self.table_data if r["download_cart"] in {"[added]", "[downloading]"}}
        for row in eligible:
            m_id = row["media_id"]
            if m_id not in global_cart_ids:
                row["download_cart"] = "[added]"
                global_cart_ids.add(m_id)

        self.set_page()
        self.update_cart_info()

    def action_select_page_undownloaded(self) -> None:
        if self.is_sidebar_open or self.query_one(ContentSwitcher).current != "table_page": return
        num_page = int(self.query_one("#main_per_page_input").value or AMOUNT_PER_PAGE)
        start = (self.main_page - 1) * num_page

        for row in self._filtered_rows[start : start + num_page]:
            # Skip locked or unknown media
            if row.get("download_type") == "unknown" or not row.get("unlocked"):
                continue
            if not row["downloaded"] and row["download_cart"] in {"[]", "[failed]"}:
                row["download_cart"] = "[added]"
        self.set_page()
        self.update_cart_info()

    def action_select_all_undownloaded(self) -> None:
        if self.is_sidebar_open or self.query_one(ContentSwitcher).current != "table_page": return
        for row in self._filtered_rows:
            # Skip locked or unknown media
            if row.get("download_type") == "unknown" or not row.get("unlocked"):
                continue
            if not row["downloaded"] and row["download_cart"] in {"[]", "[failed]"}:
                row["download_cart"] = "[added]"
        self.set_page()
        self.update_cart_info()

    # ==========================================
    # --- Cart: Clear Actions ---
    # ==========================================
    def action_clear_current_page(self) -> None:
        if self.is_sidebar_open: return
        active_tab = self.query_one(ContentSwitcher).current
        if active_tab == "table_page":
            num_page = int(self.query_one("#main_per_page_input").value or AMOUNT_PER_PAGE)
            start = (self.main_page - 1) * num_page
            for row in self._filtered_rows[start : start + num_page]:
                if row["download_cart"] == "[added]":
                    row["download_cart"] = "[]"
                    
        elif active_tab == "cart_page":
            cart_rows = [row for row in self.table_data if row.get("download_cart") == "[added]"]
            num_page = int(self.query_one("#cart_per_page_input").value or AMOUNT_PER_PAGE)
            start = (self.cart_page - 1) * num_page
            for row in cart_rows[start : start + num_page]:
                row["download_cart"] = "[]"
                
        self.set_page()
        self.update_cart_table()
        self.update_cart_info()

    def action_clear_all_filtered(self) -> None:
        if self.is_sidebar_open: return
        active_tab = self.query_one(ContentSwitcher).current
        if active_tab == "table_page":
            for row in self._filtered_rows:
                if row["download_cart"] == "[added]":
                    row["download_cart"] = "[]"
            self.set_page()
            self.update_cart_table()
            self.update_cart_info()
        elif active_tab == "cart_page":
            self.action_clear_entire_cart() # Shift+C on the cart page nukes the cart

    def action_clear_entire_cart(self) -> None:
        """Nukes everything currently marked as [added] in the global table."""
        if self.is_sidebar_open: return
        for row in self.table_data:
            if row["download_cart"] == "[added]":
                row["download_cart"] = "[]"
        
        self.set_page()
        self.update_cart_table()
        self.update_cart_info()    
    
    # --- Rest of Table Logic ---
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

    def update_cell_state(self, row_key, new_state, style="white"):
        """Allows background threads to safely update the table state and UI"""
        for row in self.table_data:
            if str(row["index"]) == str(row_key):
                row["download_cart"] = new_state
                if new_state in {"[downloaded]", "[skipped]"}:
                    row["downloaded"] = True
                break

        try:
            self.table.update_cell_at_key(str(row_key), "download_cart", Text(new_state, style=style))
        except Exception:
            pass

        self.update_cart_info()
        self.update_search_info()

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
            is_empty = False
            sort_val = 0
            raw_val = x.get(key)
            if key == "length" and raw_val in {"N/A", "N\\A"}:
                is_empty = True
            elif key == "post_date" and str(raw_val) == "Probably Deleted":
                is_empty = True
                
            if not is_empty:
                if key == "number":
                    sort_val = int(raw_val or 0)
                elif key == "post_media_count":
                    sort_val = int(raw_val or 0)
                elif key == "price":
                    sort_val = 0 if str(raw_val).lower() == "free" else float(raw_val or 0)
                elif key == "length":
                    sort_val = arrow.get(raw_val or "0:0:0", ["h:m:s"]).timestamp()
                elif key == "post_date":
                    sort_val = arrow.get(raw_val).timestamp()
                elif key in {"post_id", "media_id"}:
                    sort_val = int(raw_val or 0)
                elif key == "other_posts_with_media":
                    sort_val = len(raw_val or [])
                else:
                    sort_val = str(raw_val or "")
                    
            if self._reverse:
                group = 0 if is_empty else 1
            else:
                group = 1 if is_empty else 0
                
            return (group, sort_val)

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
                    filter_rows2 = [row for row in filter_rows if filter_node.compare(str(row.get(name, "")))]
                    filter_rows = filter_rows2
                except Exception as E:
                    log.debug(f"Error filtering {name}: {str(E)}")
            self._filtered_rows = filter_rows

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
                
    # --- Cart Table Features ---
    def init_cart_table(self):
        self._insert_visible_table(self.query_one("#cart_data_table"))

    def init_cart_toggles(self):
        args = settings.get_args()
        self.query_one("#cart_text_toggle").value = bool(args.text)
        self.query_one("#cart_text_only_toggle").value = bool(args.text_only)

    def update_cart_table(self):
        try:
            cart_table = self.query_one("#cart_data_table")
            cart_table.clear()
            
            # 1. Get all items currently in the cart
            cart_rows = [row for row in self.table_data if row.get("download_cart") == "[added]"]
            
            # 2. Get the current "Per Page" value safely
            per_page_val = self.query_one("#cart_per_page_input").value
            num_page = int(per_page_val) if per_page_val and str(per_page_val).isnumeric() else AMOUNT_PER_PAGE
            
            # 3. Calculate pagination boundaries
            total_pages = max((len(cart_rows) + num_page - 1) // num_page, 1)
            
            # Boundary correction if items were removed and the current page no longer exists
            if self.cart_page > total_pages:
                self.cart_page = total_pages
                
            start = (self.cart_page - 1) * num_page
            
            # 4. Add the rows to the table
            for count, row_dict in enumerate(cart_rows[start : start + num_page]):
                styled_row = get_styled(row_dict)
                key = str(row_dict["index"])
                cart_table.add_row(
                    *styled_row, height=None, key=key, label=str(start + count + 1)
                )
                
            # 5. Update the UI text and disable/enable buttons dynamically
            self.query_one("#cart_page_label").update(f"Page {self.cart_page} of {total_pages}")
            self.update_pagination_btns("cart", self.cart_page, total_pages)
            
        except Exception as e:
            log.debug(f"Error updating cart table: {e}")

    def init_download_filter(self):
        if settings.get_settings().size_max:
            self.query_one("#download_size_max").update_table_val(settings.get_settings().size_max)
        if settings.get_settings().size_min:
            self.query_one("#download_size_min").update_table_val(settings.get_settings().size_min)

    def reset_table(self):
        self.reset_all_inputs()
        self.reset_sort()
        self.set_filtered_rows()
        self.main_page = 1
        self.set_page()
        self.update_search_info()

    def update_table_sort(self, key):
        self.set_sort(key)
        active_tab = self.query_one(ContentSwitcher).current
        if active_tab == "table_page":
            self._insert_visible_table(self.query_one("#data_table"))
            self.set_filtered_rows()
            self.set_page()
        elif active_tab == "cart_page":
            self._insert_visible_table(self.query_one("#cart_data_table"))
            self.update_cart_table()

    def filter_table(self):
        self.set_filtered_rows()
        self.main_page = 1
        self.set_page()
        self.update_search_info()

    def set_page(self):
        with mutex:
            self.table.clear()
            rows = self._filtered_rows
            
            # 1. Get the current "Per Page" value safely
            per_page_val = self.query_one("#main_per_page_input").value
            num_page = int(per_page_val) if per_page_val and str(per_page_val).isnumeric() else AMOUNT_PER_PAGE
            
            # 2. Calculate pagination boundaries
            total_pages = max((len(rows) + num_page - 1) // num_page, 1)
            
            if self.main_page > total_pages:
                self.main_page = total_pages
                
            start = (self.main_page - 1) * num_page

            # 3. Add the rows to the table
            for count, row_dict in enumerate(rows[start : start + num_page]):
                styled_row = get_styled(row_dict)
                key = str(row_dict["index"])
                self.table.add_row(
                    *styled_row, height=None, key=key, label=str(start + count + 1)
                )
                
            try:
                self.query_one("#main_page_label").update(f"Page {self.main_page} of {total_pages}")
                self.update_pagination_btns("main", self.main_page, total_pages) 
            except Exception:
                pass

    def init_table(self):
        self._insert_visible_table()
        self.init_sort()
        self.init_filtered_rows()
        self.init_download_filter()
        self.set_page()
        self.update_search_info()
        self.update_cart_info()

    def _insert_visible_table(self, target_table=None):
        table = target_table if target_table is not None else self.table
        table.clear(True) 
        table.fixed_rows = 0
        table.zebra_stripes = True

        for ele in get_col_names():
            width = 18
            width = 50 if ele == "text" else width
            width = 30 if ele == "other_posts_with_media" else width

            base_label = re.sub("_", " ", ele).title()

            if str(ele) == self._sortkey:
                arrow_char = " ▼" if self._reverse else " ▲"
                label = f"{base_label}{arrow_char}"
            else:
                label = base_label

            table.add_column(label, key=str(ele), width=width)    

    def update_search_info(self):
        num_page = self.query_one("#main_per_page_input").value or AMOUNT_PER_PAGE
        sort_key = self._sortkey or "number"
        sort_dir = "Desc" if self._reverse else "Asc"
        clean_sort_name = re.sub("_", " ", sort_key).title()

        total_items = len(self.table_data)
        unlocked_items = sum(1 for row in self.table_data if row.get("unlocked") is True)

        db_dl = sum(1 for row in self.table_data if row.get("downloaded") is True)
        db_miss = sum(1 for row in self.table_data if row.get("unlocked") is True and not row.get("downloaded"))

        undownloaded_rows = [row for row in self.table_data if row.get("unlocked") is True and not row.get("downloaded")]
        unique_to_download = len(set(row.get("media_id") for row in undownloaded_rows if "media_id" in row))

        filtered_items = len(self._filtered_rows)
        unique_items = len(set(row.get("media_id") for row in self._filtered_rows if "media_id" in row))

        vids = sum(1 for r in self._filtered_rows if str(r.get("mediatype")).lower() == "videos")
        pics = sum(1 for r in self._filtered_rows if str(r.get("mediatype")).lower() == "images")
        auds = sum(1 for r in self._filtered_rows if str(r.get("mediatype")).lower() == "audios")

        try:
            db_line_1 = f"[bold blue]Database:[/bold blue]  \\[Total: {total_items}] \\[Unlocked: {unlocked_items}]"
            db_line_2 = f"[bold blue]DL Status:[/bold blue] \\[DL'd: {db_dl}] \\[Missing: {db_miss}] \\[Unique Missing: {unique_to_download}]"
            self.query_one("#db_info_bar").update(f"{db_line_1}\n{db_line_2}")

            view_str = f"[bold blue]View:[/bold blue]   \\[Page: {self.main_page}] \\[Per Page: {num_page}] \\[Sort: {clean_sort_name} ({sort_dir})]"
            filt_str = f"[bold blue]Filter:[/bold blue] \\[Total: {filtered_items}] \\[Unique: {unique_items}]"
            type_str = f"[bold blue]Media:[/bold blue]  \\[Vids: {vids}] \\[Pics: {pics}] \\[Aud: {auds}]"

            if filtered_items == 0:
                self.query_one("#view_info_bar").update(f"{view_str}\n{filt_str}\n{type_str}\n[bold red]All Items Filtered Out[/bold red]")
            else:
                self.query_one("#view_info_bar").update(f"{view_str}\n{filt_str}\n{type_str}")
        except:
            pass

    def update_cart_info(self):
        in_cart = sum(1 for row in self.table_data if row["download_cart"] == "[added]")
        downloading = sum(1 for row in self.table_data if row["download_cart"] == "[downloading]")
        try:
            cart_line = f"[bold blue]Cart:[/bold blue]      \\[Queued: {in_cart}] \\[Active: {downloading}]"
            for widget in self.query(".global_cart_info"):
                widget.update(cart_line)
        except:
            pass

    @property
    def table(self):
        return self.query_one("#data_table")
    @property
    def is_sidebar_open(self) -> bool:
        """Checks if any sidebar is currently visible."""
        try:
            opt_open = self.query_one("#options_sidebar").has_class("-show")
            dl_open = self.query_one("#download_option_sidebar").has_class("-show")
            return opt_open or dl_open
        except Exception:
            return False

app = InputApp()