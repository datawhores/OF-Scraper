import logging
import re
from typing import Any
import asyncio
from functools import partial

import arrow
from rich.text import Text
from textual import events,on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical,Container
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    DataTable,
    Input,
    Label,
    RichLog,

)
from textual.widget import Widget


import ofscraper.utils.logs.logger as logger
import ofscraper.utils.constants as constants


log = logging.getLogger("shared")

global app

# console=console_.get_shared_console()
class OutConsole(RichLog):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class StyledButton(Button):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class TextSearch(Horizontal):
    DEFAULT_CSS ="""
        TextSearch Input{
    width:3fr;
    }

    TextSearch Checkbox{
     width:2fr;
    }

     TextSearch {
    column-span:4;
    }
    
"""
    def __init__(self, name: str) -> None:
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield Input(
            placeholder=f"{self.filter_name.capitalize()} Search",
            id=f"{self.filter_name}_search",
        )
        yield Checkbox("FullString", False, id="fullstring_search")

    # def on_mount(self):
    #     self.styles.height = "auto"

    def empty(self):
        return self.query_one(Input).value == ""

    def update_table_val(self, val):
        self.query_one(Input).value = val

    def reset(self):
        self.query_one(Input).value = ""

    def validate(self, val):
        if self.query_one(Input).value == "" or self.query_one(Input).value is None:
            return True
        elif self.query_one(Checkbox).value and re.fullmatch(
            self.query_one(Input).value,
            str(val),
            (re.IGNORECASE if self.query_one(Input).islower() else 0),
        ):
            return True
        elif not self.query_one(Checkbox).value and re.search(
            self.query_one(Input).value,
            str(val),
            (re.IGNORECASE if self.query_one(Input).value.islower() else 0),
        ):
            return True
        return False


class NumField(Horizontal):
    def __init__(self, name: str) -> None:
        name=name.lower()
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield IntegerInput(
            placeholder=self.filter_name.capitalize().replace("_", " "),
            id=f"{self.filter_name}_input",
        )

    def empty(self):
        return self.query_one(IntegerInput).value == ""

    def update_table_val(self, val):
        self.query_one(IntegerInput).value = val

    def reset(self):
        self.query_one(IntegerInput).value = ""
 
    # class IntegerInput(Input):
    #     def __init__(
    #         self,
    #         *args,
    #         **kwargs,
    #         # ---snip---
    #     ) -> None:
    #         super().__init__(
    #             # ---snip---
    #             *args,
    #             **kwargs,
    #         )

    #     def insert_text_at_cursor(self, text: str) -> None:
    #         try:
    #             int(text)
    #         except ValueError:
    #             pass
    #         else:
    #             app.status[self.key]=self.value
    #             super().insert_text_at_cursor(text)
    #     def on_input_submitted(self):
    #         app.status[self.key]=self.value
    #     @property
    #     def key(self):
    #         return self.id.replace("_input","")

class IntegerInput( Input ):
    """A numeric filter input widget."""
    CAST = int
    def __init__( self, *args: Any, **kwargs: Any ) -> None:
        """Initialise the input."""
        super().__init__( *args, **kwargs )
        # TODO: Workaround for https://github.com/Textualize/textual/issues/1216
        self.value = self.validate_value( self.value )

    def validate_value( self, value: str ) -> str:
        """Validate the input.

        Args:
            value: The value to validate.

        Returns:
            The acceptable value.
        """
        # If the input field isn't empty...
        if value.strip():
            try:
                # ...run it through the casting function. We don't care
                # about what comes out of the other end, we just case that
                # it makes it through at all.
                _ = self.CAST( value )
            except ValueError:
                # It's expected that the casting function will throw a
                # ValueError if there's a problem with the conversion (see
                # int and float for example) so, here we are. Make a
                # noise...
                self.app.bell()
                # ...and return what's in the input now because we're
                # rejecting the new value.
                return self.value
        # The value to test is either empty, or valid. Let's accept it.
        return value


    def on_input_changed(self):
        app.status[self.key]=self.value
    def on_input_submitted(self):
        app.status[self.key]=self.value
    @property
    def key(self):
        return self.id.replace("_input","")


class PriceField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield IntegerInput(
            placeholder="Min Price", id=f"{self.filter_name}_search"
        )
        yield IntegerInput(
            placeholder="Max Price", id=f"{self.filter_name}_search2"
        )

    def empty(self):
        return (
            self.query(IntegerInput)[0].value == ""
            and self.query(IntegerInput)[1].value == ""
        )


    def update_table_val(self, val):
        if val.lower() == "free":
            val = "0"
        for ele in self.query(IntegerInput):
            ele.value = val

    def reset(self):
        self.query_one(IntegerInput).value = ""

    def validate(self, val):
        minval = self.query_one(f"#{self.filter_name}_search").value
        maxval = self.query_one(f"#{self.filter_name}_search2").value
        if val.lower() == "free":
            val = 0
        if not maxval and not minval:
            return True
        elif minval and float(val) < float(minval):
            return False
        elif maxval and float(val) > float(maxval):
            return False
        return True



class TimeField(Container):
    DEFAULT_CSS="""
    TimeField{
    column-span:4;
    row-span:2;
    }

    TimeField Label{
    width:2fr;
    }

    .time_field{
    width:1fr;
    }
    
"""
    def __init__(self, name: str) -> None:
        super().__init__(id=name)
        self.filter_name = name
        self.timeconversions = [60 * 60, 60, 1]

    def compose(self):
        with Horizontal(id="minLength"):
            yield Label("MinLength")
            yield IntegerInput(placeholder="Hour",classes="time_field")
            yield IntegerInput(placeholder="Min",classes="time_field")
            yield IntegerInput(placeholder="Sec",classes="time_field")
        with Horizontal(id="maxLength"):
            yield Label("MaxLength")
            yield IntegerInput(placeholder="Hour",classes="time_field")
            yield IntegerInput(placeholder="Min",classes="time_field")
            yield IntegerInput(placeholder="Sec",classes="time_field")

    def empty(self):
        return (
            len(list(filter(lambda x: x.value != "", self.query(IntegerInput))))
            == 0
        )

    def update_table_val(self, val):
        minLenthInputs = list(self.query_one("#minLength").query(IntegerInput))
        maxLenthInputs = list(self.query_one("#maxLength").query(IntegerInput))
        valArray = val.split(":")
        for pack in zip(maxLenthInputs, minLenthInputs, valArray):
            pack[0].value = pack[2]
            pack[1].value = pack[2]

    def reset(self):
        for ele in self.query(IntegerInput):
            ele.value = ""

    def convertString(self, val):
        if val == "N/A":
            return 0
        if isinstance(val, int):
            return val
        elif val.find(":") != -1:
            a = val.split(":")
            total = sum(
                [(int(a[i] or 0) * self.timeconversions[i]) for i in range(len(a))]
            )
            return total

        return int(val)

    def validate(self, val):
        if self.validateAfter(val) and self.validateBefore(val):
            return True
        return False

    def validateAfter(self, val):
        if val == "N/A":
            return True
        comparestr = ""
        if (
            len(
                list(
                    filter(
                        lambda x: x.value != "",
                        self.query_one("#minLength").query(IntegerInput),
                    )
                )
            )
            == 0
        ):
            return True
        for ele in self.query_one("#minLength").query(IntegerInput):
            comparestr = f"{comparestr}{ele.value or '00'}:"
        comparestr = comparestr[:-1]
        if self.convertString(val) < self.convertString(comparestr):
            return False
        return True

    def validateBefore(self, val):
        if val == "N/A":
            return True
        comparestr = ""
        if (
            len(
                list(
                    filter(
                        lambda x: x.value != "",
                        self.query_one("#maxLength").query(IntegerInput),
                    )
                )
            )
            == 0
        ):
            return True
        for ele in self.query_one("#maxLength").query(IntegerInput):
            comparestr = f"{comparestr}{ele.value}:"
        comparestr = comparestr[:-1]
        if self.convertString(val) > self.convertString(comparestr):
            return False
        return True


class BoolField(Widget):
    def __init__(self, name: str) -> None:
        name=name.lower()
        super().__init__(id=name, classes="container")
        self.filter_name = name

    def compose(self):
        with Horizontal():
            yield Checkbox(
                f"{self.filter_name.capitalize()} True",
                True,
                id=f"{self.filter_name}_true",
            )
            yield Checkbox(
                f"{self.filter_name.capitalize()} False",
                True,
                id=f"{self.filter_name}_false",
            )



    def empty(self):
        return (
            self.query(Checkbox)[0].value is False
            and self.query(Checkbox)[1].value is False
        )

    def reset(self):
        for ele in self.query(Checkbox):
            ele.value = True
    def update_table_val(self, val):
        if val == "True":
            self.query_one(f"#{self.filter_name}_true").value = True
            self.query_one(f"#{self.filter_name}_false").value = False
        elif val == "False":
            self.query_one(f"#{self.filter_name}_false").value = True
            self.query_one(f"#{self.filter_name}_true").value = False
    def on_checkbox_changed(self,checkbox):
        key=checkbox.checkbox.id.lower()
        toggle=checkbox.checkbox.value
        if key==f"{self.filter_name}_true":
            app.status[f"{self.filter_name}"]=toggle
        elif key==f"{self.filter_name}_false":
            app.status[f"not_{self.filter_name}"]=toggle


class MediaField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name, classes="container")
        self.filter_name = name

    def compose(self):
        yield Checkbox("audios", True, id=f"{self.filter_name}_audios")
        yield Checkbox("videos", True, id=f"{self.filter_name}_videos")
        yield Checkbox("images", True, id=f"{self.filter_name}_images")

    def on_checkbox_changed(self,checkbox):
        key=re.sub("Mediatype_","",checkbox.checkbox.id,re.IGNORECASE)
        toggle=checkbox.checkbox.value
        if not toggle:
            app.status["mediatypes"]=set(list(filter(lambda x:x!=key,app.status["mediatypes"])))
        else:
            app.status["mediatypes"].add(key)
        # app.update_table()


    def empty(self):
        return (
            self.query(Checkbox)[0].value is False
            and self.query(Checkbox)[1].value is False
            and self.query(Checkbox)[2].value is False
        )

    def update_table_val(self, val):
        if val == "audios":
            self.query_one(f"#{self.filter_name}_audios").value = True
            self.query_one(f"#{self.filter_name}_videos").value = False
            self.query_one(f"#{self.filter_name}_images").value = False
        elif val == "videos":
            self.query_one(f"#{self.filter_name}_videos").value = True
            self.query_one(f"#{self.filter_name}_audios").value = False
            self.query_one(f"#{self.filter_name}_images").value = False
        elif val == "images":
            self.query_one(f"#{self.filter_name}_images").value = True
            self.query_one(f"#{self.filter_name}_audios").value = False
            self.query_one(f"#{self.filter_name}_videos").value = False

    def reset(self):
        for ele in self.query(Checkbox):
            ele.value = True




class DateField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name, classes="container")
        self.filter_name = name

    def compose(self):
        yield Input(placeholder="Earliest Date", id="minDate")
        yield Input(placeholder="Latest Date", id="maxDate")

    def empty(self):
        return self.query(Input)[0].value == "" and self.query(Input)[1].value == ""



    def update_table_val(self, val):
        val = self.convertString(val)
        for ele in self.query(Input):
            if val != "":
                ele.value = arrow.get(val).format("YYYY.MM.DD")
            else:
                ele.value = ""

    def reset(self):
        for ele in self.query(Input):
            ele.value = ""

    def validate(self, val):
        if self.validateAfter(val) and self.validateBefore(val):
            return True
        return False

    def validateAfter(self, val):
        if self.query_one("#minDate").value == "":
            return True
        compare = arrow.get(self.convertString(val))
        early = arrow.get(self.convertString(self.query_one("#minDate").value))

        if compare < early:
            return False
        return True

    def validateBefore(self, val):
        if self.query_one("#maxDate").value == "":
            return True
        compare = arrow.get(self.convertString(val))
        late = arrow.get(self.convertString(self.query_one("#maxDate").value))
        if compare > late:
            return False
        return True

    def convertString(self, val):
        match = re.search("[0-9-/\.]+", val)
        if not match:
            return ""
        return match.group(0)

class TableRow():
    def __init__(self,table_row):
        self._table_row = table_row
        self._row_names=constants.getattr("ROW_NAMES")
        self._styled=None
    def get_styled(self,count=1):
        if not self._styled:
            styled_row=[Text(str(self.get_val(key) if not key.lower()=="number" else count+1), style="italic #03AC13",overflow="fold") for key in self._row_names]
            styled_row=[self.split_join_max_len(ele,30) for ele in styled_row]
            self._styled=styled_row
        return  self._styled
    def split_join_max_len(self,text, max_len):
        current_line = ""
        result = ""
        for word in str(text).split():
            if len(current_line + word) <= max_len:
                current_line += " " + word
            else:
                result += current_line.strip() + "\n"
                current_line = word
        result += current_line.strip()
        result=re.sub("^\s+","",result)
        result=re.sub("\s+$","",result)
        return Text(result)
                

    def get_val(self,name):
        name=name.lower()
        return self._table_row[name]

    def set_val(self,key,val):
        self._table_row[key.lower()]=val
    

class Status():
    def __init__(self, *args, **kwargs) -> None:
        self._status={}
        self._set_defaults()
    def _set_defaults(self):
        self._status.setdefault("mediatypes",set(["audios","videos","images"]))
        self._status.setdefault("not_unlocked",True)
        self._status.setdefault("unlocked",True)
        self._status.setdefault("downloaded",True)
        self._status.setdefault("not_downloaded",True)
        self._status.setdefault("times_detected",None)
        self._status.setdefault("post_media_count",None)





    def validate(self,key,test):
        key=key.lower()
        if key=="mediatype":
            return self._mediatype_helper(test)
        elif key in {"unlocked","downloaded"}:
            return self._bool_helper(key,test)
        elif key in {"times_detected","post_media_count"}:
            return self._times_detected_helper(key,test)
        return True
    def _mediatype_helper(self,test):
        return test.lower() in self._status["mediatypes"]
    def _bool_helper(self,key,test):
        if not test and self._status[f'not_{key}']:
            return True
        elif test and self._status[f'{key}']:
            return True
        return False
    def _times_detected_helper(self,key,test):
        if self._status[key] is None:
            return True
        else:
            return int(self._status[key])==int(test)


class Sidebar(Container):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)




class InputApp(App):
    CSS = """
    Screen {
       layers: sidebar;
       overflow: hidden;
    }

    Sidebar {
        width: 45%;
        dock: left;
        layer: sidebar;
        overflow-y:scroll;
        overflow-x:scroll;

    }


    #options{
        height:125vh;
        layout: grid;
        grid-size: 4 11;
        margin-top:2;
    }

#buttons{
height:15vh;
}
 
    Sidebar.-hidden {
        display: none;
    }

    #data_table {
    margin-bottom:2;
    height:95%

    }


    #data_table_holder {
         overflow-x:scroll;
        overflow-y:scroll;
        width:80%;
        height:80%;
    }

    Widget {
    column-span:4;
    }
    NumField {
    column-span:3;
    }
    #Times_Detected{
    column-span:1;
    }
    #Post_Media_Count{
    column-span:1;
    }
    #table_main{
    height:6fr;
    }
    """

    BINDINGS = [("ctrl+s", "toggle_sidebar")]
    def action_toggle_sidebar(self) -> None:
        self.query_one(Sidebar).toggle_class("-hidden")

    def __init__(self, *args, **kwargs) -> None:
        self._status=Status()
        super().__init__(*args, **kwargs)
    
    @property
    def status(self):
        return self._status._status
    
    @status.setter
    def status(self,val):
        self._status._status=val
    def __call__(self,*args,**kwargs):
        self.table_data_original=kwargs.pop("table_data",None)
        self.table_data=[TableRow(ele) for ele in self.table_data_original[1:]]
        self._sorted_hash={}
        self.row_names=constants.getattr("ROW_NAMES")
        self.mutex=kwargs.pop("mutex",None)
        self.row_queue=kwargs.pop("row_queue",None)
        self._sorted_rows=self.table_data
        self._filtered_rows = self.table_data
        self._init_mediatype=kwargs.pop("mediatype",None)
        self.run()
    def update_table(self):
        self.run_worker(self._update_table())
    async def _update_table(self):
        await asyncio.get_event_loop().run_in_executor(None,self.set_filtered_rows)
        await asyncio.get_event_loop().run_in_executor(None,self.make_table)


    def on_data_table_header_selected(self, event):
        self.sort_helper(event.label.plain)

    def on_data_table_cell_selected(self, event):
        table = self.query_one(DataTable)
        cursor_coordinate = table.cursor_coordinate
        if self.row_names[cursor_coordinate.column]=="Download_Cart":
            self.change_download_cart(event.coordinate)


    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "reset":
            self.set_filtered_rows(reset=True)
            self.reset_all_inputs()
            self.set_reverse(init=True)
            self.make_table()
            self.reset_filtered_cart()

        elif event.button.id == "send_downloads":
            log.info("Adding Downloads to queue")
            self.add_to_row_queue()
            self.query_one(ContentSwitcher).current = "console_page"

        elif event.button.id == "filter":
            self.update_table()
        elif event.button.id in ["console", "table"]:
            self.query_one(ContentSwitcher).current = f"{event.button.id}_page"

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.exit()
        if event.character in set([";", "'"]):
            table = self.query_one(DataTable)
            cursor_coordinate = table.cursor_coordinate
            if len(table._data) == 0:
                return
            cell_key = table.coordinate_to_cell_key(cursor_coordinate)
            event = DataTable.CellSelected(
                self,
                table.get_cell_at(cursor_coordinate),
                coordinate=cursor_coordinate,
                cell_key=cell_key,
            )
            row_name = self.row_names[event.coordinate[1]]
            if row_name != "Download_Cart":
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
                with Horizontal(id="data"):
                    yield StyledButton("Reset", id="reset")
                    yield StyledButton("Filter", id="filter")
                    yield StyledButton(
                        ">> Send Downloads to OF-Scraper", id="send_downloads"
                    )
                yield Label("Ctrl+S: Toggle Sidebar")
                yield Label("Arrows: Navigate Table")
                yield Label("\";\" or \"'\": Filter Table via Cell")
                yield Label("Add to Cart: Click cell in 'Download Cart' Column")
                with Container(id="table_main"):
                    with Sidebar():
                        with Container(id="options"):
                            for ele in ["Text"]:
                                yield TextSearch(ele)
                            for ele in ["Times_Detected"]:
                                yield NumField(ele)
                            for ele  in ["Media_ID", "Post_ID", "Post_Media_Count"]:
                                yield NumField(ele)
                            for ele in ["Price"]:
                                yield PriceField(ele)
                            for ele in ["Post_Date"]:
                                yield DateField(ele)
                            for ele in ["Length"]:
                                yield TimeField(ele)
                            yield BoolField("Downloaded")
                            yield BoolField("Unlocked")
                            for ele in ["Mediatype"]:
                                yield MediaField(ele)
                    yield DataTable(fixed_rows=1, id="data_table")
                    yield Container()
            with Vertical(id="console_page"):
                yield OutConsole()
    def on_mount(self) -> None:
        self.query_one(Sidebar).toggle_class("-hidden")
        self.set_reverse(init=True)
        self.set_cart_toggle(init=True)
        self.set_filtered_rows()
        self.make_table()
        logger.add_widget(self.query_one("#console_page").query_one(OutConsole))
        self.update_table()
    def _set_and_sort_media_type(self):
        mediatype=self._init_mediatype if bool(self._init_mediatype) else ["Audios","Videos","Images"]

        self.query_one("#Mediatype_audios").value=(mediatype==None or "Audios" in mediatype)
        self.query_one("#Mediatype_videos").value=(mediatype==None or "Videos" in mediatype)
        self.query_one("#Mediatype_images").value=(mediatype==None or "Images" in mediatype)
    # Cart
    def change_download_cart(self, coord):
        table = self.query_one(DataTable)
        Download_Cart = table.get_cell_at(coord)
        if Download_Cart.plain == "Not Unlocked":
            return
        elif Download_Cart.plain == "[]":
            self.update_cell_at_coords(coord, "[added]")


        elif Download_Cart.plain == "[added]":
            self.update_cell_at_coords(coord, "[]")

        elif Download_Cart.plain == "[downloaded]" or "[failed]":
            self.update_cell_at_coords(coord, "[]")

    def add_to_row_queue(self):
        table = self.query_one(DataTable)
        row_keys = [str(ele.get_val("index")) for ele in self._filtered_rows]
        index = self.row_names.index("Download_Cart")
        filter_row_keys = list(
            filter(lambda x: table.get_row(x)[index].plain == "[added]", row_keys)
        )
        self.update_downloadcart_cells(filter_row_keys, "[downloading]")
        log.info(f"Number of Downloads sent to queue {len(filter_row_keys)}")
        [
            self.row_queue.put(ele)
            for ele in map(lambda x: (table.get_row(x), x), filter_row_keys)
        ]


    def reset_cart(self):
        self.update_downloadcart_cells(
            [
                str(x[0])
                for x in list(
                    filter(lambda x: x.get_val("download_cart") == "[added]", self.table_data)
                )
            ],
            "[]",
        )

    def reset_filtered_cart(self):
        index = self.row_names.index("Download_Cart")
        self.update_downloadcart_cells(
            list(filter(lambda x: x.get_val("unlocked") != "Not Unlocked", self._filtered_rows)),
            "[]",
        )

    def update_cell_at_coords(self, coords, value):
        with self.mutex:
            for coord in coords if isinstance(coords,list) else [coords]:
                try:
                    table = self.query_one(DataTable)
                    table.update_cell_at(coord, Text(value))
                    row_key=table.coordinate_to_cell_key(coord).row_key.value
                    key=self.row_names[coord.column]
                    self.table_data[int(row_key)].set_val(key,value)
                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)

    def update_downloadcart_cells(self, keys, value):
        self.update_cell(keys, "Download_Cart", value)

    def update_cell(self, keys, name, value, perst=True):
        if not isinstance(keys, list):
            keys = [keys]
        with self.mutex:
            for key in keys:
                try:
                    if perst:
                        self.table_data[int(key)].set_val(name,value)
                    table = self.query_one(DataTable)
                    table.update_cell(key, name, Text(str(value)))
                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)

    # Table Functions
    def sort_helper(self,label):
        self.run_worker(self._sort_helper(label),thread=True,exclusive=True)

    async def _sort_helper(self, label=None):
        with self.mutex:
            if label is None:
                return
            elif label == "Download Cart":
                index = self.row_names.index(re.sub(" ", "_", label))
                filtered_status = ["[downloading]", "Not Unlocked", "[downloaded]"]
                table = self.query_one(DataTable)
                self.set_cart_toggle()
                keys = [str(ele[0]) for ele in self._filtered_rows]
                filter_keys = list(
                    filter(
                        lambda x: table.get_row(x)[index].plain not in filtered_status, keys
                    )
                )
                log.debug(f"set cart toggle to {self.cart_toggle.plain}")
                [
                    table.update_cell(key, "Download_Cart", self.cart_toggle)
                    for key in filter_keys
                ]
                return


            key=re.sub(" ", "_", label).lower()
            self.set_reverse(label=label)
            if self._get_sorted_hash(key):
                self._sorted_rows=self._get_sorted_hash(key)
            elif label == "Number":
                self._sorted_rows = sorted(
                    self.table_data, key=lambda x: x.get_val(key), reverse=self.reverse
                )
            elif label == "UserName":
                self._sorted_rows = sorted(
                    self.table_data, key=lambda x: x.get_val(key), reverse=self.reverse
                )
            elif label == "Downloaded":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: 1 if x.get_val(key) is True else 0,
                    reverse=self.reverse,
                )

            elif label == "Unlocked":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: 1 if x.get_val(key) is True else 0,
                    reverse=self.reverse,
                )
            elif label == "Times Detected":
                self._sorted_rows = sorted(
                    self._filtered_rows,
                    key=lambda x: x.get_val(key) or 0,
                    reverse=self.reverse,
                )
            elif label == "Length":
                helperNode = self.query_one("#Length")
                self._sorted_rows = sorted(
                    self._filtered_rows,
                    key=lambda x: (
                        helperNode.convertString(x.get_val(key)) if x.get_val(key) != "N/A" else 0
                    ),
                    reverse=self.reverse,
                )
            elif label == "Mediatype":
                self._sorted_rows = sorted(
                    self.table_data, key=lambda x: x.get_val(key), reverse=self.reverse
                )
            elif label == "Post Date":
                helperNode = self.query_one("#Post_Date")
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: (
                        helperNode.convertString(x.get_val(key)) if x.get_val(key) != "N/A" else 0
                    ),
                    reverse=self.reverse,
                )
            elif label == "Post Media Count":
                self._sorted_rows = sorted(
                    self.table_data, key=lambda x: x.get_val(key), reverse=self.reverse
                )

            elif label == "Responsetype":
                self._sorted_rows = sorted(
                    self.table_data, key=lambda x: x.get_val(key), reverse=self.reverse
                )
            elif label == "Price":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: int(float(x.get_val(key))) if x.get_val(key) != "Free" else 0,
                    reverse=self.reverse,
                )

            elif label == "Post ID":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: x.get_val(key) if x.get_val(key) else 0,
                    reverse=self.reverse,
                )
            elif label == "Media ID":
                self._sorted_rows = sorted(
                    self.table_data,
                    key=lambda x: x.get_val(key) if x.get_val(key) else 0,
                    reverse=self.reverse,
                )
            elif label == "Text":
                self._sorted_rows = sorted(
                    self._filtered_rows, key=lambda x: x.get_val(key), reverse=self.reverse
                )
            self._set_sorted_hash(key,self._sorted_rows)
        await asyncio.get_event_loop().run_in_executor(None,self.set_filtered_rows)
        await asyncio.get_event_loop().run_in_executor(None,self.make_table)
    def _get_sorted_hash(self,key):
        return self._sorted_hash.get(f'{key}_{self.reverse}')
    def _set_sorted_hash(self,key,val):
        self._sorted_hash[f'{key}_{self.reverse}']=val

    def set_reverse(self, label=None, init=False):
        if init:
            self.reverse = None
            self.label = None
        if not self.label:
            self.label = label
            self.reverse = False
        elif label != self.label:
            self.label = label
            self.reverse = False

        elif self.label == label and not self.reverse:
            self.reverse = True

        elif self.label == label and self.reverse:
            self.reverse = False

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
            if reset is True:
                self._filtered_rows = self.table_data
                self.reset_cart()
            else:
                filter_rows=self._sorted_rows
                for count, name in enumerate(self.row_names):
                    name=name.lower()
                    try:
                        targetNode = self.query_one(f"#{name}")
                        if targetNode.empty():
                            continue
                        filter_rows = list(
                            filter(
                                lambda x:self._status.validate(name,x.get_val(name)),
                                filter_rows,
                            )
                        )
                    except Exception as e:
                        pass  
                self._filtered_rows = filter_rows

    def update_input(self, row_name, value):
        row_name=row_name.lower()
        try:
            targetNode = self.query_one(f"#{row_name}")
            targetNode.update_table_val(value)
        except:
            None

    def reset_all_inputs(self):
        for ele in self.row_names[1:]:
            ele=ele.lower()
            try:
                self.query_one(f"#{ele}").reset()
            except:
                continue

    def make_table(self):
        with self.mutex:
            table = self.query_one(DataTable)
            table.clear(True)
            table.fixed_rows = 0
            table.zebra_stripes = True
            [
                table.add_column(re.sub("_", " ", ele), key=str(ele))
                for ele in self.row_names
            ]
            for count, row in enumerate(self._filtered_rows):
                table_row=row.get_styled(count=count)
                table.add_row(*table_row,key=str(row.get_val("index")),height=None)
            if len(table.rows) == 0:
                table.add_row("All Items Filtered")
app=InputApp()