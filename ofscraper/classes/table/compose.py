from textual.containers import (
    Container,
    Horizontal,
    Vertical,
    VerticalScroll,
    VerticalGroup,
    HorizontalGroup,
)
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
    with HorizontalGroup(id="buttons"):
        yield Button("DataTable", id="table")
        yield Button("Console", id="console")

    with ContentSwitcher(initial="table_page"):
        with VerticalScroll(id="table_page"):
            with Container(id="table_header"):
                with Horizontal():
                    with Vertical(classes="table_info"):
                        yield Static(
                            "[bold blue]Toggle Search Sidebar[/bold blue]: Ctrl+S",
                            markup=True,
                        )
                        yield Static(
                            "[bold blue]Toggle Page Selection Sidebar[/bold blue]: Ctrl+T",
                            markup=True,
                        )
                        yield Static(
                            "[bold blue]Toggle Download Filter Sidebar[/bold blue]: Ctrl+D",
                            markup=True,
                        )
                    yield Rule(orientation="vertical")
                    with Vertical(classes="table_info"):
                        yield Static(
                            "[bold blue]Navigate Table[/bold blue]: Arrows", markup=True
                        )
                        yield Static(
                            "[bold blue]Filter Table via Cell[/bold blue]: ; or '",
                            markup=True,
                        )
                        yield Static(
                            "[bold blue]Add to Cart[/bold blue]: Click cell in 'download cart' Column",
                            markup=True,
                        )
                yield Rule()
                for _ in range(3):
                    yield Static("", classes="search_info", shrink=True, markup=True)
            yield Rule()
            with HorizontalGroup(id="data"):
                yield Button("Reset", id="reset")
                yield Button(">> Send Downloads to OF-Scraper", id="send_downloads")
            with VerticalGroup(id="table_main"):
                yield DataTable(id="data_table")
                yield DataTable(id="data_table_hidden")

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

                    for ele in ["Media_ID"]:
                        yield NumField(ele)
                    for ele in ["Post_ID"]:
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
                    yield SelectField("Downloaded")
                    yield SelectField("Unlocked")
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
