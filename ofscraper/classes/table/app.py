import logging
import queue
import re
import arrow
from rich.text import Text
from textual import events
from textual.app import App
from textual.binding import Binding
from textual.widgets import Button, ContentSwitcher, Checkbox, Input, SelectionList
from ofscraper.classes.table.utils.names import get_col_names, get_input_names, get_post_col_names, PINNED_COLUMNS, EXTRA_COLUMNS, POST_EXTRA_COLUMNS
from ofscraper.classes.table.utils.lock import mutex
from ofscraper.classes.table.sections.table import get_styled, get_post_styled
from ofscraper.classes.table.css import CSS
from ofscraper.classes.table.const import AMOUNT_PER_PAGE
from ofscraper.classes.table.compose import composer
from ofscraper.commands.scraper.actions.download import stop
import ofscraper.classes.table.utils.open_folder as open_folder
import ofscraper.utils.logs.logger as logger
import ofscraper.utils.settings as settings
import ofscraper.utils.console as console_
import ofscraper.utils.cache.cache as cache

log = logging.getLogger("shared")
app = None
row_queue = queue.Queue()
EXTRA_COLUMNS_CACHE_KEY = "check_table_show_extra_columns"
MEDIA_COLS_CACHE_KEY = "check_table_visible_media_cols"
POST_COLS_CACHE_KEY = "check_table_visible_post_cols"


class InputApp(App):
    BINDINGS = [
        # priority, so a focused Input (which binds ctrl+d) doesn't take them
        Binding("ctrl+s", "toggle_options_sidebar", priority=True),
        Binding("ctrl+d", "toggle_download_sidebar", priority=True),
        ("a", "select_current_page", "Add Page"),
        ("A", "select_all_filtered", "Add All Filtered"),
        ("u", "select_unique_current_page", "Add Unique Page"),
        ("U", "select_unique_all_filtered", "Add All Unique"),
        ("e", "select_page_undownloaded", "Add Page New"),
        ("E", "select_all_undownloaded", "Add All New"),
        ("c", "clear_current_page", "Clear Page"),
        ("C", "clear_all_filtered", "Clear All Filtered"),
        ("x", "clear_entire_cart", "Nuke Cart"),
        Binding("ctrl+x", "stop_downloads", "Stop Downloads", priority=True),
        ("o", "open_download_folder", "Open Folder"),
        ("h", "toggle_extra_columns", "Show/Hide Columns"),
        ("v", "open_columns_tab", "Columns"),
        ("f", "inspect_post_media", "Inspect Post Media"),
    ]
    CSS = CSS

    def __init__(self, *args, **kwargs) -> None:
        self.sidebar = None
        self._filtered_rows = []
        self.post_data = []
        self._filtered_post_rows = []
        self.show_extra_columns = False
        self.visible_media_cols = list(get_col_names(show_extra=False))
        self.visible_post_cols = list(get_post_col_names(show_extra=False))
        self._prev_tab = "table"

        # Dedicated Pagination State
        self.main_page = 1
        self.post_page = 1
        self.cart_page = 1
        self._post_sortkey = "number"
        self._post_reverse = False

        super().__init__(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        self.table_data = kwargs.pop("table_data", [])
        self.post_data = kwargs.pop("post_data", [])
        self._sortkey = None
        self._reverse = False
        self._post_sortkey = "number"
        self._post_reverse = False
        self.run()

    def compose(self):
        try:
            return composer()
        except Exception:
            pass

    def on_ready(self) -> None:
        try:
            self.show_extra_columns = (
                cache.get(EXTRA_COLUMNS_CACHE_KEY, default=False) is True
            )
        except Exception:
            self.show_extra_columns = False
        self._load_column_preferences()
        self.visible_media_cols = list(get_col_names(show_extra=False))
        self.visible_post_cols = list(get_post_col_names(show_extra=False))
        self._prev_tab = "table"
        self._load_column_preferences()
        self.init_table()
        self.init_post_table()
        self.init_cart_table()
        self.init_cart_toggles()
        self.update_toggle_labels()
        self.set_active_tab("table")
        self.query_one("#main_per_page_input").value = str(AMOUNT_PER_PAGE)
        self.query_one("#post_per_page_input").value = str(AMOUNT_PER_PAGE)
        self.query_one("#cart_per_page_input").value = str(AMOUNT_PER_PAGE)
        logger.add_widget(self.query_one("#console_page_log"))
        console_.get_shared_console().quiet = True

    # --- UI Events ---
    def on_data_table_header_selected(self, event):
        clean_label = event.label.plain.replace(" ▼", "").replace(" ▲", "")
        key = re.sub(" ", "_", clean_label).lower()
        table_id = event.control.id
        if key == "download_cart":
            if table_id == "media_table":
                self.action_select_current_page()
            elif table_id == "post_table":
                self.action_select_current_page()
            elif table_id == "cart_data_table":
                self.action_clear_current_page()
        else:
            if table_id == "post_table":
                self.update_post_table_sort(key)
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
        coordinate = event.coordinate

        # Enter (or a click) on the Number cell adds or removes the row like
        # the Download cell does
        if col_name == "number" and "download_cart" in table.ordered_columns_keys:
            col_name = "download_cart"
            coordinate = coordinate._replace(
                column=table.ordered_columns_keys.index("download_cart")
            )

        if col_name == "download_cart":
            if table.id == "media_table":
                for row in self._filtered_rows:
                    if str(row["index"]) == row_key:
                        # Prevent manually clicking locked or unknown media
                        if row.get("download_type") == "unknown" or not row.get(
                            "unlocked"
                        ):
                            break

                        current = row["download_cart"]
                        if current in {
                            "[]",
                            "[downloaded]",
                            "[failed]",
                            "[stopped]",
                            "[skipped]",
                        }:
                            row["download_cart"] = "[added]"
                        elif current == "[added]":
                            row["download_cart"] = "[]"

                        styled_text = Text(
                            row["download_cart"], style="bold light_goldenrod2"
                        )
                        table.update_cell_at_coord(coordinate, styled_text)
                        break
                self.update_cart_info()

            elif table.id == "post_table":
                for prow in self._filtered_post_rows:
                    if str(prow["index"]) == row_key:
                        self._toggle_post_in_cart(prow)
                        break
                self.set_post_page()
                self.set_page()
                self.update_cart_info()

            elif table.id == "cart_data_table":
                self.update_cell_state(row_key, "[]", "bold light_goldenrod2")
                self.update_cart_table()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        # Tabs
        if btn_id in ["console", "table", "post_tab", "cart", "columns_tab"]:
            if btn_id != "columns_tab":
                self._prev_tab = btn_id
            if btn_id == "cart":
                self.update_cart_table()
            elif btn_id == "post_tab":
                self.sync_post_cart_states()
                self.set_post_page()
                self.update_post_search_info()
            elif btn_id == "columns_tab":
                self._sync_column_selectors()
            page_map = {
                "table": "media_table_page",
                "post_tab": "post_table_page",
                "cart": "cart_page",
                "console": "console_page",
                "columns_tab": "columns_page",
            }
            self.query_one(ContentSwitcher).current = page_map[btn_id]
            self.set_active_tab(btn_id)
        elif btn_id in ["open_columns_main", "open_columns_post"]:
            self.action_open_columns_tab()
        elif btn_id == "apply_columns":
            self._apply_columns_from_ui(return_to_prev=True, save=False)
        elif btn_id == "save_default_columns":
            self._save_columns_as_default()
        elif btn_id == "toggle_post_audio_cols":
            self._toggle_post_audio_columns()
        elif btn_id == "select_all_columns":
            self._select_all_columns_ui()
        elif btn_id == "reset_columns":
            self._reset_columns_ui()

        # Top level controls
        # Clear Filters in the options sidebar; the sidebar stays open
        elif btn_id in ["reset", "clear_filters"]:
            self.reset_table()
        elif btn_id in ["reset_post", "post_clear_filters"]:
            self.reset_post_table()
        elif btn_id in ["send_downloads", "send_downloads_main", "send_downloads_post"]:
            log.info("Adding Downloads to queue")
            self.add_to_row_queue()
            self.query_one(ContentSwitcher).current = "console_page"
        elif btn_id == "stop_downloads":
            self.action_stop_downloads()
        elif btn_id in ["open_download_folder", "open_download_folder_post"]:
            self.open_creator_folder()

        # Filter triggers
        elif btn_id in ["filter", "filter2"]:
            sidebar = self.query_one("#options_sidebar")
            sidebar.toggle_hidden()
            self.focus_table_if_hidden_in(sidebar)
            self.filter_table()
            self.update_toggle_labels()
        elif btn_id in ["post_filter", "post_filter2"]:
            sidebar = self.query_one("#post_options_sidebar")
            sidebar.toggle_hidden()
            self.focus_table_if_hidden_in(sidebar)
            self.filter_post_table()
            self.update_toggle_labels()

        # Pagination Logic
        elif btn_id in ["main_first", "main_prev", "main_next", "main_last", "main_go"]:
            self.handle_pagination("main", btn_id)
        elif btn_id in ["post_first", "post_prev", "post_next", "post_last", "post_go"]:
            self.handle_pagination("post", btn_id)
        elif btn_id in ["cart_first", "cart_prev", "cart_next", "cart_last", "cart_go"]:
            self.handle_pagination("cart", btn_id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Allows user to hit Enter in the pagination boxes instead of clicking Go"""
        input_id = event.input.id
        if input_id in ["main_page_input", "main_per_page_input"]:
            self.handle_pagination("main", "main_go")
        elif input_id in ["post_page_input", "post_per_page_input"]:
            self.handle_pagination("post", "post_go")
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

    def _normalize_col_list(self, cols, all_cols):
        chosen = set(cols or [])
        out = [c for c in PINNED_COLUMNS if c in all_cols]
        for c in all_cols:
            if c not in PINNED_COLUMNS and c in chosen:
                out.append(c)
        return out

    def _load_column_preferences(self) -> None:
        all_media = list(get_col_names(show_extra=True))
        all_post = list(get_post_col_names(show_extra=True))
        saved_media = None
        saved_post = None
        try:
            saved_media = cache.get(MEDIA_COLS_CACHE_KEY, default=None)
            saved_post = cache.get(POST_COLS_CACHE_KEY, default=None)
        except Exception:
            pass
        if isinstance(saved_media, (list, tuple, set)):
            self.visible_media_cols = self._normalize_col_list(saved_media, all_media)
        else:
            self.visible_media_cols = list(get_col_names(show_extra=self.show_extra_columns))
        if isinstance(saved_post, (list, tuple, set)):
            self.visible_post_cols = self._normalize_col_list(saved_post, all_post)
        else:
            # Audio columns are always excluded by default
            self.visible_post_cols = list(get_post_col_names(show_extra=False))
        self._sync_column_selectors()

    def _save_column_preferences(self) -> None:
        try:
            cache.set(MEDIA_COLS_CACHE_KEY, list(self.visible_media_cols))
            cache.set(POST_COLS_CACHE_KEY, list(self.visible_post_cols))
        except Exception:
            pass

    def _sync_column_selectors(self) -> None:
        try:
            m_sel = self.query_one("#media_columns_list", SelectionList)
            m_sel.deselect_all()
            for col in self.visible_media_cols:
                if col not in PINNED_COLUMNS:
                    m_sel.select(col)
            p_sel = self.query_one("#post_columns_list", SelectionList)
            p_sel.deselect_all()
            for col in self.visible_post_cols:
                if col not in PINNED_COLUMNS:
                    p_sel.select(col)
        except Exception:
            pass

    def _rebuild_all_tables_for_columns(self) -> None:
        self._insert_visible_table()
        self._insert_post_visible_table()
        self._insert_visible_table(self.query_one("#cart_data_table"))
        self.set_page()
        self.set_post_page()
        self.update_cart_table()

    def _apply_columns_from_ui(self, return_to_prev: bool = False, save: bool = False) -> None:
        all_media = list(get_col_names(show_extra=True))
        all_post = list(get_post_col_names(show_extra=True))
        m_sel = self.query_one("#media_columns_list", SelectionList)
        p_sel = self.query_one("#post_columns_list", SelectionList)
        self.visible_media_cols = self._normalize_col_list(m_sel.selected, all_media)
        self.visible_post_cols = self._normalize_col_list(p_sel.selected, all_post)
        if save:
            self._save_column_preferences()
        self._rebuild_all_tables_for_columns()
        if return_to_prev:
            target = self._prev_tab if self._prev_tab in {"table", "post_tab", "cart", "console"} else "table"
            page_map = {
                "table": "media_table_page",
                "post_tab": "post_table_page",
                "cart": "cart_page",
                "console": "console_page",
            }
            self.query_one(ContentSwitcher).current = page_map[target]
            self.set_active_tab(target)

    def _save_columns_as_default(self) -> None:
        self._apply_columns_from_ui(return_to_prev=False, save=True)
        self.notify("Column visibility saved as default")

    def _toggle_post_audio_columns(self) -> None:
        p_sel = self.query_one("#post_columns_list", SelectionList)
        current = set(p_sel.selected)
        if POST_EXTRA_COLUMNS <= current:
            for col in POST_EXTRA_COLUMNS:
                p_sel.deselect(col)
        else:
            for col in POST_EXTRA_COLUMNS:
                p_sel.select(col)
        self._apply_columns_from_ui(return_to_prev=False)

    def _select_all_columns_ui(self) -> None:
        self.query_one("#media_columns_list", SelectionList).select_all()
        self.query_one("#post_columns_list", SelectionList).select_all()
        self._apply_columns_from_ui(return_to_prev=False)

    def _reset_columns_ui(self) -> None:
        self.show_extra_columns = False
        try:
            cache.set(EXTRA_COLUMNS_CACHE_KEY, False)
            cache.set(MEDIA_COLS_CACHE_KEY, None)
            cache.set(POST_COLS_CACHE_KEY, None)
        except Exception:
            pass
        all_media = list(get_col_names(show_extra=True))
        all_post = list(get_post_col_names(show_extra=True))
        self.visible_media_cols = self._normalize_col_list(
            [c for c in all_media if c not in EXTRA_COLUMNS], all_media
        )
        self.visible_post_cols = self._normalize_col_list(
            [c for c in all_post if c not in POST_EXTRA_COLUMNS], all_post
        )
        self._sync_column_selectors()
        self._rebuild_all_tables_for_columns()
        self.notify("Column visibility reset to defaults")

    def action_open_columns_tab(self) -> None:
        if self.is_sidebar_open:
            return
        current_page = self.query_one(ContentSwitcher).current
        if current_page == "columns_page":
            self._apply_columns_from_ui(return_to_prev=True)
        else:
            reverse_map = {
                "media_table_page": "table",
                "post_table_page": "post_tab",
                "cart_page": "cart",
                "console_page": "console",
            }
            self._prev_tab = reverse_map.get(current_page, "table")
            self._sync_column_selectors()
            self.query_one(ContentSwitcher).current = "columns_page"
            self.set_active_tab("columns_tab")

    def action_toggle_extra_columns(self) -> None:
        if self.is_sidebar_open:
            return
        self.show_extra_columns = not self.show_extra_columns
        try:
            cache.set(EXTRA_COLUMNS_CACHE_KEY, self.show_extra_columns)
        except Exception:
            pass
        all_media = list(get_col_names(show_extra=True))
        current_media = set(self.visible_media_cols)
        if self.show_extra_columns:
            current_media |= EXTRA_COLUMNS
        else:
            current_media -= EXTRA_COLUMNS
        self.visible_media_cols = self._normalize_col_list(current_media, all_media)
        self._sync_column_selectors()
        self._rebuild_all_tables_for_columns()

    # --- Sidebars Actions ---
    def action_toggle_options_sidebar(self) -> None:
        active = self.query_one(ContentSwitcher).current
        if active == "media_table_page":
            target_id = "options_sidebar"
        elif active == "post_table_page":
            target_id = "post_options_sidebar"
        else:
            return
        for ele in filter(
            lambda x: x.id != target_id, self.query("Sidebar.-show")
        ):
            ele.toggle_hidden()
            self.focus_table_if_hidden_in(ele)
        sidebar = self.query_one(f"#{target_id}")
        sidebar.toggle_hidden()
        self.focus_table_if_hidden_in(sidebar)
        self.update_toggle_labels()

    def action_toggle_download_sidebar(self) -> None:
        if self.query_one(ContentSwitcher).current != "media_table_page":
            return
        for ele in filter(
            lambda x: x.id != "download_option_sidebar", self.query("Sidebar.-show")
        ):
            ele.toggle_hidden()
            self.focus_table_if_hidden_in(ele)
        sidebar = self.query_one("#download_option_sidebar")
        sidebar.toggle_hidden()
        self.focus_table_if_hidden_in(sidebar)
        self.update_toggle_labels()

    def focus_table_if_hidden_in(self, sidebar) -> None:
        """Focus the table if the sidebar is hidden and has the focus.

        Textual moves focus off a hidden widget to one of its siblings, which
        are hidden too, so keys went to filter boxes no one could see.
        """
        focused = self.focused
        if (
            sidebar.has_class("-hidden")
            and focused is not None
            and sidebar in focused.ancestors
        ):
            active = self.query_one(ContentSwitcher).current
            self.set_focus(self.post_table if active == "post_table_page" else self.table)

    def update_toggle_labels(self) -> None:
        try:
            opt_open = self.query_one("#options_sidebar").has_class("-show")
            dl_open = self.query_one("#download_option_sidebar").has_class("-show")

            self.query_one("#label_opt_sidebar").update(
                f"Options Menu:  [bold ansi_cyan]Ctrl+S[/bold ansi_cyan] [bold]({'Open' if opt_open else 'Closed'})[/bold]"
            )
            self.query_one("#label_dl_sidebar").update(
                f"Download Menu: [bold ansi_cyan]Ctrl+D[/bold ansi_cyan] [bold]({'Open' if dl_open else 'Closed'})[/bold]"
            )
            post_opt_open = self.query_one("#post_options_sidebar").has_class("-show")
            self.query_one("#label_post_opt_sidebar").update(
                f"Post Filters: [bold ansi_cyan]Ctrl+S[/bold ansi_cyan] [bold]({'Open' if post_opt_open else 'Closed'})[/bold]"
            )
        except:
            pass

    def set_active_tab(self, active_btn_id: str):
        """Highlights the active tab button using Textual's native variants."""
        for btn_id in ["table", "post_tab", "cart", "console", "columns_tab"]:
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
            self.query_one(f"#{prefix}_first").display = current_page > 1
            self.query_one(f"#{prefix}_prev").display = current_page > 1

            # We use < total_pages so they vanish when you hit the last page.
            self.query_one(f"#{prefix}_next").display = current_page < total_pages
            self.query_one(f"#{prefix}_last").display = current_page < total_pages
        except Exception as e:
            log.debug(f"Error updating pagination buttons: {e}")

    def handle_pagination(self, prefix, btn_id):
        # 1. Select the correct data source based on tab
        if prefix == "main":
            rows = self._filtered_rows
        elif prefix == "post":
            rows = self._filtered_post_rows
        else:
            rows = [r for r in self.table_data if r.get("download_cart") == "[added]"]

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
        current_page = self.main_page if prefix == "main" else (self.post_page if prefix == "post" else self.cart_page)

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
                target_node.value = ""  # Clear the jump box after action

        # 5. Apply Changes
        current_page = min(total_pages, max(1, current_page))
        if prefix == "main":
            self.main_page = current_page
            self.set_page()
        elif prefix == "post":
            self.post_page = current_page
            self.set_post_page()
            self.update_post_search_info()
        else:
            self.cart_page = current_page
            self.update_cart_table()

    # ==========================================
    # --- Cart: Add Actions (Additive Only) ---
    # ==========================================
    def action_select_current_page(self) -> None:
        if self.is_sidebar_open:
            return
        active = self.query_one(ContentSwitcher).current
        if active == "media_table_page":
            num_page = int(self.query_one("#main_per_page_input").value or AMOUNT_PER_PAGE)
            start = (self.main_page - 1) * num_page
            self._add_items_to_cart(self._filtered_rows[start : start + num_page])
        elif active == "post_table_page":
            num_page = int(self.query_one("#post_per_page_input").value or AMOUNT_PER_PAGE)
            start = (self.post_page - 1) * num_page
            self._add_posts_to_cart(self._filtered_post_rows[start : start + num_page], new_only=False)

    def action_select_all_filtered(self) -> None:
        if self.is_sidebar_open:
            return
        active = self.query_one(ContentSwitcher).current
        if active == "media_table_page":
            self._add_items_to_cart(self._filtered_rows)
        elif active == "post_table_page":
            self._add_posts_to_cart(self._filtered_post_rows, new_only=False)

    def _add_items_to_cart(self, rows_to_evaluate: list):
        if not rows_to_evaluate:
            return
        for row in rows_to_evaluate:
            # Skip locked or unknown media
            if row.get("download_type") == "unknown" or not row.get("unlocked"):
                continue
            if row["download_cart"] in {
                "[]",
                "[downloaded]",
                "[failed]",
                "[stopped]",
                "[skipped]",
            }:
                row["download_cart"] = "[added]"
        self.set_page()
        self.update_cart_info()

    def action_select_unique_current_page(self) -> None:
        if (
            self.is_sidebar_open
            or self.query_one(ContentSwitcher).current != "media_table_page"
        ):
            return
        num_page = int(self.query_one("#main_per_page_input").value or AMOUNT_PER_PAGE)
        start = (self.main_page - 1) * num_page
        self._run_unique_selection(self._filtered_rows[start : start + num_page])

    def action_select_unique_all_filtered(self) -> None:
        if (
            self.is_sidebar_open
            or self.query_one(ContentSwitcher).current != "media_table_page"
        ):
            return
        self._run_unique_selection(self._filtered_rows)

    def _run_unique_selection(self, rows_to_evaluate: list):
        if not rows_to_evaluate:
            return
        eligible = [
            r
            for r in rows_to_evaluate
            if r["download_cart"] in {"[]", "[downloaded]", "[failed]", "[stopped]", "[skipped]"}
            and r.get("download_type") != "unknown"
            and r.get("unlocked")
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

    def action_select_page_undownloaded(self) -> None:
        if self.is_sidebar_open:
            return
        active = self.query_one(ContentSwitcher).current
        if active == "media_table_page":
            num_page = int(self.query_one("#main_per_page_input").value or AMOUNT_PER_PAGE)
            start = (self.main_page - 1) * num_page
            for row in self._filtered_rows[start : start + num_page]:
                if row.get("download_type") == "unknown" or not row.get("unlocked"):
                    continue
                if not row["downloaded"] and row["download_cart"] in {
                    "[]",
                    "[failed]",
                    "[stopped]",
                    "[skipped]",
                }:
                    row["download_cart"] = "[added]"
            self.set_page()
            self.update_cart_info()
        elif active == "post_table_page":
            num_page = int(self.query_one("#post_per_page_input").value or AMOUNT_PER_PAGE)
            start = (self.post_page - 1) * num_page
            self._add_posts_to_cart(self._filtered_post_rows[start : start + num_page], new_only=True)

    def action_select_all_undownloaded(self) -> None:
        if self.is_sidebar_open:
            return
        active = self.query_one(ContentSwitcher).current
        if active == "media_table_page":
            for row in self._filtered_rows:
                if row.get("download_type") == "unknown" or not row.get("unlocked"):
                    continue
                if not row["downloaded"] and row["download_cart"] in {
                    "[]",
                    "[failed]",
                    "[stopped]",
                    "[skipped]",
                }:
                    row["download_cart"] = "[added]"
            self.set_page()
            self.update_cart_info()
        elif active == "post_table_page":
            self._add_posts_to_cart(self._filtered_post_rows, new_only=True)

    # ==========================================
    # --- Cart: Clear Actions ---
    # ==========================================
    def action_clear_current_page(self) -> None:
        if self.is_sidebar_open:
            return
        active_tab = self.query_one(ContentSwitcher).current
        if active_tab == "media_table_page":
            num_page = int(
                self.query_one("#main_per_page_input").value or AMOUNT_PER_PAGE
            )
            start = (self.main_page - 1) * num_page
            for row in self._filtered_rows[start : start + num_page]:
                if row["download_cart"] == "[added]":
                    row["download_cart"] = "[]"

        elif active_tab == "post_table_page":
            num_page = int(self.query_one("#post_per_page_input").value or AMOUNT_PER_PAGE)
            start = (self.post_page - 1) * num_page
            self._clear_posts_from_cart(self._filtered_post_rows[start : start + num_page])

        elif active_tab == "cart_page":
            cart_rows = [
                row for row in self.table_data if row.get("download_cart") == "[added]"
            ]
            num_page = int(
                self.query_one("#cart_per_page_input").value or AMOUNT_PER_PAGE
            )
            start = (self.cart_page - 1) * num_page
            for row in cart_rows[start : start + num_page]:
                row["download_cart"] = "[]"

        self.set_page()
        self.sync_post_cart_states()
        self.set_post_page()
        self.update_cart_table()
        self.update_cart_info()

    def action_clear_all_filtered(self) -> None:
        if self.is_sidebar_open:
            return
        active_tab = self.query_one(ContentSwitcher).current
        if active_tab == "media_table_page":
            for row in self._filtered_rows:
                if row["download_cart"] == "[added]":
                    row["download_cart"] = "[]"
            self.set_page()
            self.update_cart_table()
            self.update_cart_info()
        elif active_tab == "post_table_page":
            self._clear_posts_from_cart(self._filtered_post_rows)
        elif active_tab == "cart_page":
            self.action_clear_entire_cart()  # Shift+C on the cart page nukes the cart

    def action_clear_entire_cart(self) -> None:
        """Nukes everything currently marked as [added] in the global table."""
        if self.is_sidebar_open:
            return
        for row in self.table_data:
            if row["download_cart"] == "[added]":
                row["download_cart"] = "[]"

        self.set_page()
        self.sync_post_cart_states()
        self.set_post_page()
        self.update_cart_table()
        self.update_cart_info()

    # ==========================================
    # --- Open the Download Folder (#424) ---
    # ==========================================
    def highlighted_row(self):
        """The table_data row under the main table's cursor, or None."""
        table = self.table
        if table.row_count == 0:
            return None
        try:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        except Exception:
            return None
        return next(
            (row for row in self.table_data if str(row["index"]) == str(key)), None
        )

    def _button_creator(self):
        """The highlighted row's creator, else the table's only creator."""
        row = self.highlighted_row()
        if row is not None:
            return row.get("username")
        names = {row.get("username") for row in self.table_data}
        return names.pop() if len(names) == 1 else None

    def action_open_download_folder(self) -> None:
        if (
            self.is_sidebar_open
            or self.query_one(ContentSwitcher).current != "media_table_page"
        ):
            return
        self._open_target(lambda: open_folder.row_target(self.highlighted_row()))

    def open_creator_folder(self) -> None:
        self._open_target(
            lambda: open_folder.creator_target(self._button_creator())
        )

    def _open_target(self, get_target) -> None:
        """Open a folder; a notice with the path when that can't be done,
        never an error."""
        try:
            target = get_target()
        except Exception as E:
            log.debug(f"Couldn't work out the download folder: {E!r}")
            self.notify(
                f"Couldn't work out the download folder: {E}",
                title="Open Download Folder",
                severity="warning",
                markup=False,
            )
            return
        try:
            open_folder.open_target(target)
        except Exception as E:
            reason = str(E) or type(E).__name__
            log.debug(f"Couldn't open {target.folder}: {E!r}")
            self.notify(
                f"{reason}: {target.folder}",
                title="Open Download Folder",
                severity="warning",
                markup=False,
            )
            return
        if target.note:
            self.notify(
                f"{target.note}: {target.folder}",
                title="Open Download Folder",
                markup=False,
            )

    # --- Rest of Table Logic ---
    def action_stop_downloads(self):
        stop.request()
        while True:
            try:
                key, row = row_queue.get_nowait()
            except queue.Empty:
                break
            self.update_cell_state(key, "[added]", "bold light_goldenrod2")
        self.update_cart_table()
        log.info("Stopping downloads; Part files are kept for Resume.")
        # An idle Stop must not prevent sending a new cart.
        from ofscraper.commands.check import downloads_pending

        if not downloads_pending():
            stop.clear()

    def add_to_row_queue(self):
        if stop.requested.is_set():
            self.notify("Downloads are stopping. Send again when they have stopped.")
            return
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
        downloaded = None
        for row in self.table_data:
            if str(row["index"]) == str(row_key):
                row["download_cart"] = new_state
                # A skip (size limits or a script) isn't recorded as
                # downloaded in the database (#326), so it isn't here either
                if new_state == "[downloaded]":
                    row["downloaded"] = True
                downloaded = row["downloaded"]
                break

        try:
            self.table.update_cell_at_key(
                str(row_key), "download_cart", Text(new_state, style=style)
            )
            # Redraw Downloaded too, styled as get_styled does, so it doesn't
            # wait for the next page redraw (#358)
            if downloaded is not None:
                self.table.update_cell_at_key(
                    str(row_key),
                    "downloaded",
                    Text(str(downloaded), style="bold plum1"),
                )
        except Exception:
            pass

        try:
            self.update_cart_info()
            self.update_search_info()
        except Exception:
            # the table can close while downloads sent from it finish (#425)
            pass

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
                    sort_val = (
                        0 if str(raw_val).lower() == "free" else float(raw_val or 0)
                    )
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
                    filter_rows2 = [
                        row
                        for row in filter_rows
                        if filter_node.compare(str(row.get(name, "")))
                    ]
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
            cart_rows = [
                row for row in self.table_data if row.get("download_cart") == "[added]"
            ]

            # 2. Get the current "Per Page" value safely
            per_page_val = self.query_one("#cart_per_page_input").value
            num_page = (
                int(per_page_val)
                if per_page_val and str(per_page_val).isnumeric()
                else AMOUNT_PER_PAGE
            )

            # 3. Calculate pagination boundaries
            total_pages = max((len(cart_rows) + num_page - 1) // num_page, 1)

            # Boundary correction if items were removed and the current page no longer exists
            if self.cart_page > total_pages:
                self.cart_page = total_pages

            start = (self.cart_page - 1) * num_page

            # 4. Add the rows to the table
            for count, row_dict in enumerate(cart_rows[start : start + num_page]):
                styled_row = get_styled(row_dict, cart_table.ordered_columns_keys)
                key = str(row_dict["index"])
                cart_table.add_row(
                    *styled_row, height=None, key=key, label=str(start + count + 1)
                )

            # 5. Update the UI text and disable/enable buttons dynamically
            self.query_one("#cart_page_label").update(
                f"Page {self.cart_page} of {total_pages}"
            )
            self.update_pagination_btns("cart", self.cart_page, total_pages)

        except Exception as e:
            log.debug(f"Error updating cart table: {e}")

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
        self.main_page = 1
        self.set_page()
        self.update_search_info()

    def update_table_sort(self, key):
        self.set_sort(key)
        active_tab = self.query_one(ContentSwitcher).current
        if active_tab == "media_table_page":
            self._insert_visible_table(self.query_one("#media_table"))
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
            num_page = (
                int(per_page_val)
                if per_page_val and str(per_page_val).isnumeric()
                else AMOUNT_PER_PAGE
            )

            # 2. Calculate pagination boundaries
            total_pages = max((len(rows) + num_page - 1) // num_page, 1)

            if self.main_page > total_pages:
                self.main_page = total_pages

            start = (self.main_page - 1) * num_page

            # 3. Add the rows to the table
            for count, row_dict in enumerate(rows[start : start + num_page]):
                styled_row = get_styled(row_dict, self.table.ordered_columns_keys)
                key = str(row_dict["index"])
                self.table.add_row(
                    *styled_row, height=None, key=key, label=str(start + count + 1)
                )

            try:
                self.query_one("#main_page_label").update(
                    f"Page {self.main_page} of {total_pages}"
                )
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

        for ele in self.visible_media_cols:
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

        filtered_items = len(self._filtered_rows)
        unique_items = len(
            set(row.get("media_id") for row in self._filtered_rows if "media_id" in row)
        )

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
            db_line_1 = f"[bold ansi_blue]Database:[/bold ansi_blue]  \\[Total: {total_items}] \\[Unlocked: {unlocked_items}]"
            db_line_2 = f"[bold ansi_blue]DL Status:[/bold ansi_blue] \\[DL'd: {db_dl}] \\[Missing: {db_miss}] \\[Unique Missing: {unique_to_download}]"
            self.query_one("#db_info_bar").update(f"{db_line_1}\n{db_line_2}")

            view_str = f"[bold ansi_blue]View:[/bold ansi_blue]   \\[Page: {self.main_page}] \\[Per Page: {num_page}] \\[Sort: {clean_sort_name} ({sort_dir})]"
            filt_str = f"[bold ansi_blue]Filter:[/bold ansi_blue] \\[Total: {filtered_items}] \\[Unique: {unique_items}]"
            type_str = f"[bold ansi_blue]Media:[/bold ansi_blue]  \\[Vids: {vids}] \\[Pics: {pics}] \\[Aud: {auds}]"

            if filtered_items == 0:
                self.query_one("#view_info_bar").update(
                    f"{view_str}\n{filt_str}\n{type_str}\n[bold ansi_red]All Items Filtered Out[/bold ansi_red]"
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
            cart_line = f"[bold ansi_blue]Cart:[/bold ansi_blue]      \\[Queued: {in_cart}] \\[Active: {downloading}]"
            for widget in self.query(".global_cart_info"):
                widget.update(cart_line)
        except:
            pass

    # ==========================================
    # --- PostTable Methods & Cart Sync ---
    # ==========================================
    def _media_rows_for_post(self, prow: dict) -> list[dict]:
        pid = str(prow.get("post_id"))
        uname = str(prow.get("username") or "").lower()
        return [
            r for r in self.table_data
            if str(r.get("post_id")) == pid and str(r.get("username") or "").lower() == uname
        ]

    def sync_post_cart_states(self) -> None:
        for prow in self.post_data:
            if not prow.get("unlocked"):
                prow["download_cart"] = "Not Unlocked"
                continue
            mrows = self._media_rows_for_post(prow)
            eligible = [r for r in mrows if r.get("unlocked") and r.get("download_type") != "unknown"]
            if not eligible:
                prow["download_cart"] = "Not Unlocked"
                continue
            added = sum(1 for r in eligible if r.get("download_cart") == "[added]")
            downloading = sum(1 for r in eligible if r.get("download_cart") == "[downloading]")
            downloaded = sum(1 for r in eligible if r.get("downloaded"))
            if downloading:
                prow["download_cart"] = "[downloading]"
            elif added > 0:
                prow["download_cart"] = f"[added ({added}/{len(eligible)})]"
            elif downloaded == len(eligible):
                prow["download_cart"] = "[downloaded]"
            else:
                prow["download_cart"] = "[]"

    def _toggle_post_in_cart(self, prow: dict) -> None:
        if not prow.get("unlocked"):
            return
        mrows = self._media_rows_for_post(prow)
        eligible = [r for r in mrows if r.get("unlocked") and r.get("download_type") != "unknown"]
        if not eligible:
            return
        any_added = any(r.get("download_cart") == "[added]" for r in eligible)
        if any_added:
            for r in eligible:
                if r.get("download_cart") == "[added]":
                    r["download_cart"] = "[]"
        else:
            for r in eligible:
                if r.get("download_cart") in {"[]", "[downloaded]", "[failed]", "[stopped]", "[skipped]"}:
                    r["download_cart"] = "[added]"
        self.sync_post_cart_states()

    def _add_posts_to_cart(self, post_rows: list, new_only: bool = False) -> None:
        for prow in post_rows:
            if not prow.get("unlocked"):
                continue
            for r in self._media_rows_for_post(prow):
                if not r.get("unlocked") or r.get("download_type") == "unknown":
                    continue
                if new_only and r.get("downloaded"):
                    continue
                allowed = {"[]", "[failed]", "[stopped]", "[skipped]"} if new_only else {"[]", "[downloaded]", "[failed]", "[stopped]", "[skipped]"}
                if r.get("download_cart") in allowed:
                    r["download_cart"] = "[added]"
        self.sync_post_cart_states()
        self.set_post_page()
        self.set_page()
        self.update_cart_info()

    def _clear_posts_from_cart(self, post_rows: list) -> None:
        for prow in post_rows:
            for r in self._media_rows_for_post(prow):
                if r.get("download_cart") == "[added]":
                    r["download_cart"] = "[]"
        self.sync_post_cart_states()
        self.set_post_page()
        self.set_page()
        self.update_cart_table()
        self.update_cart_info()

    def action_inspect_post_media(self) -> None:
        if self.is_sidebar_open or self.query_one(ContentSwitcher).current != "post_table_page":
            return
        ptable = self.post_table
        if ptable.row_count == 0:
            return
        try:
            key = ptable.coordinate_to_cell_key(ptable.cursor_coordinate).row_key.value
        except Exception:
            return
        prow = next((r for r in self.post_data if str(r["index"]) == str(key)), None)
        if not prow:
            return
        self.query_one("#post_id").update_table_val(str(prow["post_id"]))
        self.filter_table()
        self.query_one(ContentSwitcher).current = "media_table_page"
        self.set_active_tab("table")

    def init_post_table(self) -> None:
        self._insert_post_visible_table()
        self.sync_post_cart_states()
        self._post_sort_runner(self._post_sortkey)
        self._post_filter_runner()
        self.set_post_page()
        self.update_post_search_info()

    def _insert_post_visible_table(self) -> None:
        table = self.post_table
        table.clear(True)
        table.fixed_rows = 0
        table.zebra_stripes = True
        for ele in self.visible_post_cols:
            base_label = re.sub("_", " ", ele).title()
            width = 45 if ele == "text" else max(16, len(base_label) + 4)
            if str(ele) == self._post_sortkey:
                arrow_char = " ▼" if self._post_reverse else " ▲"
                label = f"{base_label}{arrow_char}"
            else:
                label = base_label
            table.add_column(label, key=str(ele), width=width)

    def update_post_table_sort(self, key: str) -> None:
        with mutex:
            if self._post_sortkey == key:
                self._post_reverse = not self._post_reverse
            else:
                self._post_sortkey = key
                self._post_reverse = False
            self._post_sort_runner(key)
        self._insert_post_visible_table()
        self._post_filter_runner()
        self.set_post_page()
        self.update_post_search_info()

    def _post_sort_runner(self, key: str) -> None:
        sort_attr = f"_sort_{key}"
        def sort_key_func(x):
            if sort_attr in x:
                val = x[sort_attr]
                is_empty = val == float("inf")
                group = (0 if is_empty else 1) if self._post_reverse else (1 if is_empty else 0)
                return (group, 0 if is_empty else val)
            raw = x.get(key)
            if key == "post_date":
                is_empty = str(raw) == "Probably Deleted"
                group = (0 if is_empty else 1) if self._post_reverse else (1 if is_empty else 0)
                return (group, 0 if is_empty else arrow.get(raw).timestamp())
            if key in {"number", "post_id", "total_media", "new_media", "photos", "new_photos", "videos", "new_videos", "audios", "new_audios", "shared_bundles"}:
                return (0, int(raw or 0))
            return (0, str(raw or ""))
        self.post_data.sort(key=sort_key_func, reverse=self._post_reverse)

    def _post_filter_runner(self) -> None:
        with mutex:
            rows = list(self.post_data)
            checks = [
                ("post_text", lambda r, n: n.compare(str(r.get("text", "")))),
                ("post_post_id", lambda r, n: n.compare(str(r.get("post_id", "")))),
                ("post_price", lambda r, n: n.compare(str(r.get("_sort_total_cost", 0)))),
                ("post_post_date", lambda r, n: True if str(r.get("post_date")) == "Probably Deleted" else n.compare(str(r.get("post_date", "")))),
                ("post_unlocked", lambda r, n: n.compare(str(r.get("unlocked", "")))),
                ("post_responsetype", lambda r, n: n.compare(str(r.get("responsetype", "")))),
                ("post_username", lambda r, n: n.compare(str(r.get("username", "")))),
            ]
            for widget_id, pred in checks:
                try:
                    node = self.query_one(f"#{widget_id}")
                    rows = [r for r in rows if pred(r, node)]
                except Exception:
                    pass
            try:
                min_new_val = self.query_one("#post_min_new_media_input").value
                if min_new_val and str(min_new_val).isnumeric():
                    rows = [r for r in rows if int(r.get("new_media", 0)) >= int(min_new_val)]
            except Exception:
                pass
            try:
                mfield = self.query_one("#post_mediatype")
                rows = [r for r in rows if mfield.compare(r.get("_mediatypes", set()))]
            except Exception:
                pass
            self._filtered_post_rows = rows

    def filter_post_table(self) -> None:
        self._post_filter_runner()
        self.post_page = 1
        self.set_post_page()
        self.update_post_search_info()

    def reset_post_table(self) -> None:
        for wid in ("post_text", "post_post_id", "post_min_new_media", "post_price", "post_post_date", "post_unlocked", "post_mediatype", "post_responsetype", "post_username"):
            try:
                self.query_one(f"#{wid}").reset()
            except Exception:
                pass
        self._post_sortkey = "number"
        self._post_reverse = False
        self._post_sort_runner("number")
        self._insert_post_visible_table()
        self._post_filter_runner()
        self.post_page = 1
        self.set_post_page()
        self.update_post_search_info()

    def set_post_page(self) -> None:
        with mutex:
            table = self.post_table
            table.clear()
            rows = self._filtered_post_rows
            per_page_val = self.query_one("#post_per_page_input").value
            num_page = int(per_page_val) if per_page_val and str(per_page_val).isnumeric() else AMOUNT_PER_PAGE
            total_pages = max((len(rows) + num_page - 1) // num_page, 1)
            if self.post_page > total_pages:
                self.post_page = total_pages
            start = (self.post_page - 1) * num_page
            for count, row_dict in enumerate(rows[start : start + num_page]):
                styled_row = get_post_styled(row_dict, table.ordered_columns_keys)
                table.add_row(*styled_row, height=None, key=str(row_dict["index"]), label=str(start + count + 1))
            try:
                self.query_one("#post_page_label").update(f"Page {self.post_page} of {total_pages}")
                self.update_pagination_btns("post", self.post_page, total_pages)
            except Exception:
                pass

    def update_post_search_info(self) -> None:
        try:
            num_page = self.query_one("#post_per_page_input").value or AMOUNT_PER_PAGE
            sort_dir = "Desc" if self._post_reverse else "Asc"
            clean_sort = re.sub("_", " ", self._post_sortkey or "number").title()
            total_posts = len(self.post_data)
            unlocked_posts = sum(1 for r in self.post_data if r.get("unlocked"))
            locked_posts = total_posts - unlocked_posts
            filtered_posts = len(self._filtered_post_rows)
            new_media_total = sum(int(r.get("new_media", 0)) for r in self._filtered_post_rows)
            self.query_one("#post_info_bar").update(
                f"[bold ansi_blue]Posts:[/bold ansi_blue]    \\[Total: {total_posts}] \\[Unlocked: {unlocked_posts}] \\[Locked: {locked_posts}]\n"
                f"[bold ansi_blue]Net New:[/bold ansi_blue]  \\[New Media Across Filtered Posts: {new_media_total}]"
            )
            view_str = f"[bold ansi_blue]View:[/bold ansi_blue]   \\[Page: {self.post_page}] \\[Per Page: {num_page}] \\[Sort: {clean_sort} ({sort_dir})]"
            filt_str = f"[bold ansi_blue]Filter:[/bold ansi_blue] \\[Showing: {filtered_posts} / {total_posts}]"
            self.query_one("#post_view_info_bar").update(
                f"{view_str}\n{filt_str}" + ("\n[bold ansi_red]All Posts Filtered Out[/bold ansi_red]" if filtered_posts == 0 else "")
            )
        except Exception:
            pass

    @property
    def post_table(self):
        return self.query_one("#post_table")

    @property
    def table(self):
        return self.query_one("#media_table")

    @property
    def is_sidebar_open(self) -> bool:
        """Checks if any sidebar is currently visible."""
        try:
            return len(self.query("Sidebar.-show")) > 0
        except Exception:
            return False


app = InputApp()
