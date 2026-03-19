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
import ofscraper.utils.console as console_

log = logging.getLogger("shared")
app = None
row_queue = queue.Queue()


class InputApp(App):
    BINDINGS = [
        # Sidebars
        ("ctrl+t", "toggle_page_sidebar"),
        ("ctrl+s", "toggle_options_sidebar"),
        ("ctrl+d", "toggle_download_sidebar"),
        # Standard Selection (Additive Only)
        ("a", "select_current_page", "Add Page"),
        ("A", "select_all_filtered", "Add All Filtered"),  # Shift+A
        # Unique Selection (Additive Only)
        ("u", "select_unique_current_page", "Add Unique Page"),
        ("U", "select_unique_all_filtered", "Add All Unique"),  # Shift+U
        # New/Undownloaded Selection (Additive Only)
        ("e", "select_page_undownloaded", "Add Page New"),
        ("E", "select_all_undownloaded", "Add All New"),  # Shift+E
        # Clear Cart Actions
        ("c", "clear_current_page", "Clear Page"),
        ("C", "clear_all_filtered", "Clear All Filtered"),  # Shift+C
        ("x", "clear_entire_cart", "Nuke Cart"),  # Global Clear
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
        self.update_toggle_labels()
        logger.add_widget(self.query_one("#console_page").query_one(OutConsole))
        console_.get_shared_console().quiet = True

    # --- UI Events ---
    def on_data_table_header_selected(self, event):
        # Strip out the arrows before generating the key
        clean_label = event.label.plain.replace(" ▼", "").replace(" ▲", "")
        key = re.sub(" ", "_", clean_label).lower()

        if key == "download_cart":
            self.action_select_current_page()
        else:
            self.update_table_sort(key)
            self.update_search_info()

    def on_data_table_cell_selected(self, event):
        # Single-cell clicking remains a toggle for precision control
        col_name = self.table.ordered_columns_keys[event.coordinate.column]
        if col_name == "download_cart":
            row_key = event.cell_key.row_key.value

            for row in self._filtered_rows:
                if str(row["index"]) == row_key:
                    current = row["download_cart"]
                    if current in {"[]", "[downloaded]", "[failed]"}:
                        row["download_cart"] = "[added]"
                    elif current == "[added]":
                        row["download_cart"] = "[]"

                    styled_text = Text(
                        row["download_cart"], style="bold light_goldenrod2"
                    )
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
            self.update_toggle_labels()
        elif event.button.id in ["page_enter", "page_enter2"]:
            self.query_one("#page_option_sidebar").toggle_hidden()
            self.filter_table()
            self.update_toggle_labels()
        elif event.button.id in ["console", "table"]:
            self.query_one(ContentSwitcher).current = f"{event.button.id}_page"

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

    # --- Sidebar Actions ---
    def action_toggle_options_sidebar(self) -> None:
        for ele in filter(
            lambda x: x.id != "options_sidebar", self.query("Sidebar.-show")
        ):
            ele.toggle_hidden()
        self.query_one("#options_sidebar").toggle_hidden()
        self.update_toggle_labels()

    def action_toggle_page_sidebar(self) -> None:
        for ele in filter(
            lambda x: x.id != "page_option_sidebar", self.query("Sidebar.-show")
        ):
            ele.toggle_hidden()
        self.query_one("#page_option_sidebar").toggle_hidden()
        self.update_toggle_labels()

    def action_toggle_download_sidebar(self) -> None:
        for ele in filter(
            lambda x: x.id != "download_option_sidebar", self.query("Sidebar.-show")
        ):
            ele.toggle_hidden()
        self.query_one("#download_option_sidebar").toggle_hidden()
        self.update_toggle_labels()

    def update_toggle_labels(self) -> None:
        opt_open = self.query_one("#options_sidebar").has_class("-show")
        page_open = self.query_one("#page_option_sidebar").has_class("-show")
        dl_open = self.query_one("#download_option_sidebar").has_class("-show")

        self.query_one("#label_opt_sidebar").update(
            f"Options Menu:  [bold cyan]Ctrl+S[/bold cyan] [bold]({'Open' if opt_open else 'Closed'})[/bold]"
        )
        self.query_one("#label_page_sidebar").update(
            f"Page Menu:     [bold cyan]Ctrl+T[/bold cyan] [bold]({'Open' if page_open else 'Closed'})[/bold]"
        )
        self.query_one("#label_dl_sidebar").update(
            f"Download Menu: [bold cyan]Ctrl+D[/bold cyan] [bold]({'Open' if dl_open else 'Closed'})[/bold]"
        )

    # ==========================================
    # --- Cart: Add Actions (Additive Only) ---
    # ==========================================
    def action_select_current_page(self) -> None:
        rows = self._filtered_rows
        num_page = int(self.query_one("#num_per_page_input").value or AMOUNT_PER_PAGE)
        total_pages = max((len(rows) + num_page - 1) // num_page, 1)
        page = min(int(self.query_one("#page_input").value) or 1, total_pages)
        start = (page - 1) * num_page
        self._add_items_to_cart(rows[start : start + num_page])

    def action_select_all_filtered(self) -> None:
        self._add_items_to_cart(self._filtered_rows)

    def _add_items_to_cart(self, rows_to_evaluate: list):
        if not rows_to_evaluate:
            return
        for row in rows_to_evaluate:
            if row["download_cart"] in {"[]", "[downloaded]", "[failed]"}:
                row["download_cart"] = "[added]"
        self.set_page()
        self.update_cart_info()

    # --- Unique Cart Actions ---
    def action_select_unique_current_page(self) -> None:
        rows = self._filtered_rows
        num_page = int(self.query_one("#num_per_page_input").value or AMOUNT_PER_PAGE)
        total_pages = max((len(rows) + num_page - 1) // num_page, 1)
        page = min(int(self.query_one("#page_input").value) or 1, total_pages)
        start = (page - 1) * num_page
        self._run_unique_selection(rows[start : start + num_page])

    def action_select_unique_all_filtered(self) -> None:
        self._run_unique_selection(self._filtered_rows)

    def _run_unique_selection(self, rows_to_evaluate: list):
        if not rows_to_evaluate:
            return

        eligible = [
            r
            for r in rows_to_evaluate
            if r["download_cart"] in {"[]", "[downloaded]", "[failed]"}
        ]
        if not eligible:
            return

        global_cart_ids = {
            r["media_id"]
            for r in self.table_data
            if r["download_cart"] in {"[added]", "[downloading]"}
        }

        for row in eligible:
            m_id = row["media_id"]
            if m_id not in global_cart_ids:
                row["download_cart"] = "[added]"
                global_cart_ids.add(m_id)

        self.set_page()
        self.update_cart_info()

    # --- New/Undownloaded Cart Actions ---
    def action_select_page_undownloaded(self) -> None:
        rows = self._filtered_rows
        num_page = int(self.query_one("#num_per_page_input").value or AMOUNT_PER_PAGE)
        total_pages = max((len(rows) + num_page - 1) // num_page, 1)
        page = min(int(self.query_one("#page_input").value) or 1, total_pages)
        start = (page - 1) * num_page

        for row in rows[start : start + num_page]:
            if not row["downloaded"] and row["download_cart"] in {"[]", "[failed]"}:
                row["download_cart"] = "[added]"
        self.set_page()
        self.update_cart_info()

    def action_select_all_undownloaded(self) -> None:
        for row in self._filtered_rows:
            if not row["downloaded"] and row["download_cart"] in {"[]", "[failed]"}:
                row["download_cart"] = "[added]"
        self.set_page()
        self.update_cart_info()

    # ==========================================
    # --- Cart: Clear Actions ---
    # ==========================================
    def action_clear_current_page(self) -> None:
        rows = self._filtered_rows
        num_page = int(self.query_one("#num_per_page_input").value or AMOUNT_PER_PAGE)
        total_pages = max((len(rows) + num_page - 1) // num_page, 1)
        page = min(int(self.query_one("#page_input").value) or 1, total_pages)
        start = (page - 1) * num_page

        for row in rows[start : start + num_page]:
            if row["download_cart"] == "[added]":
                row["download_cart"] = "[]"
        self.set_page()
        self.update_cart_info()

    def action_clear_all_filtered(self) -> None:
        for row in self._filtered_rows:
            if row["download_cart"] == "[added]":
                row["download_cart"] = "[]"
        self.set_page()
        self.update_cart_info()

    def action_clear_entire_cart(self) -> None:
        """Nukes everything currently marked as [added] in the global table."""
        for row in self.table_data:
            if row["download_cart"] == "[added]":
                row["download_cart"] = "[]"
        self.set_page()
        self.update_cart_info()

    # --- Rest of Table Logic (Unchanged) ---
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
                # Sync the boolean so 'Missing' and 'Status: DL'd' update live!
                if new_state in {"[downloaded]", "[skipped]"}:
                    row["downloaded"] = True
                break

        try:
            self.table.update_cell_at_key(
                str(row_key), "download_cart", Text(new_state, style=style)
            )
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
            if key == "number":
                return int(x.get("number", 0))
            if key == "post_media_count":
                return int(x.get("post_media_count", 0))
            if key == "price":
                return (
                    0
                    if str(x.get("price")).lower() == "free"
                    else float(x.get("price", 0))
                )
            if key == "length":
                return (
                    arrow.get(x.get("length", "0:0:0"), ["h:m:s"]).timestamp()
                    if x.get("length") not in {"N/A", "N\A"}
                    else 0
                )
            if key == "post_date":
                return (
                    arrow.get(x.get("post_date")).timestamp()
                    if str(x.get("post_date")) != "Probably Deleted"
                    else 0
                )
            if key in {"post_id", "media_id"}:
                return int(x.get(key, 0))
            if key == "other_posts_with_media":
                return len(x.get("other_posts_with_media", []))
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
                    filter_rows2 = [
                        row
                        for row in filter_rows
                        if filter_node.compare(str(row.get(name, "")))
                    ]
                    if len(filter_rows2) == 0:
                        pass
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

    def init_download_filter(self):
        if settings.get_settings().size_max:
            self.query_one("#download_size_max").update_table_val(
                settings.get_settings().size_max
            )
        if settings.get_settings().size_min:
            self.query_one("#download_size_min").update_table_val(
                settings.get_settings().size_min
            )

    def reset_table(self):
        self.reset_all_inputs()
        self.reset_sort()
        self.set_filtered_rows()
        self.set_page()
        self.update_search_info()

    def update_table_sort(self, key):
        self.set_sort(key)
        self._insert_visible_table()
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
            num_page = int(
                self.query_one("#num_per_page_input").value or AMOUNT_PER_PAGE
            )
            total_pages = max((len(rows) + num_page - 1) // num_page, 1)
            page = min(int(self.query_one("#page_input").value) or 1, total_pages)
            start = (page - 1) * num_page

            for count, row_dict in enumerate(rows[start : start + num_page]):
                styled_row = get_styled(row_dict)
                key = str(row_dict["index"])
                self.table.add_row(
                    *styled_row, height=None, key=key, label=str(start + count + 1)
                )

    def init_table(self):
        self._insert_visible_table()
        self.init_sort()
        self.init_filtered_rows()
        self.init_download_filter()
        self.set_page()
        self.update_search_info()
        self.update_cart_info()

    def _insert_visible_table(self):
        table = self.table
        table.clear(True)  # True clears columns and rows so we can rebuild headers
        table.fixed_rows = 0
        table.zebra_stripes = True

        for ele in get_col_names():
            width = 18
            width = 50 if ele == "text" else width
            width = 30 if ele == "other_posts_with_media" else width

            # Format the base label
            base_label = re.sub("_", " ", ele).title()

            # Add visual arrow if this is the active sort column
            if str(ele) == self._sortkey:
                arrow_char = " ▼" if self._reverse else " ▲"
                label = f"{base_label}{arrow_char}"
            else:
                label = base_label

            table.add_column(label, key=str(ele), width=width)

    def update_search_info(self):
        page = self.query_one("#page_input").value or START_PAGE
        num_page = self.query_one("#num_per_page_input").value or AMOUNT_PER_PAGE
        sort_key = self._sortkey or "number"
        sort_dir = "Desc" if self._reverse else "Asc"
        clean_sort_name = re.sub("_", " ", sort_key).title()

        # --- Column 1: Database & Global Stats ---
        total_items = len(self.table_data)
        unlocked_items = sum(
            1 for row in self.table_data if row.get("unlocked") is True
        )

        db_dl = sum(1 for row in self.table_data if row.get("downloaded") is True)
        db_miss = sum(
            1
            for row in self.table_data
            if row.get("unlocked") is True and not row.get("downloaded")
        )

        undownloaded_rows = [
            row
            for row in self.table_data
            if row.get("unlocked") is True and not row.get("downloaded")
        ]
        unique_to_download = len(
            set(row.get("media_id") for row in undownloaded_rows if "media_id" in row)
        )

        # --- Column 2: Filter Stats ---
        filtered_items = len(self._filtered_rows)
        unique_items = len(
            set(row.get("media_id") for row in self._filtered_rows if "media_id" in row)
        )

        # Media Type Breakdown for current filter
        vids = sum(
            1
            for r in self._filtered_rows
            if str(r.get("mediatype")).lower() == "videos"
        )
        pics = sum(
            1
            for r in self._filtered_rows
            if str(r.get("mediatype")).lower() == "images"
        )
        auds = sum(
            1
            for r in self._filtered_rows
            if str(r.get("mediatype")).lower() == "audios"
        )

        try:
            # Update Column 1 (Top Half)
            db_line_1 = f"[bold blue]Database:[/bold blue]  \[Total: {total_items}] \[Unlocked: {unlocked_items}]"
            db_line_2 = f"[bold blue]DL Status:[/bold blue] \[DL'd: {db_dl}] \[Missing: {db_miss}] \[Unique Missing: {unique_to_download}]"
            self.query_one("#db_info_bar").update(f"{db_line_1}\n{db_line_2}")

            # Update Column 2 (Full View)
            view_str = f"[bold blue]View:[/bold blue]   \[Page: {page}] \[Per Page: {num_page}] \[Sort: {clean_sort_name} ({sort_dir})]"
            filt_str = f"[bold blue]Filter:[/bold blue] \[Total: {filtered_items}] \[Unique: {unique_items}]"
            type_str = f"[bold blue]Media:[/bold blue]  \[Vids: {vids}] \[Pics: {pics}] \[Aud: {auds}]"

            # If everything is filtered out, append the warning
            if filtered_items == 0:
                self.query_one("#view_info_bar").update(
                    f"{view_str}\n{filt_str}\n{type_str}\n[bold red]All Items Filtered Out[/bold red]"
                )
            else:
                self.query_one("#view_info_bar").update(
                    f"{view_str}\n{filt_str}\n{type_str}"
                )
        except:
            pass

    def update_cart_info(self):
        in_cart = sum(1 for row in self.table_data if row["download_cart"] == "[added]")
        downloading = sum(
            1 for row in self.table_data if row["download_cart"] == "[downloading]"
        )

        try:
            # Column 1 (Bottom Half)
            cart_line = f"[bold blue]Cart:[/bold blue]      \[Queued: {in_cart}] \[Active: {downloading}]"
            self.query_one("#global_cart_info").update(f"{cart_line}")
        except:
            pass

    @property
    def table(self):
        return self.query_one("#data_table")


app = InputApp()
