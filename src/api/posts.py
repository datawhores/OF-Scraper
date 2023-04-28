from ..utils.config import read_config
import re
from ..constants import TEXTLENGTH_DEFAULT
import src.utils.args as args_
config = read_config()['config']


class Post():
    def __init__(self, post, model_id, username, responsetype=None):
        self._post = post
        self._model_id = model_id
        self._username = username
        self._responsetype_ = responsetype or post.get("responseType")

    @property
    def allmedia(self):
        if self._responsetype_ == "highlights":
            return [{"url": self.post["cover"], "type":"photo"}]
        return self._post.get("media") or []

    @property
    def post(self):
        return self._post

    @property
    def model_id(self):
        return self._model_id

    @property
    def username(self):
        return self._username

    @property
    def archived(self):
        if self.post.get("isArchived"):
            return 1
        return 0

    @property
    def text(self):
        if self._responsetype_ == "highlights":
            return ""
        elif self._responsetype_ == "stories":
            return ""
        return self._post.get("text")

    @property
    def title(self):
        return self._post.get("title")

    # original responsetype for database
    @property
    def responsetype_(self):
        return self._responsetype_

    @property
    def responsetype(self):
        if self.archived:
            if config.get("responsetype", {}).get("archived") == "":
                return "achived"
            elif config.get("responsetype", {}).get("archived") == None:
                return "achived"
            elif config.get("responsetype", {}).get("archived") != "":
                return config.get("responsetype", {}).get("archived")
        else:
            if config.get("responsetype", {}).get(self._responsetype_) == "":
                return self._responsetype_
            elif config.get("responsetype", {}).get(self._responsetype_) == None:
                return self._responsetype_
            elif config.get("responsetype", {}).get(self._responsetype_) != "":
                return config.get("responsetype", {}).get(self._responsetype_)

    @property
    def id(self):
        return self._post["id"]

    @property
    def date(self):
        return self._post.get("createdAt") or self._post.get("postedAt")

    @property
    def value(self):
        if self.price == 0:
            return "free"
        elif self.price > 0:
            return "paid"

    @property
    def price(self):
        return float(self.post.get('price') or 0)

    @property
    def paid(self):
        if (self.post.get("isOpen") or self.post.get("isOpened") or len(self.media) > 0 or self.price != 0):
            return True
        return False

    @property
    def fromuser(self):
        if self._post.get("fromUser"):
            return self._post["fromUser"]["id"]
        else:
            return self._model_id

    @property
    def preview(self):
        return self._post.get("preview")

    @property
    def media(self):
        if (self.fromuser != self.model_id):
            return []
        else:
            media = map(lambda x: Media(
                x[1], x[0], self), enumerate(self.allmedia))
            return list(filter(lambda x: x.canview == True, media))


class Media():
    def __init__(self, media, count, post):
        self._media = media
        self._count = count
        self._post = post

    @property
    def mediatype(self):
        if self.responsetype_ == "highlights":
            return "images"
        if self._media["type"] == "gif" or self._media["type"] == "photo":
            return "images"
        else:
            return f"{self._media['type']}s"

    @property
    def url(self):
        if self.responsetype_ == "stories":
            return self._media.get("files", {}).get("source", {}).get("url")
        elif self.responsetype_ == "highlights":
            return self._media.get("url")
        elif self.responsetype_ == "profile":
            return self._media.get("url")
        else:
            return self._media.get("source", {}).get("source")

    @property
    def post(self):
        return self._post

    @property
    def id(self):
        return self._media["id"]

    # ID for use in dynamic names
    @property
    def id_(self):
        if self.count != None and len(self._post.allmedia) > 1:
            return f"{self._post._post['id']}_{self.count}"
        return self._post._post['id']

    @property
    def canview(self):
        if self.responsetype_ == "highlights":
            return True
        return self._media.get("canView") or False

    @property
    def responsetype(self):
        return self._post.responsetype

    @property
    def responsetype_(self):
        return self._post.responsetype_

    @property
    def value(self):
        return self._post.value

    @property
    def postdate(self):
        return self._post.date

    @property
    def date(self):
        return self._media.get("createdAt") or self._media.get("postedAt") or self.postdate

    @property
    def id(self):
        return self._media.get("id")

    @property
    def postid(self):
        return self._post.id

    @property
    def text(self):
        return self._post.text


    @property
    def text_(self):
        text = self.text
        # this is for removing emojis
        # text=re.sub("[^\x00-\x7F]","",text)
        # this is for removing html tags
        text = re.sub("<[^>]*>", "", text)
        # this for remove random special invalid special characters
        text = re.sub('[\n<>:"/\|?*]+', '', text)
        text = re.sub(" +", " ", text)
        length = int(config.get("textlength") or TEXTLENGTH_DEFAULT)
        if args_.getargs().letter_count:
            if length==0 and self._addcount():
                return f"{text}_{self.count}"
            elif length==0 and not self._addcount():
                return text
            elif length!=0 and not self._addcount():
                return "".join(list(text))[:length]
            elif length!=0 and self._addcount():
                append=f"_{self.count}"
                return f"{''.join(list(text)[:length-len(append)])}{append}"
                
        if not args_.getargs().letter_count:
            if length==0 and self._addcount():
                return f"{text}_{self.count}"
            elif length==0 and not self._addcount():
                return text
            elif length!=0 and not self._addcount():
                return "".join(list(filter(lambda x:len(x)!=0,re.split("( )", text)))[:length])
            elif length!=0 and self._addcount():
                append=f"_{self.count}"
                splitArray=list(filter(lambda x:len(x)!=0,re.split("( )", text)))[:length]
                splitArray[-1]=re.sub(" ","",f"{splitArray[-1]}{append}")
                return "".join(splitArray)

                



       
   
     
       

       

    @property
    def count(self):
        return self._count+1

    @property
    def filename(self):
        if not self.url:
            return
        return self.url.split('.')[-2].split('/')[-1].strip("/,.;!_-@#$%^&*()+\\ ")

    @property
    def preview(self):
        if self.post.preview:
            return 1
        else:
            return 0

    @property
    def linked(self):
        return None

    @property
    def media(self):
        return self._media

    # for use in dynamic names
    def _addcount(self):
        if len(self._post.allmedia) > 1 or self.responsetype_ in ["stories", "highlights"]:
            return True
        return False