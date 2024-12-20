import logging
import queue
import re

import arrow
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, ContentSwitcher, Rule,Static

import ofscraper.utils.logs.logger as logger
from ofscraper.classes.table.fields.datefield import DateField
from ofscraper.classes.table.fields.mediafield import MediaField
from ofscraper.classes.table.fields.numfield import NumField, OtherMediaNumField
from ofscraper.classes.table.fields.pricefield import PriceField
from ofscraper.classes.table.fields.responsefield import ResponseField
from ofscraper.classes.table.fields.selectfield import SelectField
from ofscraper.classes.table.fields.textsearch import TextSearch
from ofscraper.classes.table.fields.timefield import TimeField
from ofscraper.classes.table.inputs.strinput import StrInput
from ofscraper.classes.table.utils.row_names import row_names, row_names_all
from ofscraper.classes.table.utils.status import status
from ofscraper.classes.table.utils.lock import mutex
from ofscraper.classes.table.sections.table_console import OutConsole
from ofscraper.classes.table.sections.sidebar import Sidebar
from ofscraper.classes.table.sections.table import TableRow, DataTableExtended as DataTable
from textual.widgets import SelectionList
from ofscraper.classes.table.css import CSS
from ofscraper.classes.table.const import AMOUNT_PER_PAGE,START_PAGE


def composer(args):
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
                for _ in range(3):
                    yield Static("",classes="search_info",shrink=True,markup=True)
                yield Rule()
                with Horizontal(id="data"):
                    yield Button("Reset", id="reset")
                    yield Button(
                        ">> Send Downloads to OF-Scraper", id="send_downloads"
                    )

            
                with Container(id="table_main"):
                    with Sidebar(id="page_option_sidebar"):
                        yield Button("Enter", id="page_enter")
                        for ele in ["Page"]:
                            yield NumField(ele, default=START_PAGE)
                        for ele in ["Num_Per_Page"]:
                            yield NumField(ele, default=AMOUNT_PER_PAGE)
                        yield Button("Enter", id="page_enter2")

                    with Sidebar(id="options_sidebar"):
                        with Container(id="main_options"):
                            yield Button("Filter", id="filter")
                            yield Rule()
                            for ele in ["Text"]:
                                yield TextSearch(ele)
                            yield Rule()
                            for ele in ["other_posts_with_media"]:
                                yield OtherMediaNumField(ele)

                            for ele in ["Media_ID"]:
                                yield NumField(ele, default=args.media_id)
                            yield Rule()
                            for ele in ["Post_ID"]:
                                yield NumField(ele, default=args.post_id)
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
                            yield Button("Filter", id="filter2")
                    yield DataTable(id="data_table")
                    yield DataTable(id="data_table_hidden")

            with Vertical(id="console_page"):
                yield OutConsole()
