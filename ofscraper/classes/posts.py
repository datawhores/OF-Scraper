import importlib
import logging
import re

import arrow
from bs4 import BeautifulSoup

import ofscraper.classes.media as Media
import ofscraper.utils.config.data as data

html_parser = "lxml" if importlib.util.find_spec("lxml") else "html.parser"
log = logging.getLogger("shared")


class Post:
    def __init__(self, post, model_id, username, responsetype=None, label=None):
        self._post = post
        self._model_id = int(model_id)
        self._username = username
        self.responsetype = responsetype or post.get("responseType")
        self._label = label

    # All media return from API dict
    @property
    def post_media(self):
        return self._post.get("media") or []

    @property
    def label(self):
        return self._label

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
    def sanitized_text(self):
        string = self.text
        if string:
            string = re.sub("<[^>]*>", "", string)
            string = " ".join(string.split())
            string = BeautifulSoup(string, html_parser).get_text()
        return string

    @property
    def text(self):
        return self._post.get("text")

    # text for posts
    @property
    def db_text(self):
        return self.text if not data.get_sanitizeDB() else self.sanitized_text

    @property
    def title(self):
        return self._post.get("title")

    @property
    def modified_responsetype(self):
        if self.archived:
            if data.get_archived_responsetype() == "":
                return "Archived"
            return data.get_archived_responsetype()

        else:
            # remap some values
            response_key = self.responsetype
            response_key = (
                "timeline"
                if response_key.lower() in {"post", "posts"}
                else response_key
            )
            response = data.responsetype().get(response_key)

            if response == "":
                return self.responsetype.capitalize()
            elif response == None:
                return self.responsetype.capitalize()
            elif response != "":
                return response.capitalize()

    @property
    def id(self):
        return self._post["id"]

    @property
    def date(self):
        return self._post.get("postedAt") or self._post.get("createdAt")

    # modify verison of post date
    @property
    def formatted_date(self):
        return arrow.get(self.date).format("YYYY-MM-DD hh:mm:ss")

    @property
    def value(self):
        if self.price == 0:
            return "free"
        elif self.price > 0:
            return "paid"

    @property
    def price(self):
        return float(self.post.get("price") or 0)

    @property
    def paid(self):
        if (
            self.post.get("isOpen")
            or self.post.get("isOpened")
            or len(self.media) > 0
            or self.price != 0
        ):
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

    # media object array for media that is unlocked or viewable
    @property
    def media(self):
        if int(self.fromuser) != int(self.model_id):
            return []
        else:
            media = map(
                lambda x: Media.Media(x[1], x[0], self), enumerate(self.post_media)
            )
            return list(filter(lambda x: x.canview == True, media))

    # media object array for all media
    @property
    def all_media(self):
        return list(
            map(lambda x: Media.Media(x[1], x[0], self), enumerate(self.post_media))
        )

    @property
    def expires(self):
        return (
            self._post.get("expiredAt", {}) or self._post.get("expiresAt", None)
        ) != None

    @property
    def mass(self):
        return self._post.get("isFromQueue", None)
