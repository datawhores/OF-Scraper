import logging
import arrow
import ofscraper.utils.config as config
import ofscraper.classes.media as Media

log=logging.getLogger("shared")

class Post():
    def __init__(self, post, model_id, username, responsetype=None,label=None):
        self._post = post
        self._model_id = int(model_id)
        self._username = username
        self._responsetype_ = responsetype or post.get("responseType")
        self._label=label

    #All media return from API dict
    @property
    def post_media(self):
        return self._post.get("media") or []

    @property
    def label(self):
        return self._label
    #use for placeholder
    @property
    def label_(self):
        return self._label if self._label else "None"
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
            if config.get_archived_responsetype(config.read_config()) == "":
                return "archived"
            return config.get_archived_responsetype(config.read_config())

        else:
            #remap some values
            response=config.read_config().get("responsetype", {}).get(self.responsetype_) 

            if  response == "":
                return self.responsetype_.capitalize()
            elif  response == None:
                return self.responsetype_.capitalize()
            elif  response != "":
                return  response.capitalize()

    @property
    def id(self):
        return self._post["id"]

    @property
    def date(self):
        return self._post.get("createdAt") or self._post.get("postedAt")
    #modify verison of post date
    @property
    def date_(self):
        return arrow.get(self.date).format("YYYY-MM-DD hh:mm:ss")

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
            return int(self._post["fromUser"]["id"])
        else:
            return self._model_id

    @property
    def preview(self):
        return self._post.get("preview")

    #media object array for media that is unlocked or viewable
    @property
    def media(self):
        if (int(self.fromuser) != int(self.model_id)):
            return []
        else:
            media = map(lambda x: Media.Media(
                x[1], x[0], self), enumerate(self.post_media))
            return list(filter(lambda x: x.canview == True, media))
    #media object array for all media
    @property
    def all_media(self):
        return list(map(lambda x: Media.Media(
            x[1], x[0], self), enumerate(self.post_media)))
    @property
    def expires(self):
        return (self._post.get("expiredAt",{}) or self._post.get("expiresAt",None))!=None
    
    @property
    def mass(self):
        return self._post.get("isFromQueue",None)
