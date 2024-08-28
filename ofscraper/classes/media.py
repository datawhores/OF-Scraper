import asyncio
import logging
import re

# supress warnings
import warnings

import arrow
from bs4 import MarkupResemblesLocatorWarning
from mpegdash.parser import MPEGDASHParser
from async_property import async_cached_property

import ofscraper.classes.base as base
import ofscraper.utils.args.accessors.quality as quality
import ofscraper.utils.config.data as data
import ofscraper.utils.constants as constants
import ofscraper.utils.dates as dates
import ofscraper.utils.logs.utils.level as log_helpers
import  ofscraper.runner.manager as manager2


warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


log = logging.getLogger("shared")

semaphore = asyncio.BoundedSemaphore(constants.getattr("MPD_MAX_SEMS"))


class Media(base.base):
    def __init__(self, media, count, post):
        super().__init__()
        self._media = media
        self._count = count
        self._post = post
        self._final_url = None
        self._mpd = None
        self._log = None
        self._hls = None
        self._lock = asyncio.Lock()
        self._cached_mpd = None

    def __eq__(self, other):
        return self.postid == other.postid

    @property
    def expires(self):
        return self._post.expires

    @property
    def media_source(self):
        return self._media.get("source", {})
    

    @property
    def files_source(self):
        return {key: (inner_dict or {}).get("url") for key, inner_dict in self._media.get("files",{}).items()}

    @property
    def quality(self):
        return self._media.get("videoSources", {})

    @property
    def mediatype(self):
        if self._media["type"] == "photo":
            return "images"
        elif self._media["type"] == "gif":
            return "videos"
        elif self._media["type"] == "forced_skipped":
            return "forced_skipped"
        else:
            return f"{self._media['type']}s".lower()

    @property
    def duration(self):
        return self._media.get("duration") or self.media_source.get("duration")

    @property
    def final_duration(self):
        return self._media.get("duration") or self.media_source.get("duration") or 0

    @property
    def numeric_duration(self):
        if not self.duration:
            return "N/A"
        return str((arrow.get(self.duration) - arrow.get(0)))

    @property
    def url(self):
        if self.protected is True:
            return None
        elif self._final_url:
            return self._final_url
        elif self.responsetype == "stories" or self.responsetype == "highlights":
            self._final_url = self.files_source.get("full")
        elif self.responsetype == "profile":
            self._final_url = self._media.get("url")
        else:
            self._final_url = self._url_quality_picker()
        return self._final_url

    def _url_quality_picker(self):
        quality = self.normal_quality_helper()
        out=None
        if quality != "source":
            out=self._media.get("videoSources", {}).get(quality)
        elif out is None:
            out=self.files_source.get("full")
        
        elif out is None:
            out=self.media_source.get("source")
        return out
        

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
        # profiles are always viewable
        if self.responsetype.lower() == "profile":
            return True
        return (
            self._media.get("canView") if (self.url or self.mpd) is not None else False
        )

    @property
    def label(self):
        return self._post.label

    # used for placeholder
    @property
    def label_string(self):
        return self._post.label_string

    @property
    def downloadtype(self):
        return "Protected" if self.mpd else "Normal"

    @property
    def modified_responsetype(self):
        return (
            self._post.modified_response_helper(mediatype=self.mediatype)
            or self._post.modified_responsetype
        )

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
        return self._post.text

    @property
    def mpd(self):
        if self._mpd:
            return self._mpd
        elif self.protected is False:
            return None
        return (
            self._media.get("files", {}).get("drm", {}).get("manifest", {}).get("dash")
        )

    @property
    def hls(self):
        if self._hls:
            return self._hls
        elif self.protected is False:
            return None
        return (
            self._media.get("files", {}).get("drm", {}).get("manifest", {}).get("hls")
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
    def hls_policy(self):
        if self.url:
            return None
        return (
            self._media.get("files", {})
            .get("drm", {})
            .get("signature", {})
            .get("hls", {})
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
    def hls_keypair(self):
        if self.url:
            return None
        return (
            self._media.get("files", {})
            .get("drm", {})
            .get("signature", {})
            .get("hls", {})
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
    def hls_signature(self):
        if self.url:
            return None
        return (
            self._media.get("files", {})
            .get("drm", {})
            .get("signature", {})
            .get("hls", {})
            .get("CloudFront-Signature")
        )

    @property
    def hls_header(self):
        return f"CloudFront-Policy={self.hls_policy}; CloudFront-Signature={self.hls_signature}; CloudFront-Key-Pair-Id={self.hls_keypair}"

    @property
    def hls_base(self):
        return re.sub(r"[a-z0-9]+.m3u8$", "", self.hls)

    @property
    def mpdout(self):
        if not self.mpd:
            return None

    @property
    def file_text(self):
        text = self.get_text()
        text = self.file_cleanup(text, mediatype=self.mediatype)
        text = self.text_trunicate(text)
        if not text:
            return  self.id
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
            return f"{filename}_{arrow.get(self.date).format(data.get_date(mediatype=self.mediatype))}"

    @async_cached_property
    async def final_filename(self):
        # Assuming usage within the same class or instance
        final_filename = await self._get_final_filename_async()
        # Block and wait for the asynchronous operation to complete
        return final_filename

    @property
    def no_quality_final_filename(self):
        filename = self.filename or str(self.id)
        if self.mediatype == "videos":
            filename = re.sub("_[a-z]+", "", filename)
        # cleanup
        try:
            filename = self.file_cleanup(filename)
            filename = re.sub(
                " ", data.get_spacereplacer(mediatype=self.mediatype), filename
            )
        except Exception as E:
            print(E)
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

    @async_cached_property
    async def parse_mpd(self):
        if not self.mpd:
            return
        elif self._cached_mpd:
            return self._cached_mpd
        params = {
            "Policy": self.policy,
            "Key-Pair-Id": self.keypair,
            "Signature": self.signature,
        }
        async with self._lock:
            async with manager2.Manager.aget_ofsession(
                retries=constants.getattr("MPD_NUM_TRIES"),
                wait_min=constants.getattr("OF_MIN_WAIT_API"),
                wait_max=constants.getattr("OF_MAX_WAIT_API"),
                connect_timeout=constants.getattr("MPD_CONNECT_TIMEOUT"),
                total_timeout=constants.getattr("MPD_TOTAL_TIMEOUT"),
                read_timeout=constants.getattr("MPD_READ_TIMEOUT"),
                pool_timeout=constants.getattr("MPD_POOL_CONNECT_TIMEOUT"),
                semaphore=semaphore,
                log=self._log,
            ) as c:
                async with c.requests_async(url=self.mpd, params=params) as r:
                    self._cached_mpd = MPEGDASHParser.parse(await r.text_())
                    return self._cached_mpd

    @async_cached_property
    async def mpd_video(self):
        if not self.mpd:
            return
        video = await self.mpd_video_helper()
        return video

    @async_cached_property
    async def mpd_audio(self):
        if not self.mpd:
            return
        audio = await self.mpd_audio_helper()
        return audio

    @property
    def license(self):
        if not self.mpd:
            return None
        responsetype = self.post.post["responseType"]
        if responsetype in ["timeline", "archived", "pinned", "posts", "streams"]:
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

    @url.setter
    def url(self, val):
        self._final_url = val

    @mpd.setter
    def mpd(self, val):
        self._mpd = val

    @async_cached_property
    async def selected_quality(self):
        if self.protected is False:
            return self.normal_quality_helper()
        return await self.alt_quality_helper()

    @async_cached_property
    async def selected_quality_placeholder(self):
        return await self.selected_quality or constants.getattr(
            "QUALITY_UNKNOWN_DEFAULT"
        )

    @property
    def protected(self):
        if self.mediatype not in {"videos", "texts"}:
            return False
        elif bool(self.media_source.get("source")):
            return False
        elif bool(self.files_source.get("full")):
            return False
        return True

    @property
    def username(self):
        return self._post.username

    @property
    def model_id(self):
        return self._post.model_id

    @property
    def duration_string(self):
        return dates.format_seconds(self.duration) if self.duration else None

    @property
    def log(self):
        return self._log

    @log.setter
    def log(self, val):
        self._log = val

    def get_text(self):
        if self.responsetype != "Profile":
            text = (
                self._post.file_sanitized_text
                or self.filename
                or arrow.get(self.date).format(data.get_date(mediatype=self.mediatype))
            )
        elif self.responsetype == "Profile":
            text = f"{arrow.get(self.date).format(data.get_date(mediatype=self.mediatype))} {self.text or self.filename}"
        return text

    async def mpd_video_helper(self, mpd=None):
        mpd = mpd or await self.parse_mpd
        if not mpd:
            return
        allowed = quality.get_allowed_qualities()
        for period in mpd.periods:
            for adapt_set in filter(
                lambda x: x.mime_type == "video/mp4", period.adaptation_sets
            ):
                kId = None
                for prot in adapt_set.content_protections:
                    if prot.value is None:
                        kId = prot.pssh[0].pssh
                        break

                selected_quality = None
                for ele in ["240", "720"]:
                    if ele not in allowed:
                        continue
                    selected_quality = selected_quality or next(
                        filter(
                            lambda x: x.height == int(ele), adapt_set.representations
                        ),
                        None,
                    )
                selected_quality = selected_quality or max(
                    adapt_set.representations, key=lambda x: x.height
                )
                for repr in adapt_set.representations:
                    if repr.height == selected_quality.height:
                        origname = f"{repr.base_urls[0].base_url_value}"
                        return {
                            "origname": origname,
                            "pssh": kId,
                            "type": "video",
                            "name": f"tempvid_{self.id}_{self.postid}",
                            "ext": "mp4",
                        }

    async def mpd_audio_helper(self, mpd=None):
        mpd = mpd or await self.parse_mpd
        if not mpd:
            return
        for period in mpd.periods:
            for adapt_set in filter(
                lambda x: x.mime_type == "audio/mp4", period.adaptation_sets
            ):
                kId = None
                for prot in adapt_set.content_protections:
                    if prot.value is None:
                        kId = prot.pssh[0].pssh
                        log_helpers.updateSenstiveDict(kId, "pssh_code")
                        break
                for repr in adapt_set.representations:
                    origname = f"{repr.base_urls[0].base_url_value}"
                    return {
                        "origname": origname,
                        "pssh": kId,
                        "type": "audio",
                        "name": f"tempaudio_{self.id}_{self.postid}",
                        "ext": "mp4",
                    }

    def normal_quality_helper(self):
        allowed = quality.get_allowed_qualities()
        if self.mediatype != "videos":
            return "source"
        for ele in ["240", "720"]:
            if ele not in allowed:
                continue
            elif self._media.get("videoSources", {}).get(ele):
                return ele
        return "source"

    async def alt_quality_helper(self, mpd=None):
        mpd = mpd or await self.parse_mpd

        if not mpd:
            return
        allowed = quality.get_allowed_qualities()
        selected = None

        for period in mpd.periods:
            for adapt_set in filter(
                lambda x: x.mime_type == "video/mp4", period.adaptation_sets
            ):
                for ele in ["240", "720"]:
                    if ele not in allowed:
                        continue
                    selected = selected or next(
                        filter(
                            lambda x: x.height == int(ele), adapt_set.representations
                        ),
                        None,
                    )
                return str(selected.height) if selected else "source"

    async def _get_final_filename_async(self):
        filename = self.filename or str(self.id)
        if self.mediatype == "videos":
            filename = re.sub("_[a-z0-9]+$", "", filename)
            quality_placeholder = await self.selected_quality_placeholder
            filename = f"{filename}_{quality_placeholder}"
        # cleanup (unchanged)
        try:
            filename = self.file_cleanup(filename)
            filename = re.sub(
                " ", data.get_spacereplacer(mediatype=self.mediatype), filename
            )

        except Exception as E:
            print(E)
            # Handle exception for robustness (optional)

        return filename
