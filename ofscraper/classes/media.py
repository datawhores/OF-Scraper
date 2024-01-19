import logging
import re
import string
import traceback

# supress warnings
import warnings

import arrow
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from mpegdash.parser import MPEGDASHParser
from tenacity import (
    AsyncRetrying,
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_random,
)

import ofscraper.classes.sessionbuilder as sessionbuilder
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


log = logging.getLogger("shared")


class Media:
    def __init__(self, media, count, post):
        self._media = media
        self._count = count
        self._post = post

    @property
    def expires(self):
        return self._post.expires

    @property
    def mediatype(self):
        if self._media["type"] == "photo":
            return "images"
        elif self._media["type"] == "gif":
            return "videos"
        elif self._media["type"] == "forced_skipped":
            return "forced_skipped"
        else:
            return f"{self._media['type']}s"

    @property
    def length(self):
        return self._media.get("duration") or self._media.get("source", {}).get(
            "duration"
        )

    @property
    def numeric_length(self):
        if not self.length:
            return "N/A"
        return str((arrow.get(self.length) - arrow.get(0)))

    @property
    def url(self):
        if self.responsetype == "stories" or self.responsetype == "highlights":
            return self._media.get("files", {}).get("source", {}).get("url")
        elif self.responsetype == "profile":
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
    def file_postid(self):
        return self._post._post["id"]

    @property
    def canview(self):
        return (
            self._media.get("canView") or True
            if (self.url or self.mpd) != None
            else False
        )

    @property
    def label(self):
        return self._post.label

    # used for placeholder
    @property
    def label_string(self):
        return self._post.label or "None"

    @property
    def downloadtype(self):
        return "Protected" if self.mpd else "Normal"

    @property
    def modified_responsetype(self):
        return self._post.modified_responsetype

    @property
    def responsetype(self):
        return self._post.responsetype

    @property
    def value(self):
        return self._post.value

    @property
    def postdate(self):
        return self._post.date

    # modified verison of post date
    @property
    def formatted_postdate(self):
        return self._post.formatted_date

    @property
    def date(self):
        return (
            self._media.get("createdAt") or self._media.get("postedAt") or self.postdate
        )

    # modified verison of media date
    @property
    def formatted_date(self):
        if self._media.get("createdAt") or self._media.get("postedAt"):
            return arrow.get(
                self._media.get("createdAt") or self._media.get("postedAt")
            ).format("YYYY-MM-DD hh:mm:ss")
        return None

    @property
    def id(self):
        return self._media.get("id")

    @property
    def postid(self):
        return self._post.id

    @property
    def text(self):
        if self._post.text:
            return re.sub(
                "\n+", " ", BeautifulSoup(self._post.text, "html.parser").text
            )
        return self._post.text

    @property
    def mpd(self):
        if self.url:
            return None
        return (
            self._media.get("files", {}).get("drm", {}).get("manifest", {}).get("dash")
        )

    @property
    def policy(self):
        if self.url:
            return None
        return (
            self._media.get("files", {})
            .get("drm", {})
            .get("signature", {})
            .get("dash", {})
            .get("CloudFront-Policy")
        )

    @property
    def keypair(self):
        if self.url:
            return None
        return (
            self._media.get("files", {})
            .get("drm", {})
            .get("signature", {})
            .get("dash", {})
            .get("CloudFront-Key-Pair-Id")
        )

    @property
    def signature(self):
        if self.url:
            return None
        return (
            self._media.get("files", {})
            .get("drm", {})
            .get("signature", {})
            .get("dash", {})
            .get("CloudFront-Signature")
        )

    @property
    def mpdout(self):
        if not self.mpd:
            return None

    @property
    def file_text(self):
        text = self.get_text()
        text = self.cleanup(text)
        if len(text) == 0:
            return text
        length = int(data.get_textlength())
        if length == 0:
            return text
        elif data.get_textType() == "letter":
            return f"{''.join(list(text)[:length])}"
        else:
            # split and reduce
            wordarray = list(filter(lambda x: len(x) != 0, re.split("( )", text)))
            splitArray = wordarray[: length + 1]
            text = f"{''.join(splitArray)}"
        text = re.sub(" +$", "", text)
        return text

    @property
    def count(self):
        return self._count + 1

    # og filename
    @property
    def filename(self):
        if not self.url and not self.mpd:
            return None
        elif not self.responsetype == "Profile":
            return re.sub(
                "\.mpd$",
                "",
                (self.url or self.mpd)
                .split(".")[-2]
                .split("/")[-1]
                .strip("/,.;!_-@#$%^&*()+\\ "),
            )
        else:
            filename = re.sub(
                "\.mpd$",
                "",
                (self.url or self.mpd)
                .split(".")[-2]
                .split("/")[-1]
                .strip("/,.;!_-@#$%^&*()+\\ "),
            )
            return f"{filename}_{arrow.get(self.date).format(data.get_date())}"

    @property
    def final_filename(self):
        filename = self.filename or self.id
        if self.mediatype == "videos":
            filename = (
                filename if re.search("_source", filename) else f"{filename}_source"
            )
        # cleanup
        filename = self.cleanup(filename)
        return filename

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

    @property
    async def parse_mpd(self):
        if not self.mpd:
            return
        params = {
            "Policy": self.policy,
            "Key-Pair-Id": self.keypair,
            "Signature": self.signature,
        }
        async with sessionbuilder.sessionBuilder() as c:
            async for _ in AsyncRetrying(
                retry=retry_if_not_exception_type(KeyboardInterrupt),
                stop=stop_after_attempt(constants.getattr("NUM_TRIES")),
                wait=wait_random(
                    min=constants.getattr("OF_MIN"),
                    max=constants.getattr("OF_MAX"),
                ),
                reraise=True,
            ):
                with _:
                    async with c.requests(url=self.mpd, params=params)() as r:
                        if not r.ok:
                            r.raise_for_status()
                        return MPEGDASHParser.parse(await r.text_())

    @property
    def license(self):
        if not self.mpd:
            return None
        responsetype = self.post.post["responseType"]
        if responsetype in ["timeline", "archived", "pinned", "posts"]:
            responsetype = "post"
        return constants.getattr("LICENCE_URL").format(
            self.id, responsetype, self.postid
        )

    @property
    def mass(self):
        return self._post.mass

    @mediatype.setter
    def mediatype(self, val):
        self._media["type"] = val

    # for use in dynamic names
    @property
    def needs_count(self):
        if set(["filename", "file_name", "text", "postid", "post_id"]).isdisjoint(
            [
                name
                for text, name, spec, conv in list(
                    string.Formatter().parse(data.get_fileformat())
                )
            ]
        ):
            return False
        elif len(self._post.post_media) > 1 or self.responsetype in [
            "stories",
            "highlights",
        ]:
            return True
        return False

    def get_text(self):
        if self.responsetype != "Profile":
            text = (
                self._post.sanitized_text
                or self.filename
                or arrow.get(self.date).format(data.get_date())
            )
        elif self.responsetype == "Profile":
            text = f"{arrow.get(self.date).format(data.get_date())} {self.text or self.filename}"
        return text

    def cleanup(self, text):
        text = re.sub('[\n<>:"/\|?*:;]+', "", text)
        text = re.sub("-+", "_", text)
        text = re.sub(" +", " ", text)
        text = re.sub(" ", data.get_spacereplacer(), text)
        return text
