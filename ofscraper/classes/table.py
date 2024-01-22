import logging
import re

import arrow
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    DataTable,
    Input,
    Label,
    TextLog,
)

import ofscraper.utils.logs.logger as logger

log = logging.getLogger("shared")


# console=console_.get_shared_console()
class OutConsole(TextLog):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class StyledButton(Button):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class StringField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield Input(
            placeholder=f"{self.filter_name.capitalize()} Search",
            id=f"{self.filter_name}_search",
        )
        yield Checkbox(f"FullString", False, id="fullstring_search")

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.width = "2fr"
        self.query_one(Input).styles.width = "4fr"
        self.query_one(Checkbox).styles.width = "1fr"

    def empty(self):
        return self.query_one(Input).value == ""

    def update_table_val(self, val):
        self.query_one(Input).value = val

    def reset(self):
        self.query_one(Input).value = ""

    def validate(self, val):
        if self.query_one(Input).value == "" or self.query_one(Input).value == None:
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
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield self.IntegerInput(
            placeholder=self.filter_name.capitalize().replace("_", " "),
            id=f"{self.filter_name}_search",
        )

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.width = "1fr"

    def empty(self):
        return self.query_one(self.IntegerInput).value == ""

    def update_table_val(self, val):
        self.query_one(self.IntegerInput).value = val

    def reset(self):
        self.query_one(self.IntegerInput).value = ""

    def validate(self, val):
        if self.query_one(self.IntegerInput).value == "":
            return True
        if int(val) == int(self.query_one(self.IntegerInput).value):
            return True
        return False

    class IntegerInput(Input):
        def __init__(
            self,
            *args,
            **kwargs
            # ---snip---
        ) -> None:
            super().__init__(
                # ---snip---
                *args,
                **kwargs,
            )

        def insert_text_at_cursor(self, text: str) -> None:
            try:
                int(text)
            except ValueError:
                pass
            else:
                super().insert_text_at_cursor(text)


class PriceField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield self.IntegerInput(
            placeholder="Min Price", id=f"{self.filter_name}_search"
        )
        yield self.IntegerInput(
            placeholder="Max Price", id=f"{self.filter_name}_search2"
        )

    def empty(self):
        return (
            self.query(self.IntegerInput)[0].value == ""
            and self.query(self.IntegerInput)[1].value == ""
        )

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.width = "1fr"
        for ele in self.query(self.IntegerInput):
            ele.styles.width = "1fr"

    def update_table_val(self, val):
        if val.lower() == "free":
            val = "0"
        for ele in self.query(self.IntegerInput):
            ele.value = val

    def reset(self):
        self.query_one(self.IntegerInput).value = ""

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

    class IntegerInput(Input):
        def __init__(
            self,
            *args,
            **kwargs
            # ---snip---
        ) -> None:
            super().__init__(
                # ---snip---
                *args,
                **kwargs,
            )

        def insert_text_at_cursor(self, text: str) -> None:
            try:
                if text != ".":
                    int(text)
            except ValueError:
                pass
            else:
                super().insert_text_at_cursor(text)


class TimeField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name)
        self.filter_name = name
        self.timeconversions = [60 * 60, 60, 1]

    def compose(self):
        with Horizontal(id="minLength"):
            yield Label("MinLength")
            yield self.IntegerInput(placeholder="Hour")
            yield self.IntegerInput(placeholder="Min")
            yield self.IntegerInput(placeholder="Sec")
        with Horizontal(id="maxLength"):
            yield Label("MaxLength")
            yield self.IntegerInput(placeholder="Hour")
            yield self.IntegerInput(placeholder="Min")
            yield self.IntegerInput(placeholder="Sec")

    def empty(self):
        return (
            len(list(filter(lambda x: x.value != "", self.query(self.IntegerInput))))
            == 0
        )

    def on_mount(self):
        for ele in self.query_one("#minLength").query(self.IntegerInput):
            ele.styles.width = "1fr"
        for ele in self.query_one("#maxLength").query(self.IntegerInput):
            ele.styles.width = "1fr"
        self.styles.height = "auto"
        self.styles.width = "2fr"

    def update_table_val(self, val):
        minLenthInputs = list(self.query_one("#minLength").query(self.IntegerInput))
        maxLenthInputs = list(self.query_one("#maxLength").query(self.IntegerInput))
        valArray = val.split(":")
        for pack in zip(maxLenthInputs, minLenthInputs, valArray):
            pack[0].value = pack[2]
            pack[1].value = pack[2]

    def reset(self):
        for ele in self.query(self.IntegerInput):
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
                        self.query_one("#minLength").query(self.IntegerInput),
                    )
                )
            )
            == 0
        ):
            return True
        for ele in self.query_one("#minLength").query(self.IntegerInput):
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
                        self.query_one("#maxLength").query(self.IntegerInput),
                    )
                )
            )
            == 0
        ):
            return True
        for ele in self.query_one("#maxLength").query(self.IntegerInput):
            comparestr = f"{comparestr}{ele.value}:"
        comparestr = comparestr[:-1]
        if self.convertString(val) > self.convertString(comparestr):
            return False
        return True

    class IntegerInput(Input):
        def __init__(
            self,
            *args,
            **kwargs
            # ---snip---
        ) -> None:
            super().__init__(
                # ---snip---
                *args,
                **kwargs,
            )

        def insert_text_at_cursor(self, text: str) -> None:
            try:
                if not text.isdigit():
                    raise ValueError
                if len(self.value) == 2:
                    raise ValueError

            except ValueError:
                pass
            else:
                super().insert_text_at_cursor(text)

        def on_mount(self):
            self.styles.width = "50%"


class BoolField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name, classes="container")
        self.filter_name = name

    def on_mount(self):
        count = len(self.query(Checkbox))
        [
            setattr(ele, "styles.width", f"{int(100/count)}%")
            for ele in self.query(Checkbox)
        ]

    def compose(self):
        yield Checkbox(
            f"{self.filter_name.capitalize()} True",
            True,
            id=f"{self.filter_name}_search",
        )
        yield Checkbox(
            f"{self.filter_name.capitalize()} False",
            True,
            id=f"{self.filter_name}_search2",
        )
        self.styles.height = "auto"
        self.styles.width = "1fr"

    def update_table_val(self, val):
        if val == "True":
            self.query_one(f"#{self.filter_name}_search").value = True
            self.query_one(f"#{self.filter_name}_search2").value = False
        elif val == "False":
            self.query_one(f"#{self.filter_name}_search2").value = True
            self.query_one(f"#{self.filter_name}_search").value = False

    def empty(self):
        return (
            self.query(Checkbox)[0].value == False
            and self.query(Checkbox)[1].value == False
        )

    def reset(self):
        for ele in self.query(Checkbox):
            ele.value = True

    def validate(self, val):
        if val == True and not self.query_one(f"#{self.filter_name}_search").value:
            return False
        elif val == False and not self.query_one(f"#{self.filter_name}_search2").value:
            return False

        return True


class MediaField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name, classes="container")
        self.filter_name = name

    def on_mount(self):
        [setattr(ele, "styles.width", "30%") for ele in self.query(Checkbox)]

    def compose(self):
        yield Checkbox("audios", True, id=f"{self.filter_name}_search")
        yield Checkbox("videos", True, id=f"{self.filter_name}_search2")
        yield Checkbox("Images", True, id=f"{self.filter_name}_search3")
        self.styles.height = "auto"
        self.styles.width = "1fr"

    def empty(self):
        return (
            self.query(Checkbox)[0].value == False
            and self.query(Checkbox)[1].value == False
            and self.query(Checkbox)[2].value == False
        )

    def update_table_val(self, val):
        if val == "audios":
            self.query_one(f"#{self.filter_name}_search").value = True
            self.query_one(f"#{self.filter_name}_search2").value = False
            self.query_one(f"#{self.filter_name}_search3").value = False
        elif val == "videos":
            self.query_one(f"#{self.filter_name}_search2").value = True
            self.query_one(f"#{self.filter_name}_search3").value = False
            self.query_one(f"#{self.filter_name}_search").value = False
        elif val == "images":
            self.query_one(f"#{self.filter_name}_search3").value = True
            self.query_one(f"#{self.filter_name}_search").value = False
            self.query_one(f"#{self.filter_name}_search2").value = False

    def reset(self):
        for ele in self.query(Checkbox):
            ele.value = True

    def validate(self, val):
        if val == "audios" and not self.query_one(f"#{self.filter_name}_search").value:
            return False
        elif (
            val == "videos" and not self.query_one(f"#{self.filter_name}_search2").value
        ):
            return False
        elif (
            val == "images" and not self.query_one(f"#{self.filter_name}_search3").value
        ):
            return False
        return True


class DateField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name, classes="container")
        self.filter_name = name

    def compose(self):
        yield Input(placeholder="Earliest Date", id=f"minDate")
        yield Input(placeholder="Latest Date", id=f"maxDate")

    def empty(self):
        return self.query(Input)[0].value == "" and self.query(Input)[1].value == ""

    def on_mount(self):
        self.styles.height = "auto"
        self.styles.width = "1fr"
        for ele in self.query(Input):
            ele.styles.width = "1fr"

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


class InputApp(App):
    # Events
    def on_data_table_header_selected(self, event):
        self._current_added = self.get_current_added_rows()
        self.sort_helper(event.label.plain)
        self.restore_added_rows()

        # set reverse
        # use native python sorting until textual has key support

    def on_data_table_cell_selected(self, event):
        table = self.query_one(DataTable)
        cursor_coordinate = table.cursor_coordinate
        if cursor_coordinate[1] == self.row_names.index("Download_Cart"):
            self.change_download_cart(event.coordinate)

        # set reverse
        # use native python sorting until textual has key support

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self._current_added = self.get_current_added_rows()
            self.set_filtered_rows()
            self.sort_helper()
            self.make_table()
            self.restore_added_rows()
        elif event.button.id == "reset":
            self.set_filtered_rows(reset=True)
            self.reset_all_inputs()
            self.set_reverse(init=True)
            self.make_table()
        elif event.button.id == "send_downloads":
            log.info("Adding Downloads to queue")
            self.add_to_row_queue()
            self.query_one(ContentSwitcher).current = "console_page"

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
                self._current_added = self.get_current_added_rows()
                self.update_input(row_name, event.value.plain)
                self.set_filtered_rows()
                self.make_table()
                self.restore_added_rows()
            else:
                self.change_download_cart(event.coordinate)

    # Main
    def compose(self) -> ComposeResult:
        with Horizontal(id="buttons"):
            yield Button("DataTable", id="table")
            yield Button("Console", id="console")

        with ContentSwitcher(initial="table_page"):
            with Vertical(id="table_page"):
                with VerticalScroll():
                    with Horizontal():
                        for ele in ["Text"]:
                            yield StringField(ele)
                        for ele in ["Times_Detected"]:
                            yield NumField(ele)
                        for ele in ["Media_ID", "Post_ID", "Post_Media_Count"]:
                            yield NumField(ele)
                    with Horizontal():
                        for ele in ["Price"]:
                            yield PriceField(ele)
                        for ele in ["Post_Date"]:
                            yield DateField(ele)
                        for ele in ["Length"]:
                            yield TimeField(ele)

                    with Horizontal():
                        for ele in ["Downloaded", "Unlocked"]:
                            yield BoolField(ele)
                        for ele in ["Mediatype"]:
                            yield MediaField(ele)
                with Horizontal(id="data"):
                    yield StyledButton("Submit", id="submit")
                    yield StyledButton("Reset", id="reset")
                    yield StyledButton(
                        ">> Send Downloads to OF-Scraper", id="send_downloads"
                    )
                yield DataTable(fixed_rows=1, id="data-table_page")
            with Vertical(id="console_page"):
                yield OutConsole()

    def on_mount(self) -> None:
        self.set_reverse(init=True)
        self.set_cart_toggle(init=True)
        self.make_table()
        self.query_one("#reset").styles.align = ("center", "middle")
        self.query_one(VerticalScroll).styles.height = "25vh"
        self.query_one(VerticalScroll).styles.dock = "top"
        self.query_one(DataTable).styles.height = "60vh"
        self.query_one("#send_downloads").styles.content_align = ("right", "middle")
        for ele in self.query(Horizontal)[:-1]:
            ele.styles.height = "10vh"
        logger.add_widget(self.query_one("#console_page").query_one(OutConsole))

    # Cart
    def change_download_cart(self, coord):
        table = self.query_one(DataTable)
        Download_Cart = table.get_row_at(coord[0])[
            self.row_names.index("Download_Cart")
        ]
        if Download_Cart.plain == "Not Unlocked":
            return
        elif Download_Cart.plain == "[]":
            self.update_downloadcart_cell_coord(coord, "[added]")

        elif Download_Cart.plain == "[added]":
            self.update_downloadcart_cell_coord(coord, "[]")

        elif Download_Cart.plain == "[downloaded]" or "[failed]":
            self.update_downloadcart_cell_coord(coord, "[]")

    def add_to_row_queue(self):
        table = self.query_one(DataTable)
        keys = [str(ele[0]) for ele in self._filtered_rows]
        index = self.row_names.index("Download_Cart")
        filter_keys = list(
            filter(lambda x: table.get_row(x)[index].plain == "[added]", keys)
        )
        self.update_downloadcart_cell(filter_keys, "[downloading]")
        log.info(f"Number of Downloads sent to queue {len(filter_keys)}")
        [
            self.row_queue.put(ele)
            for ele in map(lambda x: (table.get_row(x), x), filter_keys)
        ]

    def get_current_added_rows(self):
        table = self.query_one(DataTable)
        keys = [str(ele[0]) for ele in self._filtered_rows]
        index = self.row_names.index("Download_Cart")
        filter_keys = list(
            filter(lambda x: table.get_row(x)[index].plain == "[added]", keys)
        )
        return filter_keys

    def restore_added_rows(self):
        table = self.query_one(DataTable)
        currentkeys = set(map(lambda x: x.value, table.rows.keys()))
        [
            table.update_cell(key, "Download_Cart", Text("[added]"))
            for key in filter(lambda x: x in currentkeys, self._current_added)
        ]

    def reset_cart(self):
        index = self.row_names.index("Download_Cart")
        self.update_downloadcart_cell(
            [
                str(x[0])
                for x in list(
                    filter(lambda x: x[index] == "[added]", self.table_data[1:])
                )
            ],
            "[]",
        )

    def reset_filtered_cart(self):
        index = self.row_names.index("Download_Cart")
        self.update_downloadcart_cell(
            list(filter(lambda x: x[index] != "Not Unlocked", self._filtered_rows)),
            "[]",
        )

    def update_downloadcart_cell_coord(self, keys, value):
        index = self.row_names.index("Download_Cart")
        if not isinstance(keys, list):
            keys = [keys]
        with self.mutex:
            for key in keys:
                try:
                    table = self.query_one(DataTable)
                    table.update_cell_at(key, Text(value))
                    # table.ordered_rows gets the keys in table order
                    self.table_data[int(table.ordered_rows[keys[0]].key.value)][
                        index
                    ] = value

                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)

    def update_downloadcart_cell(self, keys, value):
        self.update_cell(keys, "Download_Cart", value)

    def update_cell(self, keys, name, value, perst=True):
        index = self.row_names.index(name)
        if not isinstance(keys, list):
            keys = [keys]
        with self.mutex:
            for key in keys:
                try:
                    if perst:
                        self.table_data[int(key)][index] = value
                    table = self.query_one(DataTable)
                    table.update_cell(key, name, Text(str(value)))
                except Exception as E:
                    log.debug("Row was probably removed")
                    log.debug(E)

    # Table Functions

    def sort_helper(self, label=None):
        # to allow sorting after submit
        if label == None:
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

            # [table.update_cell(key,"Download_Cart",self.cart_toggle) for key in filter_keys]

        elif label != "Download Cart":
            index = self.row_names.index(re.sub(" ", "_", label))

            self.set_reverse(label=label)

            if label == "Number":
                self._filtered_rows = sorted(
                    self._filtered_rows, key=lambda x: x[index], reverse=self.reverse
                )
                self.make_table()
            elif label == "UserName":
                self._filtered_rows = sorted(
                    self._filtered_rows, key=lambda x: x[index], reverse=self.reverse
                )
                self.make_table()
            elif label == "Downloaded":
                self._filtered_rows = sorted(
                    self._filtered_rows,
                    key=lambda x: 1 if x[index] == True else 0,
                    reverse=self.reverse,
                )
                self.make_table()

            elif label == "Unlocked":
                self._filtered_rows = sorted(
                    self._filtered_rows,
                    key=lambda x: 1 if x[index] == True else 0,
                    reverse=self.reverse,
                )
                self.make_table()
            elif label == "Times Detected":
                self._filtered_rows = sorted(
                    self._filtered_rows,
                    key=lambda x: 1 if x[index] == True else 0,
                    reverse=self.reverse,
                )
                self.make_table()
            elif label == "Length":
                helperNode = self.query_one("#Length")
                self._filtered_rows = sorted(
                    self._filtered_rows,
                    key=lambda x: helperNode.convertString(x[index])
                    if x[index] != "N/A"
                    else 0,
                    reverse=self.reverse,
                )
                self.make_table()
            elif label == "Mediatype":
                self._filtered_rows = sorted(
                    self._filtered_rows, key=lambda x: x[index], reverse=self.reverse
                )
                self.make_table()
            elif label == "Post Date":
                helperNode = self.query_one("#Post_Date")
                self._filtered_rows = sorted(
                    self._filtered_rows,
                    key=lambda x: helperNode.convertString(x[index])
                    if x[index] != "N/A"
                    else 0,
                    reverse=self.reverse,
                )
                self.make_table()
            elif label == "Post Media Count":
                self._filtered_rows = sorted(
                    self._filtered_rows, key=lambda x: x[index], reverse=self.reverse
                )
                self.make_table()

            elif label == "Responsetype":
                self._filtered_rows = sorted(
                    self._filtered_rows, key=lambda x: x[index], reverse=self.reverse
                )
                self.make_table()
            elif label == "Price":
                self._filtered_rows = sorted(
                    self._filtered_rows,
                    key=lambda x: int(float(x[index])) if x[index] != "Free" else 0,
                    reverse=self.reverse,
                )
                self.make_table()

            elif label == "Post ID":
                self._filtered_rows = sorted(
                    self._filtered_rows,
                    key=lambda x: x[index] if x[index] else 0,
                    reverse=self.reverse,
                )
                self.make_table()
            elif label == "Media ID":
                self._filtered_rows = sorted(
                    self._filtered_rows,
                    key=lambda x: x[index] if x[index] else 0,
                    reverse=self.reverse,
                )
                self.make_table()
            elif label == "Text":
                self._filtered_rows = sorted(
                    self._filtered_rows, key=lambda x: x[index], reverse=self.reverse
                )
                self.make_table()

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
        if reset == True:
            self._filtered_rows = self.table_data[1:]
            self.reset_cart()
        else:
            filter_rows = self.table_data[1:]
            for count, name in enumerate(self.row_names[1:]):
                try:
                    targetNode = self.query_one(f"#{name}")
                    if targetNode.empty():
                        continue
                    filter_rows = list(
                        filter(
                            lambda x: targetNode.validate(x[count + 1]) == True,
                            filter_rows,
                        )
                    )
                except:
                    None
            self._filtered_rows = filter_rows
        self.reset_filtered_cart()

    def update_input(self, row_name, value):
        try:
            targetNode = self.query_one(f"#{row_name}")
            targetNode.update_table_val(value)
        except:
            None

    def reset_all_inputs(self):
        for ele in self.row_names[1:]:
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
                for ele in self.table_data[0]
            ]
            for count, row in enumerate(self._filtered_rows):
                # Adding styled and justified `Text` objects instead of plain strings.
                styled_row = [(Text(str(count + 1)))]
                styled_row.extend(
                    Text(str(cell), style="italic #03AC13") for cell in row[1:]
                )
                table.add_row(*styled_row, key=str(row[0]))

            if len(table.rows) == 0:
                table.add_row("All Items Filtered")
