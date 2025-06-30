# ofscraper/classes/of/media.py

import asyncio
import logging
import re
import warnings
from typing import Union
from pathlib import Path

import arrow
from async_property import async_cached_property
from bs4 import MarkupResemblesLocatorWarning
from mpegdash.parser import MPEGDASHParser

import ofscraper.classes.of.base as base
import ofscraper.main.manager as manager
import ofscraper.utils.args.accessors.quality as quality
import ofscraper.utils.config.data as data
import ofscraper.utils.dates as dates
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.logs.utils.level as log_helpers

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

log = logging.getLogger("shared")
semaphore = asyncio.BoundedSemaphore(of_env.getattr("MPD_MAX_SEMS"))


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

        self.download_attempted = False
        self.download_succeeded = (
            None  # Using tri-state: None (not attempted), True, False
        )

    def __eq__(self, other):
        if not isinstance(other, Media):
            return NotImplemented
        return self.id == other.id

    def mark_download_attempt(self):
        """Marks that a download has been attempted."""
        self.download_attempted = True

    def mark_download_finished(self,success=True):
        """Marks a download as successful/failed."""
        self.download_attempted = True
        self.download_succeeded =(success==True)
        self.update_status()

    def update_status(self):
        self.media["download_status"] = "skipped"
        if self.download_attempted == True and self.download_succeeded == False:
            self.media["download_status"] = "failed"
        elif self.download_attempted == True and self.download_succeeded == True:
            self.media["download_status"] = "succeed"

    def add_filepath(self, path: Union[str | Path]):
        path = str(path)
        self.media["filepath"] = path

    # only use if content type can't be found from request
    @property
    def content_type(self):
        if self.mediatype.lower() == "videos":
            return "mp4"
        elif self.mediatype.lower() == "images":
            return "jpg"
        elif self.mediatype.lower() == "audios":
            return "mp3"

    @property
    def expires(self):
        return self._post.expires

    @property
    def media_source(self):
        return self._media.get("source", {})

    @property
    def files_source(self):
        return {
            key: (inner_dict or {}).get("url")
            for key, inner_dict in self._media.get("files", {}).items()
        }

    @property
    def quality(self):
        return self._media.get("videoSources", {})

    @property
    def mediatype(self):
        media_type = self._media["type"]
        if media_type == "photo":
            return "images"
        elif media_type == "gif":
            return "videos"
        elif media_type == "forced_skipped":
            return "forced_skipped"
        else:
            return f"{media_type}s".lower()

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
        elif self.responsetype in {"stories", "highlights"}:
            self._final_url = self.files_source.get("full")
        elif self.responsetype == "profile":
            self._final_url = self._media.get("url")
        else:
            self._final_url = self._url_quality_picker()
        return self._final_url

    def _url_quality_picker(self):
        quality_val = self.normal_quality_helper()
        out = None
        if quality_val != "source":
            out = self._media.get("videoSources", {}).get(quality_val)

        if out is None:
            out = self.files_source.get("full")

        if out is None:
            out = self.media_source.get("source")
        return out

    @property
    def post(self):
        return self._post

    @property
    def id(self):
        return self._media["id"]

    @property
    def file_postid(self):
        return self._post.id

    @property
    def canview(self):
        if self.responsetype.lower() == "profile":
            return True
        return (
            self._media.get("canView", False)
            if (self.url or self.mpd) is not None
            else False
        )

    @property
    def label(self):
        return self._post.label

    @property
    def label_string(self):
        return self._post.label_string

    @property
    def downloadtype(self):
        return "Protected" if self.mpd else "Normal"

    @property
    def modified_responsetype(self):
        return self._post.modified_response_helper() or self._post.modified_responsetype

    @property
    def responsetype(self):
        return self._post.responsetype

    @property
    def value(self):
        return self._post.value

    @property
    def postdate(self):
        return self._post.date

    @property
    def formatted_postdate(self):
        return self._post.formatted_date

    @property
    def date(self):
        return (
            self._media.get("createdAt") or self._media.get("postedAt") or self.postdate
        )

    @property
    def formatted_date(self):
        date_val = self._media.get("createdAt") or self._media.get("postedAt")
        if date_val:
            return arrow.get(date_val).format("YYYY-MM-DD hh:mm:ss")
        return None

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
        if self.protected is False:
            return None
        return (
            self._media.get("files", {}).get("drm", {}).get("manifest", {}).get("dash")
        )

    @property
    def hls(self):
        if self._hls:
            return self._hls
        if self.protected is False:
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
        if not self.hls:
            return None
        return re.sub(r"[a-z0-9]+.m3u8$", "", self.hls)

    @property
    def mpdout(self):
        if not self.mpd:
            return None

    @property
    def file_text(self):
        text = self.get_text()
        text = self.file_cleanup(text)
        text = self.text_trunicate(text)
        if not text:
            return str(self.id)
        return text

    @property
    def count(self):
        return self._count + 1

    @property
    def filename(self):
        if not self.url and not self.mpd:
            return None

        base_url = self.url or self.mpd
        if not base_url:
            return None

        filename_part = (
            base_url.split(".")[-2].split("/")[-1].strip("/,.;!_-@#$%^&*()+\\ ")
        )
        filename = re.sub(r"\.mpd$", "", filename_part)

        if self.responsetype.lower() == "profile":
            date_str = arrow.get(self.date).format()
            return f"{filename}_{date_str}"
        return filename

    @async_cached_property
    async def final_filename(self):
        return await self._get_final_filename_async()

    @property
    def no_quality_final_filename(self):
        filename = self.filename or str(self.id)
        if self.mediatype == "videos":
            filename = re.sub("_[a-z0-9]+$", "", filename)

        try:
            filename = self.file_cleanup(filename)
            filename = re.sub(" ", data.get_spacereplacer(), filename)
        except Exception as e:
            log.error(f"Error cleaning filename: {e}")

        return filename

    @property
    def preview(self):
        return 1 if self.post.preview else 0

    @property
    def linked(self):
        return (self.url or self.mpd) is not None

    @property
    def link(self):
        return self.url or self.mpd

    @property
    def media(self):
        return self._media

    @async_cached_property
    async def parse_mpd(self):
        if not self.mpd:
            return
        if self._cached_mpd:
            return self._cached_mpd
        params = {
            "Policy": self.policy,
            "Key-Pair-Id": self.keypair,
            "Signature": self.signature,
        }
        async with self._lock:
            if self._cached_mpd:  # double check lock
                return self._cached_mpd
            async with manager.Manager.aget_ofsession(
                retries=of_env.getattr("MPD_NUM_TRIES"),
                wait_min=of_env.getattr("OF_MIN_WAIT_API"),
                wait_max=of_env.getattr("OF_MAX_WAIT_API"),
                connect_timeout=of_env.getattr("MPD_CONNECT_TIMEOUT"),
                total_timeout=of_env.getattr("MPD_TOTAL_TIMEOUT"),
                read_timeout=of_env.getattr("MPD_READ_TIMEOUT"),
                pool_timeout=of_env.getattr("MPD_POOL_CONNECT_TIMEOUT"),
                sem=semaphore,
                log=self._log,
            ) as c:
                async with c.requests_async(url=self.mpd, params=params) as r:
                    self._cached_mpd = MPEGDASHParser.parse(await r.text_())
                    return self._cached_mpd

    @async_cached_property
    async def mpd_video(self):
        if not self.mpd:
            return
        return await self.mpd_video_helper()

    @async_cached_property
    async def mpd_audio(self):
        if not self.mpd:
            return
        return await self.mpd_audio_helper()

    @property
    def license(self):
        if not self.mpd:
            return None
        responsetype = self.post.responsetype
        if responsetype in ["timeline", "archived", "pinned", "posts", "streams"]:
            responsetype = "post"
        return of_env.getattr("LICENCE_URL").format(self.id, responsetype, self.postid)

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
        return await self.selected_quality or of_env.getattr("QUALITY_UNKNOWN_DEFAULT")

    @property
    def protected(self):
        if self.mediatype not in {"videos", "texts"}:
            return False
        if self.media_source.get("source"):
            return False
        if self.files_source.get("full"):
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
        if self.responsetype.lower() != "profile":
            date_str = arrow.get(self.date).format(data.get_date())
            text = self._post.file_sanitized_text or self.filename or date_str
        else:
            date_str = arrow.get(self.date).format()
            text = f"{date_str} {self.text or self.filename}"
        return text

    async def mpd_video_helper(self, mpd_obj=None):
        mpd = mpd_obj or await self.parse_mpd
        if not mpd:
            return None
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

                representations = sorted(
                    adapt_set.representations, key=lambda x: x.height, reverse=True
                )
                selected_repr = None
                for quality_val in allowed:
                    if quality_val.lower() == "source":
                        selected_repr = representations[0]
                        break
                    for r in representations:
                        if str(r.height) == quality_val:
                            selected_repr = r
                            break
                    if selected_repr:
                        break

                selected_repr = (
                    selected_repr or representations[0]
                )  # Fallback to highest

                origname = f"{selected_repr.base_urls[0].base_url_value}"
                return {
                    "origname": origname,
                    "pssh": kId,
                    "type": "video",
                    "name": f"tempvid_{self.id}_{self.postid}",
                    "ext": "mp4",
                }

    async def mpd_audio_helper(self, mpd_obj=None):
        mpd = mpd_obj or await self.parse_mpd
        if not mpd:
            return None
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

                # Typically there's only one audio representation
                repr = adapt_set.representations[0]
                origname = f"{repr.base_urls[0].base_url_value}"
                return {
                    "origname": origname,
                    "pssh": kId,
                    "type": "audio",
                    "name": f"tempaudio_{self.id}_{self.postid}",
                    "ext": "mp4",
                }

    def normal_quality_helper(self):
        if self.mediatype != "videos":
            return "source"

        allowed = quality.get_allowed_qualities()
        available = self._media.get("videoSources", {})

        # Check from highest to lowest preferred quality
        for qual in allowed:
            if qual.lower() == "source":  # "source" is an alias for the best available
                return "source"
            if available.get(qual):
                return qual
        return "source"  # Fallback

    async def alt_quality_helper(self, mpd_obj=None):
        mpd = mpd_obj or await self.parse_mpd
        if not mpd:
            return None

        allowed = quality.get_allowed_qualities()
        for period in mpd.periods:
            for adapt_set in filter(
                lambda x: x.mime_type == "video/mp4", period.adaptation_sets
            ):
                representations = sorted(
                    adapt_set.representations, key=lambda x: x.height, reverse=True
                )
                for qual in allowed:
                    if qual.lower() == "source":
                        return str(representations[0].height)
                    for r in representations:
                        if str(r.height) == qual:
                            return str(r.height)
                return str(representations[0].height)  # Fallback to best

    async def _get_final_filename_async(self):
        filename = self.filename or str(self.id)
        if self.mediatype == "videos":
            filename = re.sub("_[a-z0-9]+$", "", filename)
            quality_placeholder = await self.selected_quality_placeholder
            filename = f"{filename}_{quality_placeholder}"

        try:
            filename = self.file_cleanup(filename)
            filename = re.sub(" ", data.get_spacereplacer(), filename)
        except Exception as e:
            log.error(f"Error creating final filename: {e}")

        return filename
