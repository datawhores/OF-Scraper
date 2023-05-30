import logging
import re
import httpx
from textual.app import App, ComposeResult
from textual.widgets import Input
from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable,Button
from textual import events
import ofscraper.utils.args as args_
import ofscraper.utils.console as console
import ofscraper.db.operations as operations
import ofscraper.api.profile as profile
import ofscraper.utils.auth as auth
import ofscraper.api.timeline as timeline
import ofscraper.api.messages as messages
import ofscraper.api.posts as posts_



log=logging.getLogger(__package__)
args=args_.getargs()


   
def post_checker():
    headers = auth.make_headers(auth.read_auth())
    user_dict={}
    client=httpx.Client(http2=True, headers=headers)

    for ele in list(filter(lambda x:re.search("onlyfans.com/[0-9]+/[a-z]+",x),args.url)):
        name_match=re.search("/([a-z]+$)",ele)
        num_match=re.search("/([0-9]+)",ele)
        if name_match and num_match:
            if not user_dict.get(name_match.group(1)):
                user_dict[name_match.group(1)]={}
                post_id=user_dict[name_match.group(1)].get("posts")
                data=timeline.get_individual_post(num_match.group(1),client)
            user_dict[name_match.group(1)]=user_dict[name_match.group(1)] or []
            user_dict[name_match.group(1)].append(data)
    ROWS=[ ("Downloaded","TEXT","MEDIA_ID","POST_ID",)]  
     
    for user_name in user_dict.keys():
        temp=[]
        model_id = profile.get_id(headers, user_name)
        downloaded=set(operations.get_media_ids(model_id,user_name))
        [temp.extend(ele.media) for ele in map(lambda x:posts_.Post(x,model_id,user_name),user_dict[user_name])]

        ROWS.extend(map(lambda x:(x.id in downloaded,x.text,x.id,x.postid,),temp))
    app=InputApp()
    app.table_data=ROWS
    app.run()

        



class InputApp(App):
    def on_input_submitted(self, event: Input.Submitted) -> None:
        table=self.query("DataTable").last()
        keys=list(table.rows.keys())
        for key in keys:
            key=key.value
            row=table.get_row(key)
            rowstring=" ".join(list(map(lambda x:x.plain,row)))
            if not re.search(event.value,rowstring):
                table.remove_row(key)
    def on_key(self, event: events.Key) -> None:
        if event.key=="escape":
            self.exit()
    def compose(self) -> ComposeResult:
        yield Vertical(
        Horizontal(
        Input(placeholder="Search"),
        Button("Reset")
        )
        ,DataTable()
        )

    def on_button_pressed(self, event: events.MouseEvent) -> None:
        table = self.query_one(DataTable)
        table.clear(True)
        self.make_table()
        
    def on_mount(self) -> None:
        self.make_table()
        self.query_one(Input).styles.width="70%"
        self.query_one(Horizontal).styles.height="20%"
    
    

    def make_table(self):
        table = self.query_one(DataTable)
        table.add_columns(*self.table_data[0])
        for count,row in enumerate(self.table_data[1:]):
            # Adding styled and justified `Text` objects instead of plain strings.
            styled_row = [
                Text(str(cell), style="italic #03AC13", justify="right") for cell in row
            ]
            table.add_row(*styled_row,key=str(count))

        

def message_checker():
    for ele in list(filter(lambda x:re.search("onlyfans.com/.*/chats/[0-9]+",x),args.url)):
            num_match=re.search("/([0-9]+)",ele)
            message_checker(num_match)

            

    





