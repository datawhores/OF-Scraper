from textual.containers import Container, Horizontal, Vertical
import re
from textual.widgets import Button, ContentSwitcher, Rule, Static, Checkbox, SelectionList, Label
from textual.widgets.selection_list import Selection
from ofscraper.classes.table.utils.names import col_names, post_col_names, PINNED_COLUMNS, EXTRA_COLUMNS, POST_EXTRA_COLUMNS

from ofscraper.classes.table.fields.datefield import DateField
from ofscraper.classes.table.fields.mediafield import MediaField, PostMediaField, PostMediaField
from ofscraper.classes.table.fields.downloadfield import DownloadField
from ofscraper.classes.table.fields.numfield import NumField, PostiveNumField
from ofscraper.classes.table.fields.pricefield import PriceField
from ofscraper.classes.table.fields.responsefield import ResponseField
from ofscraper.classes.table.fields.selectfield import SelectField
from ofscraper.classes.table.fields.textsearch import TextSearch
from ofscraper.classes.table.fields.timefield import TimeField
from ofscraper.classes.table.inputs.strinput import StrInput
from ofscraper.classes.table.inputs.intergerinput import IntegerInput
from ofscraper.classes.table.sections.table_console import OutConsole
from ofscraper.classes.table.sections.sidebar import Sidebar
from ofscraper.classes.table.sections.table import DataTableExtended
from ofscraper.classes.table.fields.sizefield import SizeMaxField, SizeMinField

# a scan doesn't learn file sizes; the download request does
SIZE_LIMIT_NOTE = (
    "Size limits apply when files download, not to the table: a scan doesn't"
    " know file sizes, so no rows are hidden."
)


# Add this helper function above def composer():
def pagination_bar(prefix: str):
    """Reusable pagination row for both Main and Cart pages."""
    with Horizontal(classes="pagination_row"):
        # 1. Navigation Cluster
        yield Button("<<", id=f"{prefix}_first", classes="page_btn")
        yield Button("<", id=f"{prefix}_prev", classes="page_btn")
        yield Static("Page 1 of 1", id=f"{prefix}_page_label", classes="page_label")      
        yield Button(">", id=f"{prefix}_next", classes="page_btn")
        yield Button(">>", id=f"{prefix}_last", classes="page_btn")

        # 2. THE GAP: Explicit spacer between navigation and configuration
        yield Static("", classes="pagination_gap")

        # 3. Action Cluster
        yield Static("Per Page:", classes="mini_label")
        yield IntegerInput(placeholder="100", id=f"{prefix}_per_page_input", classes="page_input")
        yield Static("Page:", classes="mini_label")
        yield IntegerInput(placeholder="Num", id=f"{prefix}_page_input", classes="page_input_small")
        yield Button("Go", id=f"{prefix}_go", classes="page_btn")

def composer():
    with Horizontal(id="tabs_row"):
        yield Button("MediaTable", id="table")
        yield Button("PostTable", id="post_tab")
        yield Button("Cart", id="cart")
        yield Button("Console", id="console")
        yield Button("Columns (v)", id="columns_tab")
        yield Button("Stop Downloads (Ctrl+X)", id="stop_downloads")

    yield Rule()

    with ContentSwitcher(initial="media_table_page"):
        
# ==========================================
        # 1. MAIN DATA TABLE PAGE
        # ==========================================
        with Vertical(id="media_table_page"):
            with Horizontal(classes="header_top_row"):
                # Column 1: DB and Cart Info
                with Vertical(classes="trackers_column"):
                    yield Static("", id="db_info_bar", markup=True)
                    yield Static("", classes="global_cart_info", markup=True)
                yield Rule(orientation="vertical", classes="header_divider")
                
                # Column 2: View & Filter Info (RESTORED!)
                with Vertical(classes="page_info_column"):
                    yield Static("", id="view_info_bar", markup=True)
                yield Rule(orientation="vertical", classes="header_divider")
                
                # Column 3: Toggles
                with Vertical(classes="toggles_column"):
                    yield Static("[bold ansi_blue]Sidebar Controls:[/bold ansi_blue]", markup=True)
                    yield Static("Options Menu:  [bold ansi_cyan]Ctrl+S[/bold ansi_cyan]", id="label_opt_sidebar", markup=True)
                    yield Static("Download Menu: [bold ansi_cyan]Ctrl+D[/bold ansi_cyan]", id="label_dl_sidebar", markup=True)
                yield Rule(orientation="vertical", classes="header_divider")
    
                # Column 4: Instructions
                with Vertical(classes="instructions_column"):
                    yield Static(
                        "[bold ansi_blue]Cart_Add:[/bold ansi_blue] Page (a) | All Filtered ([bold ansi_cyan]Shift+A[/bold ansi_cyan])\n"
                        "[bold ansi_blue]Cart_Unique:[/bold ansi_blue] Page (u) | All Unique ([bold ansi_cyan]Shift+U[/bold ansi_cyan])\n"
                        "[bold ansi_green]Cart_New Only:[/bold ansi_green] Page (e) | All New ([bold ansi_cyan]Shift+E[/bold ansi_cyan])\n"
                        "[bold ansi_red]Clear Cart:[/bold ansi_red] Page (c) | All Filtered ([bold ansi_cyan]Shift+C[/bold ansi_cyan]) | Nuke (x)\n"
                        "[bold ansi_blue]Open Folder:[/bold ansi_blue] Highlighted Row (o) | Extra Cols (h) | Columns (v)",
                        id="table_instructions",
                        markup=True,
                    )
            with Horizontal(id="main_action_row"):
                yield Button(">> Send Downloads to OF-Scraper", id="send_downloads_main")
                yield Button("Open Download Folder", id="open_download_folder")
                yield Button("Reset Filters", id="reset")
                yield Button("Columns (v)", id="open_columns_main")
            
            # Inline Pagination
            with Horizontal(classes="pagination_row"):
                yield from pagination_bar("main")

            with Vertical(id="media_table_main"):
                yield DataTableExtended(id="media_table")

            # Sidebars (Only visible on Main Table)
            with Sidebar(id="download_option_sidebar", classes="-hidden"):
                yield Static("Values change right away", shrink=True, markup=True)
                yield SizeMinField("Download_Size_Min")
                yield SizeMaxField("Download_Size_Max")
                # no markup: "[skipped]" would be read as a style tag
                yield Static(
                    SIZE_LIMIT_NOTE, id="size_limit_note", shrink=True, markup=False
                )

            with Sidebar(id="options_sidebar", classes="-hidden"):
                with Container(id="main_options"):
                    yield Button("Filter", id="filter")
                    yield Button("Clear Filters", id="clear_filters")
                    yield Rule()
                    yield TextSearch("Text")
                    yield Rule()
                    yield NumField("Media_ID")
                    yield NumField("Post_ID")
                    yield Rule()
                    yield NumField("Post_Media_Count")
                    yield Rule()
                    yield PriceField("Price")
                    yield Rule()
                    yield DateField("Post_Date")
                    yield Rule()
                    yield TimeField("Length")
                    yield Rule()
                    yield SelectField("Downloaded")
                    yield SelectField("Unlocked")
                    yield Rule()
                    yield MediaField("Mediatype")
                    yield ResponseField("Responsetype")
                    yield Rule()
                    yield DownloadField("Download_Type")
                    yield Rule()
                    yield Label("Creator Username:")
                    yield StrInput(id="username", placeholder="Username (e.g. creator_name)")
                    yield Rule()
                    yield Button("Filter", id="filter2")


        # ==========================================
        # 2. POST DATA TABLE PAGE
        # ==========================================
        with Vertical(id="post_table_page"):
            with Horizontal(classes="header_top_row"):
                with Vertical(classes="trackers_column"):
                    yield Static("", id="post_info_bar", markup=True)
                    yield Static("", classes="global_cart_info", markup=True)
                yield Rule(orientation="vertical", classes="header_divider")

                with Vertical(classes="page_info_column"):
                    yield Static("", id="post_view_info_bar", markup=True)
                yield Rule(orientation="vertical", classes="header_divider")

                with Vertical(classes="toggles_column"):
                    yield Static("[bold ansi_blue]Sidebar Controls:[/bold ansi_blue]", markup=True)
                    yield Static("Post Filters: [bold ansi_cyan]Ctrl+S[/bold ansi_cyan]", id="label_post_opt_sidebar", markup=True)
                yield Rule(orientation="vertical", classes="header_divider")

                with Vertical(classes="instructions_column"):
                    yield Static(
                        "[bold ansi_blue]Post_Cart_Add:[/bold ansi_blue] Page (a) | All Filtered ([bold ansi_cyan]Shift+A[/bold ansi_cyan])\n"
                        "[bold ansi_green]Post_Cart_New:[/bold ansi_green] Page (e) | All New ([bold ansi_cyan]Shift+E[/bold ansi_cyan])\n"
                        "[bold ansi_red]Clear Cart:[/bold ansi_red] Page (c) | All Filtered ([bold ansi_cyan]Shift+C[/bold ansi_cyan]) | Nuke (x)\n"
                        "[bold ansi_blue]Inspect Media:[/bold ansi_blue] Filter MediaTable by Post (f) | Open Folder (o)",
                        id="post_table_instructions",
                        markup=True,
                    )
            with Horizontal(id="post_action_row"):
                yield Button(">> Send Downloads to OF-Scraper", id="send_downloads_post")
                yield Button("Open Download Folder", id="open_download_folder_post")
                yield Button("Reset Filters", id="reset_post")
                yield Button("Columns (v)", id="open_columns_post")

            with Horizontal(classes="pagination_row"):
                yield from pagination_bar("post")

            with Vertical(id="post_table_main"):
                yield DataTableExtended(id="post_table")

            with Sidebar(id="post_options_sidebar", classes="-hidden"):
                with Container(id="post_options"):
                    yield Button("Filter", id="post_filter")
                    yield Button("Clear Filters", id="post_clear_filters")
                    yield Rule()
                    yield TextSearch("post_text")
                    yield Rule()
                    yield NumField("post_post_id")
                    yield PostiveNumField("post_min_new_media")
                    yield Rule()
                    yield PriceField("post_price")
                    yield Rule()
                    yield DateField("post_post_date")
                    yield Rule()
                    yield SelectField("post_unlocked")
                    yield Rule()
                    yield PostMediaField("post_mediatype")
                    yield ResponseField("post_responsetype", label="Post Type (matches ANY checked)")
                    yield Rule()
                    yield Label("Creator Username:")
                    yield StrInput(id="post_username", placeholder="Username (e.g. creator_name)")
                    yield Rule()
                    yield Button("Filter", id="post_filter2")

        # ==========================================
        # 3. CART STAGING PAGE
        # ==========================================
        with Vertical(id="cart_page"):
            with Horizontal(classes="header_top_row"):
                with Vertical(classes="info_column"):
                    yield Button(">> Send Downloads to OF-Scraper", id="send_downloads")
                    yield Static("", classes="global_cart_info", markup=True)

                yield Checkbox("Download Text", id="cart_text_toggle")
                yield Checkbox("Text Only (Skip Media)", id="cart_text_only_toggle")
                yield Rule(orientation="vertical", classes="header_divider")
                with Vertical(classes="instructions_column"):
                    yield Static(
                        "[bold ansi_yellow]Cart Management:[/bold ansi_yellow]\n"
                        "• [bold]Click '\\[added]'[/bold] to instantly remove that item from the cart.\n"
                        "• [bold]Click 'Download Cart'[/bold] (the column header) to clear this entire page.\n"
                        "• Press [bold ansi_cyan](c)[/bold ansi_cyan] to remove all items currently visible on this page.\n"
                        "• Press [bold ansi_cyan](x)[/bold ansi_cyan] or [bold ansi_cyan]Shift+C[/bold ansi_cyan] to NUKE the entire cart.\n"
                        "• Show/Hide Columns [bold ansi_cyan](h)[/bold ansi_cyan].",
                        markup=True,
                    )

            # Inline Pagination
            with Horizontal(classes="pagination_row"):
                yield from pagination_bar("cart")
            with Vertical(id="cart_table_main"):
                yield DataTableExtended(id="cart_data_table")

        # ==========================================
        # 3. CONSOLE PAGE
        # ==========================================
        with Vertical(id="console_page"):
            with Horizontal(classes="header_top_row"):
                yield Static("[bold ansi_green]Console View[/bold ansi_green]\nMonitor active background tasks and download progress.", markup=True)
            yield OutConsole(id="console_page_log")

        # ==========================================
        # 4. COLUMNS PICKER PAGE
        # ==========================================
        with Vertical(id="columns_page"):
            with Horizontal(classes="header_top_row"):
                yield Static(
                    "[bold ansi_blue]Column Visibility:[/bold ansi_blue] Choose which columns appear in MediaTable/Cart and PostTable.\n"
                    "[dim]Number & Download Cart stay pinned. Apply & Return (v) updates this session only; Save as Default persists across runs.[/dim]",
                    markup=True,
                )
            with Horizontal(id="columns_action_row"):
                yield Button("Apply & Return (v)", id="apply_columns", variant="primary")
                yield Button("Save as Default", id="save_default_columns", variant="success")
                yield Button("Toggle Post Audio Cols", id="toggle_post_audio_cols")
                yield Button("Select All", id="select_all_columns")
                yield Button("Reset Defaults", id="reset_columns")
            with Horizontal(id="columns_grid"):
                with Vertical(classes="columns_panel"):
                    yield Static("[bold ansi_cyan]MediaTable & Cart Columns[/bold ansi_cyan]", classes="columns_panel_title", markup=True)
                    yield SelectionList(
                        *[
                            Selection(
                                re.sub("_", " ", c).title(),
                                value=c.lower(),
                                id=f"col_opt_media_{c.lower()}",
                                initial_state=(c.lower() not in EXTRA_COLUMNS),
                            )
                            for c in col_names
                            if c.lower() not in PINNED_COLUMNS
                        ],
                        id="media_columns_list",
                    )
                with Vertical(classes="columns_panel"):
                    yield Static("[bold ansi_cyan]PostTable Columns[/bold ansi_cyan]", classes="columns_panel_title", markup=True)
                    yield SelectionList(
                        *[
                            Selection(
                                re.sub("_", " ", c).title(),
                                value=c.lower(),
                                id=f"col_opt_post_{c.lower()}",
                                initial_state=(c.lower() not in POST_EXTRA_COLUMNS),
                            )
                            for c in post_col_names
                            if c.lower() not in PINNED_COLUMNS
                        ],
                        id="post_columns_list",
                    )
