import logging
import re
import asyncio
import textwrap
import httpx
import arrow
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import Input, DataTable, Button, Checkbox, Label
from rich.text import Text
from textual.containers import Horizontal, VerticalScroll
from textual import events
import ofscraper.utils.args as args_
import ofscraper.db.operations as operations
import ofscraper.api.profile as profile
import ofscraper.utils.auth as auth
import ofscraper.api.timeline as timeline
import ofscraper.api.messages as messages_
import ofscraper.api.posts as posts_
import ofscraper.constants as constants
import ofscraper.api.paid as paid_
import ofscraper.api.archive as archive
import ofscraper.api.pinned as pinned
import ofscraper.api.highlights as highlights_


from diskcache import Cache
from ..utils.paths import getcachepath
cache = Cache(getcachepath())

log = logging.getLogger(__package__)
args = args_.getargs()
ROW_NAMES = "Number", "UserName", "Downloaded", "Unlocked", "Times_Detected", "Length", "Mediatype", "Post_Date", "Post_Media_Count", "Responsetype", "Price", "Post_ID", "Media_ID", "Text"
ROWS = []


def post_checker():
    headers = auth.make_headers(auth.read_auth())
    user_dict = {}
    client = httpx.Client(http2=True, headers=headers)
    links = list(url_helper())
    for ele in links:
        name_match = re.search("/([a-z_]+$)", ele)
        if name_match:
            user_name = name_match.group(1)
            log.info(f"Getting Full Timeline for {user_name}")
            model_id = profile.get_id(headers, user_name)
        name_match = re.search("^[a-z]+$", ele)
        if name_match:
            user_name = name_match.group(0)
            model_id = profile.get_id(headers, user_name)

        oldtimeline = cache.get(f"timeline_check_{model_id}", default=[])
        if len(oldtimeline) > 0 and not args.force:
            user_dict[user_name] = oldtimeline
        elif not user_dict.get(user_name):
            user_dict[user_name] = {}
            user_dict[user_name] = user_dict[user_name] or []
            user_dict[user_name].extend(asyncio.run(
                timeline.get_timeline_post(headers, model_id)))
            user_dict[user_name].extend(asyncio.run(
                pinned.get_pinned_post(headers, model_id)))
            user_dict[user_name].extend(asyncio.run(
                archive.get_archived_post(headers, model_id)))
            cache.set(
                f"timeline_check_{model_id}", user_dict[user_name], expire=constants.CHECK_EXPIRY)

    # individual links
    for ele in list(filter(lambda x: re.search("onlyfans.com/[0-9]+/[a-z_]+$", x), links)):
        name_match = re.search("/([a-z]+$)", ele)
        num_match = re.search("/([0-9]+)", ele)
        if name_match and num_match:
            model_id = num_match.group(1)
            user_name = name_match.group(1)
            log.info(f"Getting Invidiual Link for {user_name}")

            if not user_dict.get(user_name):
                user_dict[name_match.group(1)] = {}
            data = timeline.get_individual_post(model_id, client)
            user_dict[user_name] = user_dict[user_name] or []
            user_dict[user_name].append(data)

    ROWS=[]
    for user_name in user_dict.keys():
        downloaded = get_downloaded(user_name, model_id)
        media = get_all_found_media(user_name, user_dict[user_name])
        ROWS.extend(row_gather(media, downloaded, user_name))
    app_run_helper(ROWS)



def message_checker():
    links = list(url_helper())
    user_dict = {}
    ROWS=[]
    for item in links:
        num_match = re.search("/([0-9]+)", item)
        headers = auth.make_headers(auth.read_auth())
        if num_match:
            model_id = num_match.group(1)
            user_name = profile.scrape_profile(headers, model_id)['username']
        name_match = re.search("^[a-z_.]+$", item)
        if name_match:
            user_name = name_match.group(0)
            model_id = profile.get_id(headers, user_name)     
        user_dict[user_name] = user_dict.get(user_name, [])
        log.info(f"Getting Messages for {user_name}")
        messages = None
        oldmessages = cache.get(f"message_check_{model_id}", default=[])

        
        if len(oldmessages) > 0 and not args.force:
            messages = oldmessages
        else:
            messages = asyncio.run(
                messages_.get_messages(headers,  model_id))
            cache.set(f"message_check_{model_id}",
                        messages, expire=constants.CHECK_EXPIRY)
        media = get_all_found_media(user_name, messages)
        downloaded = get_downloaded(user_name, model_id)
        ROWS.extend(row_gather(media, downloaded, user_name))

    app_run_helper(ROWS)



def purchase_checker():
    user_dict = {}
    headers = auth.make_headers(auth.read_auth())
    ROWS = []
    for user_name in args.username:
        user_dict[user_name] = user_dict.get(user_name, [])
        model_id = profile.get_id(headers, user_name)
        oldpaid = cache.get(f"purchased_check_{model_id}", default=[])
        paid = None
        
        if len(oldpaid) > 0 and not args.force:
            paid = oldpaid
        else:
            paid = asyncio.run(paid_.get_paid_posts(user_name, model_id))
            cache.set(f"purchased_check_{model_id}",
                      paid, expire=constants.CHECK_EXPIRY)
        downloaded = get_downloaded(user_name, model_id)
        media = get_all_found_media(user_name, paid)
        ROWS.extend(row_gather(media, downloaded, user_name))

    app_run_helper(ROWS)


def stories_checker():
    user_dict = {}
    headers = auth.make_headers(auth.read_auth())
    ROWS=[]
    for user_name in args.username:
        user_dict[user_name] = user_dict.get(user_name, [])
        model_id = profile.get_id(headers, user_name)    
        highlights, stories = asyncio.run(highlights_.get_highlight_post(headers, model_id))
        highlights=list(map(lambda x:posts_.Post(
        x, model_id, user_name,"highlights"), highlights))
        stories=list(map(lambda x:posts_.Post(
        x, model_id, user_name,"stories"), stories))
            

     
        downloaded = get_downloaded(user_name, model_id)
        media=[]
        [media.extend(ele.all_media) for ele in stories+highlights]
        ROWS.extend(row_gather(media, downloaded, user_name))

    app_run_helper(ROWS)

  


def url_helper():
    out = []
    out.extend(args.file or [])
    out.extend(args.url or [])
    return map(lambda x: x.strip(), out)


def get_all_found_media(user_name, posts):
    headers = auth.make_headers(auth.read_auth())

    temp = []
    model_id = profile.get_id(headers, user_name)
    posts_array=list(map(lambda x:posts_.Post(
        x, model_id, user_name), posts))
    [temp.extend(ele.all_media) for ele in posts_array]
    return temp




def get_downloaded(user_name, model_id):
    downloaded = {}
    operations.create_tables(model_id, user_name)
    [downloaded.update({ele: downloaded.get(ele, 0)+1})
     for ele in operations.get_media_ids(model_id, user_name)+get_paid_ids(model_id,user_name)]
    
    return downloaded

def get_paid_ids(model_id,user_name):
    oldpaid = cache.get(f"purchased_check_{model_id}", default=[])
    paid = None
        
    if len(oldpaid) > 0 and not args.force:
         paid = oldpaid
    else:
        paid = asyncio.run(paid_.get_paid_posts(user_name, model_id))
        cache.set(f"purchased_check_{model_id}",
                      paid, expire=constants.CHECK_EXPIRY)
    media = get_all_found_media(user_name, paid)
    media=list(filter(lambda x:x.canview==True,media))
    return list(map(lambda x:x.id,media))


def app_run_helper(ROWS_):
    ROWS = get_first_row()
    ROWS.extend(ROWS_)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app = InputApp()
    # we have to set properies before run
    app.table_data = ROWS
    app.row_names = ROW_NAMES
    app.set_filtered_rows(reset=True)
    app.run()


def get_first_row():
    return [ROW_NAMES]


def texthelper(text):
    text=text or ""
    text = textwrap.dedent(text)
    text = re.sub(" +$", "", text)
    text = re.sub("^ +", "", text)
    text = re.sub("<[^>]*>", "", text)
    text = text if len(
        text) < constants.TABLE_STR_MAX else f"{text[:constants.TABLE_STR_MAX]}..."
    return text


def unlocked_helper(ele):
    return ele.canview


def datehelper(date):
    if date == "None":
        return "Probably Deleted"
    return date


def times_helper(ele, mediadict, downloaded):
    return max(len(mediadict.get(ele.id, [])), downloaded.get(ele.id, 0))
  
def row_gather(media, downloaded, username):

    # fix text

    mediadict = {}
    [mediadict.update({ele.id: mediadict.get(ele.id, []) + [ele]})
     for ele in list(filter(lambda x:x.canview,media))]
    out = []
    media = sorted(media, key=lambda x: arrow.get(x.date), reverse=True)
    for count, ele in enumerate(media):
        out.append((count+1, username, ele.id in downloaded or cache.get(ele.postid)!=None or  cache.get(ele.filename)!=None , unlocked_helper(ele), times_helper(ele, mediadict, downloaded), ele.length_, ele.mediatype, datehelper(
            ele.postdate_), len(ele._post.post_media), ele.responsetype_, "Free" if ele._post.price == 0 else "{:.2f}".format(ele._post.price),  ele.postid, ele.id, texthelper(ele.text)))
    return out


class StyledButton(Button):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)


class StringField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield Input(placeholder=f"{self.filter_name.capitalize()} Search", id=f"{self.filter_name}_search")
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
        elif self.query_one(Checkbox).value and re.fullmatch(self.query_one(Input).value, str(val), (re.IGNORECASE if self.query_one(Input).islower() else 0)):
            return True
        elif not self.query_one(Checkbox).value and re.search(self.query_one(Input).value, str(val), (re.IGNORECASE if self.query_one(Input).value.islower() else 0)):
            return True
        return False


class NumField(Horizontal):
    def __init__(self, name: str) -> None:
        super().__init__(id=name)
        self.filter_name = name

    def compose(self):
        yield self.IntegerInput(placeholder=self.filter_name.capitalize(), id=f"{self.filter_name}_search")

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
            *args, **kwargs
            # ---snip---
        ) -> None:
            super().__init__(
                # ---snip---
                *args, **kwargs
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
        yield self.IntegerInput(placeholder="Min Price", id=f"{self.filter_name}_search")
        yield self.IntegerInput(placeholder="Max Price", id=f"{self.filter_name}_search2")

    def empty(self):
        return self.query(self.IntegerInput)[0].value == "" and self.query(self.IntegerInput)[1].value == ""

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
            *args, **kwargs
            # ---snip---
        ) -> None:
            super().__init__(
                # ---snip---
                *args, **kwargs
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
        self.timeconversions = [60*60, 60, 1]

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
        return len(list(filter(lambda x: x.value != "", self.query(self.IntegerInput)))) == 0

    def on_mount(self):
        for ele in self.query_one("#minLength").query(self.IntegerInput):
            ele.styles.width = "1fr"
        for ele in self.query_one("#maxLength").query(self.IntegerInput):
            ele.styles.width = "1fr"
        self.styles.height = "auto"
        self.styles.width = "2fr"

    def update_table_val(self, val):
        minLenthInputs = list(self.query_one(
            "#minLength").query(self.IntegerInput))
        maxLenthInputs = list(self.query_one(
            "#maxLength").query(self.IntegerInput))
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
            total = sum([(int(a[i] or 0)*self.timeconversions[i])
                        for i in range(len(a))])
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
        if len(list(filter(lambda x: x.value != "", self.query_one("#minLength").query(self.IntegerInput)))) == 0:
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
        if len(list(filter(lambda x: x.value != "", self.query_one("#maxLength").query(self.IntegerInput)))) == 0:
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
            *args, **kwargs
            # ---snip---
        ) -> None:
            super().__init__(
                # ---snip---
                *args, **kwargs
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
        [setattr(ele, "styles.width", f"{int(100/count)}%")
         for ele in self.query(Checkbox)]

    def compose(self):
        yield Checkbox(f"{self.filter_name.capitalize()} True", True, id=f"{self.filter_name}_search")
        yield Checkbox(f"{self.filter_name.capitalize()} False", True, id=f"{self.filter_name}_search2")
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
        return self.query(Checkbox)[0].value == False and self.query(Checkbox)[1].value == False

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
        return self.query(Checkbox)[0].value == False and self.query(Checkbox)[1].value == False and self.query(Checkbox)[2].value == False

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
        elif val == "videos" and not self.query_one(f"#{self.filter_name}_search2").value:
            return False
        elif val == "images" and not self.query_one(f"#{self.filter_name}_search3").value:
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

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.exit()
        if event.key == "end":
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
            self.update_input(row_name, event.value.plain)
            self.set_filtered_rows()
            self.make_table()
        # if event.key=="enter" and arrow.now().float_timestamp-self._lastclick.float_timestamp>3:
        #     self._lastclick=arrow.now()
        #     self.set_filtered_rows()
        #     self.make_table()

    def compose(self) -> ComposeResult:
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
        yield DataTable(fixed_rows=1, id="data-table_page")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self.set_filtered_rows()
            self.sort_helper()
            self.make_table()
        elif event.button.id == "reset":
            self.set_filtered_rows(reset=True)
            self.reset_all_inputs()
            self.set_reverse(init=True)
            self.make_table()

    def on_data_table_header_selected(self, event):
        self.sort_helper(event.label.plain)

        # set reverse
        # use native python sorting until textual has key support

    def sort_helper(self, label=None):
        # to allow sorting after submit
        if label != None:
            self.set_reverse(label=label)
        if label == "Number":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: x[0], reverse=self.reverse)
            self.make_table()
        elif label == "Username":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: x, reverse=self.reverse)
            self.make_table()
        elif label == "Downloaded":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: 1 if x[2] == True else 0, reverse=self.reverse)
            self.make_table()

        elif label == "Unlocked":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: 1 if x[3] == True else 0, reverse=self.reverse)
            self.make_table()
        elif label == "Times Detected":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: 1 if x[4] == True else 0, reverse=self.reverse)
            self.make_table()
        elif label == "Length":
            helperNode = self.query_one("#Length")
            self._filtered_rows = sorted(self._filtered_rows, key=lambda x: helperNode.convertString(
                x[5]) if x[5] != "N/A" else 0, reverse=self.reverse)
            self.make_table()
        elif label == "Mediatype":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: x[6], reverse=self.reverse)
            self.make_table()
        elif label == "Post Date":
            helperNode = self.query_one("#Post_Date")
            self._filtered_rows = sorted(self._filtered_rows, key=lambda x: helperNode.convertString(
                x[7]) if x[7] != "N/A" else 0, reverse=self.reverse)
            self.make_table()
        elif label == "Post Media Count":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: x[8], reverse=self.reverse)
            self.make_table()

        elif label == "Responsetype":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: x[9], reverse=self.reverse)
            self.make_table()
        elif label == "Price":
            self._filtered_rows = sorted(self._filtered_rows, key=lambda x: int(
                float(x[10])) if x[10] != "Free" else 0, reverse=self.reverse)
            self.make_table()

        elif label == "Post ID":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: x[11], reverse=self.reverse)
            self.make_table()
        elif label == "Media ID":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: x[12], reverse=self.reverse)
            self.make_table()
        elif label == "Text":
            self._filtered_rows = sorted(
                self._filtered_rows, key=lambda x: x[13], reverse=self.reverse)
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

    def on_mount(self) -> None:
        self._lastclick = arrow.now()
        self.set_reverse(init=True)
        self.make_table()
        self.query_one("#reset").styles.align = ("center", "middle")
        self.query_one(VerticalScroll).styles.height = "35vh"
        self.query_one(VerticalScroll).styles.dock = "top"
        self.query_one(DataTable).styles.height = "60vh"

        for ele in self.query(Horizontal)[:-1]:
            ele.styles.height = "10vh"

    def set_filtered_rows(self, reset=False):
        if reset == True:
            self._filtered_rows = self.table_data[1:]
        else:
            rows = self.table_data[1:]
            for count, name in enumerate(self.row_names[1:]):
                try:
                    targetNode = self.query_one(f"#{name}")
                    if targetNode.empty():
                        continue
                    rows = list(
                        filter(lambda x: targetNode.validate(x[count+1]) == True, rows))
                except:
                    None
            self._filtered_rows = rows

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
        table = self.query_one(DataTable)
        table.clear(True)
        table.fixed_rows = 0
        table.zebra_stripes = True
        [table.add_column(re.sub("_", " ", ele), key=str(ele))
         for ele in self.table_data[0]]
        for count, row in enumerate(self._filtered_rows):
            # Adding styled and justified `Text` objects instead of plain strings.
            styled_row = [
                Text(str(cell), style="italic #03AC13") for cell in row
            ]
            table.add_row(*styled_row, key=str(count+1))

        if len(table.rows) == 0:
            table.add_row("All Items Filtered")
        table.cursor_coordinate = Coordinate(0, 0)
