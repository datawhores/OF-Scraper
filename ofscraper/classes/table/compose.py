from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, Rule, Static, Checkbox

from ofscraper.classes.table.fields.datefield import DateField
from ofscraper.classes.table.fields.mediafield import MediaField
from ofscraper.classes.table.fields.downloadfield import DownloadField
from ofscraper.classes.table.fields.numfield import NumField
from ofscraper.classes.table.fields.pricefield import PriceField
from ofscraper.classes.table.fields.responsefield import ResponseField
from ofscraper.classes.table.fields.selectfield import SelectField
from ofscraper.classes.table.fields.textsearch import TextSearch
from ofscraper.classes.table.fields.timefield import TimeField
from ofscraper.classes.table.inputs.strinput import StrInput
from ofscraper.classes.table.inputs.intergerinput import IntegerInput
from ofscraper.classes.table.sections.table_console import OutConsole
from ofscraper.classes.table.sections.sidebar import Sidebar
from ofscraper.classes.table.sections.table import DataTableExtended as DataTable
from ofscraper.classes.table.fields.sizefield import SizeMaxField, SizeMinField


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
        yield IntegerInput(placeholder="Number", id=f"{prefix}_page_input", classes="page_input_small")
        yield Button("Go", id=f"{prefix}_go", classes="page_btn")

def composer():
    # ... keep your tabs_row code ...

    with ContentSwitcher(initial="table_page"):
        with Vertical(id="table_page"):
            # ... keep your header_top_row code ...
            
            # Use the new helper!
            yield from pagination_bar("main")

            with Vertical(id="table_main"):
                yield DataTable(id="data_table")
            
            # ... keep sidebars ...

        with Vertical(id="cart_page"):
            # ... keep your header_top_row code ...

            # Use the new helper here too!
            yield from pagination_bar("cart")

            with Vertical(id="cart_table_main"):
                yield DataTable(id="cart_data_table")
def composer():
    with Horizontal(id="tabs_row"):
        yield Button("DataTable", id="table")
        yield Button("Cart", id="cart")
        yield Button("Console", id="console")

    yield Rule()

    with ContentSwitcher(initial="table_page"):
        
# ==========================================
        # 1. MAIN DATA TABLE PAGE
        # ==========================================
        with Vertical(id="table_page"):
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
                    yield Static("[bold blue]Sidebar Controls:[/bold blue]", markup=True)
                    yield Static("Options Menu:  [bold cyan]Ctrl+S[/bold cyan]", id="label_opt_sidebar", markup=True)
                    yield Static("Download Menu: [bold cyan]Ctrl+D[/bold cyan]", id="label_dl_sidebar", markup=True)
                yield Rule(orientation="vertical", classes="header_divider")
    
                # Column 4: Instructions
                with Vertical(classes="instructions_column"):
                    yield Static(
                        "[bold blue]Cart_Add:[/bold blue] Page (a) | All Filtered ([bold cyan]Shift+A[/bold cyan])\n"
                        "[bold blue]Cart_Unique:[/bold blue] Page (u) | All Unique ([bold cyan]Shift+U[/bold cyan])\n"
                        "[bold green]Cart_New Only:[/bold green] Page (e) | All New ([bold cyan]Shift+E[/bold cyan])\n"
                        "[bold red]Clear Cart:[/bold red] Page (c) | All Filtered ([bold cyan]Shift+C[/bold cyan]) | Nuke (x)",
                        id="table_instructions",
                        markup=True,
                    )
            with Horizontal(id="main_action_row"):
                yield Button(">> Send Downloads to OF-Scraper", id="send_downloads_main")
                yield Button("Reset Filters", id="reset")
            
            # Inline Pagination
            with Horizontal(classes="pagination_row"):
                yield from pagination_bar("main")

            with Vertical(id="table_main"):
                yield DataTable(id="data_table")

            # Sidebars (Only visible on Main Table)
            with Sidebar(id="download_option_sidebar", classes="-hidden"):
                yield Static("Values change right away", shrink=True, markup=True)
                yield SizeMinField("Download_Size_Min")
                yield SizeMaxField("Download_Size_Max")

            with Sidebar(id="options_sidebar", classes="-hidden"):
                with Container(id="main_options"):
                    yield Button("Filter", id="filter")
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
                    yield StrInput(id="username")
                    yield Rule()
                    yield Button("Filter", id="filter2")

        # ==========================================
        # 2. CART STAGING PAGE
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
                        "[bold yellow]Cart Management:[/bold yellow]\n"
                        "• [bold]Click '\\[added]'[/bold] to instantly remove that item from the cart.\n"
                        "• [bold]Click 'Download Cart'[/bold] (the column header) to clear this entire page.\n"
                        "• Press [bold cyan](c)[/bold cyan] to remove all items currently visible on this page.\n"
                        "• Press [bold cyan](x)[/bold cyan] or [bold cyan]Shift+C[/bold cyan] to NUKE the entire cart.",
                        markup=True,
                    )

            # Inline Pagination
            with Horizontal(classes="pagination_row"):
                yield from pagination_bar("cart")
            with Vertical(id="cart_table_main"):
                yield DataTable(id="cart_data_table")

        # ==========================================
        # 3. CONSOLE PAGE
        # ==========================================
        with Vertical(id="console_page"):
            with Horizontal(classes="header_top_row"):
                yield Static("[bold green]Console View[/bold green]\nMonitor active background tasks and download progress.", markup=True)
            yield OutConsole(id="console_page_log")