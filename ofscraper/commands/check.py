import logging
import re
import asyncio
import textwrap
import httpx
from textual.app import App, ComposeResult
from textual.widgets import Input
from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Button
from textual import events
import ofscraper.utils.args as args_
import ofscraper.db.operations as operations
import ofscraper.api.profile as profile
import ofscraper.utils.auth as auth
import ofscraper.api.timeline as timeline
import ofscraper.api.messages as messages_
import ofscraper.api.posts as posts_
import ofscraper.constants as constants


log = logging.getLogger(__package__)
args = args_.getargs()


def post_checker():
    headers = auth.make_headers(auth.read_auth())
    user_dict = {}
    client = httpx.Client(http2=True, headers=headers)
    for ele in list(filter(lambda x: re.search("onlyfans.com/[a-z]+", x), args.url)):
        name_match = re.search("/([a-z]+$)", ele)
        if name_match:
            user_name=name_match.group(1)
            if not user_dict.get(user_name):
                model_id=profile.get_id(headers,user_name)
                user_dict[user_name] = {}
                user_dict[user_name] = user_dict[user_name] or []
                user_dict[user_name].extend(asyncio.run(timeline.get_timeline_post(headers,model_id)))
                user_dict[user_name].extend(timeline.get_pinned_post(headers,model_id))
                user_dict[user_name].extend(timeline.get_archive_post(headers,model_id))


    for ele in list(filter(lambda x: re.search("onlyfans.com/[0-9]+/[a-z]+", x), args.url)):
        name_match = re.search("/([a-z]+$)", ele)
        num_match = re.search("/([0-9]+)", ele)
        if name_match and num_match:
            model_id=num_match.group(1)
            user_name=name_match.group(1)
            if not user_dict.get(user_name):
                user_dict[name_match.group(1)] = {}
            data = timeline.get_individual_post(model_id, client)
            user_dict[user_name] = user_dict[user_name] or []
            user_dict[user_name].append(data)
    ROWS = get_first_row()
    for user_name in user_dict.keys():
        temp = []
        model_id = profile.get_id(headers, user_name)
        operations.create_tables(model_id,user_name)
        downloaded = set(operations.get_media_ids(model_id, user_name))
        [temp.extend(ele.all_media) for ele in map(lambda x:posts_.Post(
            x, model_id, user_name), user_dict[user_name])]

        ROWS.extend(add_rows(temp,downloaded))


    app = InputApp()
    app.table_data = ROWS
    app.run()


def message_checker():
    url = args.url
    num_match = re.search("/([0-9]+)", args.url)
    headers = auth.make_headers(auth.read_auth())
    ROWS = get_first_row()
    if num_match:
        model_id = num_match.group(1)
        user_name = profile.scrape_profile(headers, model_id)['name']
        operations.create_tables(model_id,user_name)
        downloaded = set(operations.get_media_ids(model_id, user_name))
        messages = asyncio.run(messages_.get_messages(headers,  model_id))
        media = []
        [media.extend(ele.all_media) for ele in map(
            lambda x:posts_.Post(x, model_id, user_name), messages)]
        ROWS.extend(add_rows(media,downloaded))
    app = InputApp()
    app.table_data = ROWS
    app.run()



def get_first_row():
    return [("Number","Downloaded", "TEXT", "PRICE","MEDIA_ID", "POST_ID",)]
def texthelper(text):
    text=textwrap.dedent(text)
    text=re.sub(" +$","",text)
    text=re.sub("^ +","",text)
    text = re.sub("<[^>]*>", "", text) 
    text=text if len(text)<constants.TABLE_STR_MAX else f"{text[:constants.TABLE_STR_MAX]}..."
    return text
def add_rows(media,downloaded):
    #fix text
    for ele in media:   
        return map(lambda x: (x[0],x[1].id in downloaded, texthelper(x[1].text),x[1]._post.price, x[1].id, x[1].postid,), enumerate(media))


class InputApp(App):
    def on_input_submitted(self, event: Input.Submitted) -> None:
        table = self.query("DataTable").last()
        table.clear()
        if len(table.rows)==0:
            table.add_row("All Items Filtered")

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.exit()

    def compose(self) -> ComposeResult:
        yield Vertical(
            Horizontal(
                Input(placeholder="Search"),
                Button("Reset")
            ), DataTable(fixed_rows=1)
        )

    def on_button_pressed(self, event: events.MouseEvent) -> None:
        table = self.query_one(DataTable)
        table.clear(True)
        self.make_table()

    def on_mount(self) -> None:
        self.make_table()
        self.query_one(Input).styles.width = "70%"
        self.query_one(Vertical).styles.width = "100vw"
        self.query_one(Vertical).styles.height = "100vh"
        self.query_one(Horizontal).styles.height = "20%"
        self.query_one(Horizontal).styles.width = "100%"
        self.query_one(DataTable).styles.width = "100%"
        self.query_one(DataTable).styles.height = "70%"



    def make_table(self,value=".*"):
        table = self.query_one(DataTable)
        table.fixed_rows = 1
        table.zebra_stripes=True
        table.add_columns(*self.table_data[0])
        for count, row in enumerate(self.table_data[1:]):
            if re.search(value," ".join(map(lambda x:str(x),row))):
            # Adding styled and justified `Text` objects instead of plain strings.
                styled_row = [
                    Text(str(cell), style="italic #03AC13") for cell in row
                ]
                table.add_row(*styled_row, key=str(count))

