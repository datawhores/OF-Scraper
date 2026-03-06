from textual.containers import Container, Horizontal, Vertical, VerticalGroup
from textual.widgets import Button, ContentSwitcher, Rule, Static

from ofscraper.classes.table.fields.datefield import DateField
from ofscraper.classes.table.fields.mediafield import MediaField
from ofscraper.classes.table.fields.downloadfield import DownloadField
from ofscraper.classes.table.fields.numfield import NumField, PostiveNumField
from ofscraper.classes.table.fields.pricefield import PriceField
from ofscraper.classes.table.fields.responsefield import ResponseField
from ofscraper.classes.table.fields.selectfield import SelectField
from ofscraper.classes.table.fields.textsearch import TextSearch
from ofscraper.classes.table.fields.timefield import TimeField
from ofscraper.classes.table.inputs.strinput import StrInput
from ofscraper.classes.table.sections.table_console import OutConsole
from ofscraper.classes.table.sections.sidebar import Sidebar
from ofscraper.classes.table.sections.table import DataTableExtended as DataTable
from ofscraper.classes.table.const import AMOUNT_PER_PAGE, START_PAGE
from ofscraper.classes.table.fields.sizefield import SizeMaxField, SizeMinField


def composer():
    # =================================================================
    # TOP TABS: Switch Views
    # =================================================================
    with Horizontal(id="tabs_row"):
        yield Button("DataTable", id="table")
        yield Button("Console", id="console")

    # =================================================================
    # HEADER: 4-Column Info (Trackers | Page Info | Toggles | Shortcuts)
    # =================================================================
    with Horizontal(id="header_top_row"):
        
        # Column 1: Database & Cart Status
        with Vertical(id="trackers_column"):
            yield Static("", id="db_info_bar", markup=True)
            yield Static("", id="global_cart_info", markup=True)

        yield Rule(orientation="vertical", classes="header_divider")

        # Column 2: Current Page & Sorting State
        with Vertical(id="page_info_column"):
            yield Static("", id="view_info_bar", markup=True)

        yield Rule(orientation="vertical", classes="header_divider")

        # Column 3: Toggles Status
        with Vertical(id="toggles_column"):
            yield Static("[bold blue]Sidebar Controls:[/bold blue]", markup=True)
            yield Static("Options Menu:  [bold cyan]Ctrl+S[/bold cyan] [bold](Closed)[/bold]", id="label_opt_sidebar", markup=True)
            yield Static("Page Menu:     [bold cyan]Ctrl+T[/bold cyan] [bold](Closed)[/bold]", id="label_page_sidebar", markup=True)
            yield Static("Download Menu: [bold cyan]Ctrl+D[/bold cyan] [bold](Closed)[/bold]", id="label_dl_sidebar", markup=True)
            yield Static("[bold blue]Table:[/bold blue] Navigate (Arrows) | Quick Filter (; or ')", id="table_nav_hint", markup=True)
            
        yield Rule(orientation="vertical", classes="header_divider")

        # Column 4: Full Keyboard Instructions (Shift & Clear Actions)
        with Vertical(id="instructions_column"):
            yield Static(
                "[bold blue]Cart_Add:[/bold blue] Page (a) | All Filtered ([bold cyan]Shift+A[/bold cyan])\n"
                "[bold blue]Cart_Unique:[/bold blue] Page (u) | All Unique ([bold cyan]Shift+U[/bold cyan])\n"
                "[bold green]Cart_New Only:[/bold green] Page (e) | All New ([bold cyan]Shift+E[/bold cyan])\n"
                "[bold red]Clear Cart:[/bold red] Page (c) | All Filtered ([bold cyan]Shift+C[/bold cyan]) | Nuke (x)",
                id="table_instructions",
                markup=True,
            )

    yield Rule()

    # =================================================================
    # ACTION BUTTONS: Modify/Submit Data
    # =================================================================
    with Horizontal(id="button_row"):
        yield Button("Reset Filters", id="reset")
        yield Button(">> Send Downloads to OF-Scraper", id="send_downloads")

    with ContentSwitcher(initial="table_page"):
        with Vertical(id="table_page"):
                
            with VerticalGroup(id="table_main"):
                yield DataTable(id="data_table")

            with Sidebar(id="download_option_sidebar", classes="-hidden"):
                yield Static("Values are change right away", shrink=True, markup=True)
                yield SizeMinField("Download_Size_Min")
                yield SizeMaxField("Download_Size_Max")

            with Sidebar(id="page_option_sidebar", classes="-hidden"):
                yield Button("Enter", id="page_enter")
                for ele in ["Page"]:
                    yield PostiveNumField(ele, default=START_PAGE)
                for ele in ["Num_Per_Page"]:
                    yield PostiveNumField(ele, default=AMOUNT_PER_PAGE)
                yield Button("Enter", id="page_enter2")

            with Sidebar(id="options_sidebar", classes="-hidden"):
                with Container(id="main_options"):
                    yield Button("Filter", id="filter")
                    yield Rule()
                    for ele in ["Text"]:
                        yield TextSearch(ele)
                    yield Rule()

                    for ele in ["Media_ID", "Post_ID"]:
                        yield NumField(ele)
                    yield Rule()
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
                    for ele in ["Downloaded", "Unlocked"]:
                        yield SelectField(ele)
                    yield Rule()
                    for ele in ["Mediatype"]:
                        yield MediaField(ele)
                    for ele in ["Responsetype"]:
                        yield ResponseField(ele)
                    yield Rule()
                    yield DownloadField("Download_Type")
                    yield Rule()
                    for ele in ["username"]:
                        yield StrInput(id=ele)
                    yield Rule()
                    yield Button("Filter", id="filter2")
                    
        with Vertical(id="console_page"):
            yield OutConsole(id="console_page", classes="-hidden")