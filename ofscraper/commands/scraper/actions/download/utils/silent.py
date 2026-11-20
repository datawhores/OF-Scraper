"""Fansly videos saved without sound because the CDN refused their audio.

A silent save is final: the file counts as downloaded and no later run looks
at it again. If the refusal was temporary, the sound is lost for good. So a
video saved silent because its audio was refused is flagged, and its audio
is checked again: once at the end of the run that saved it, then once per
later download run of the creator, ``SILENT_RECHECKS`` times in all.

A check fetches fresh links for every flagged video of the creator in one
``account/media`` call, then asks for each video's audio playlist and first
audio file. Accepted: the video is downloaded again and the silent file is
replaced once the new copy passes its checks. A video this run didn't scan
(an early stop, another area or date range) is built again from its post:
a timeline post is fetched with ``post?ids=``; a message or a purchase,
which have no such call, from the copy of the post kept in the flag and the
fresh links. Refused (or the media is gone, or the new copy still has no
sound, or it could not be kept: the size limits or ``skip_download_script``
skipped it, or the silent file could not be replaced): one check is used,
so a video that can never be replaced isn't downloaded on every run for
ever. Anything else (network, rate limit, a failed download): nothing is
used.

The flags live in the profile cache, one entry per creator; every change is
made under one lock, so flags saved at once don't overwrite each other.
"""

import asyncio
import collections
import logging
import pathlib
import threading

import ofscraper.classes.of.posts as posts_
import ofscraper.managers.manager as manager
import ofscraper.utils.cache.cache as cache
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.commands.scraper.actions.download import stop
from ofscraper.sites.fansly import api as fansly_api
from ofscraper.sites.fansly import normalize

log = logging.getLogger("shared")

ACCEPTED, REFUSED, GONE, FAILED = "accepted", "refused", "gone", "failed"
# the new copy has sound but wasn't kept (a filter skipped it, or the silent
# file could not be replaced)
NOT_KEPT = "not kept"

# every read-modify-write of a creator's flags
_lock = threading.Lock()


def _key(model_id):
    return f"fansly_silent_v1_{model_id}"


def flags(model_id) -> dict:
    """media id -> {"post_id", "account_media_id", "path", "checks", ...}"""
    try:
        found = cache.get(_key(model_id), default=None)
    except Exception as E:
        log.debug(f"Fansly: could not read the silent-video flags: {E}")
        return {}
    return dict(found) if isinstance(found, dict) else {}


def _change(model_id, change):
    """Apply ``change(records)`` to the stored flags, under the lock."""
    with _lock:
        records = flags(model_id)
        if change(records) is not False:
            cache.set(_key(model_id), records)


def _post_of(ele):
    """What builds ``ele``'s post again: its area, label and, for a message or
    a purchase, a copy of the post without its media."""
    post = getattr(ele, "_post", None)
    raw = dict(getattr(post, "_post", None) or {})
    kind = raw.get("responseType")
    return {
        "area": getattr(post, "_responsetype", None),
        "label": getattr(post, "_label", None),
        "purchased": bool(getattr(post, "_purchased", False)),
        "kind": kind,
        "post": None if kind == "post" else {k: v for k, v in raw.items() if k != "media"},
    }


def flag(model_id, ele, path):
    """``ele`` was saved at ``path`` without sound because its audio was refused."""
    fansly = (ele.media or {}).get("fansly") or {}
    account_media_id = fansly.get("accountMediaId")
    if not account_media_id or not limit():
        return
    built = _post_of(ele)

    def change(records):
        record = records.get(str(ele.id)) or {"checks": 0}
        record.update(
            post_id=str(ele.post_id),
            account_media_id=str(account_media_id),
            preview=bool(fansly.get("isPreview")),
            path=str(path),
            **built,
        )
        records[str(ele.id)] = record

    _change(model_id, change)


def clear(model_id, media_id):
    """``media_id`` was saved with sound: no more checks."""
    _change(model_id, lambda records: records.pop(str(media_id), None) is not None)


def limit() -> int:
    try:
        return max(0, int(of_env.getattr("SILENT_RECHECKS")))
    except (TypeError, ValueError):
        return 0


def _videos_wanted():
    types = settings.get_settings().mediatypes or []
    return any(str(t).lower() == "videos" for t in types)


async def _rebuild(api, model_id, username, media_id, record, account_media):
    """The Media of a flagged video this run didn't scan, built from its post
    with ``account_media``'s fresh links, or None when the post is gone."""
    if record.get("kind") == "post":
        found = await fansly_api.posts_by_id(api, [record["post_id"]])
        post = next((p for p in found or [] if str(p.get("id")) == record["post_id"]), None)
    elif record.get("post"):
        post = dict(record["post"])
        post["media"] = normalize.media_for(account_media, post.get("createdAt"))
    else:
        post = None
    if not post:
        return None
    built = posts_.Post(
        post, model_id, username, record.get("area"),
        label=record.get("label"), purchased=record.get("purchased", False),
    )
    return next((m for m in built.all_media if str(m.id) == media_id), None)


async def _silent_path(record, ele, saved_path):
    """Where the silent copy is: the path kept in the flag or, when no file
    is there any more (moved, and the database updated since), the folder
    and name the database has for it."""
    path = record.get("path")
    if path and pathlib.Path(path).is_file():
        return path
    if saved_path is not None:
        try:
            found = await saved_path(ele)
        except Exception as E:
            log.debug(f"Media {ele.id}: could not read where it is saved: {type(E).__name__}")
            found = None
        if found and pathlib.Path(found).is_file():
            return str(found)
    return path


async def recheck(c, username, model_id, media_by_id, check_audio, download, saved_path=None):
    """Check the creator's flagged videos once (see the module docstring).

    ``media_by_id``: this run's Media by id, used for a download again.
    ``check_audio(c, raw)``: one of ACCEPTED, REFUSED, GONE, FAILED for a raw
    Fansly Media with fresh links. ``download(c, ele)``: True when ``ele``
    was saved again with sound, REFUSED when the new copy still has none,
    NOT_KEPT when it has sound but wasn't kept, anything else when the
    download failed. ``saved_path(ele)``: the file the database has for
    ``ele``, or None.
    """
    records = flags(model_id)
    allowed = limit()
    if not records or not allowed or not _videos_wanted():
        return
    outcomes = collections.Counter()
    try:
        async with manager.Manager.session.aget_ofsession() as api:
            try:
                found = await fansly_api.account_media(
                    api, [r["account_media_id"] for r in records.values()]
                )
            except Exception as E:
                log.debug(f"Fansly: checking the audio of silent videos failed: {E}")
                return
            answers = {str(x.get("id")): x for x in found or [] if isinstance(x, dict)}
            for media_id, record in records.items():
                if stop.requested.is_set():
                    break
                outcome = await _check_one(
                    c, api, username, model_id, media_id, record,
                    answers.get(record["account_media_id"]) or {},
                    media_by_id, check_audio, download, saved_path,
                )
                outcomes[outcome] += 1
                _record(model_id, media_id, outcome, allowed)
    finally:
        total = sum(outcomes.values())
        if total:
            log.debug(
                f"Fansly: checked the audio of {total} silent "
                f"{'video' if total == 1 else 'videos'}: "
                + ", ".join(f"{n} {what}" for what, n in sorted(outcomes.items()))
            )


async def _check_one(c, api, username, model_id, media_id, record, account_media,
                     media_by_id, check_audio, download, saved_path=None):
    raw = account_media.get("preview" if record.get("preview") else "media") or {}
    if str(raw.get("id")) != media_id or not raw.get("variants") and not raw.get("locations"):
        return GONE
    try:
        outcome = await check_audio(c, raw)
    except Exception as E:
        log.debug(f"Media {media_id}: checking its audio failed: {type(E).__name__}")
        return FAILED
    if outcome != ACCEPTED:
        return outcome
    ele = media_by_id.get(media_id)
    if ele is None:
        try:
            ele = await _rebuild(api, model_id, username, media_id, record, account_media)
        except Exception as E:
            log.debug(f"Media {media_id}: fetching its post failed: {type(E).__name__}")
            return FAILED
        if ele is None:
            return GONE
    ele.media.setdefault("fansly", {})["media"] = raw
    ele.replace_silent = await _silent_path(record, ele, saved_path)
    try:
        # Ctrl+C cancels it like any other download
        with stop.transfer(ele):
            saved = await download(c, ele)
    except asyncio.CancelledError:
        if not stop.requested.is_set():
            raise
        return "stopped"
    finally:
        ele.replace_silent = None
    if saved is True:
        return "saved with sound"
    return saved if saved in (REFUSED, NOT_KEPT) else FAILED


def _record(model_id, media_id, outcome, allowed):
    """Store one check's outcome: a refusal, gone media and a copy that
    wasn't kept use a check."""

    def change(records):
        record = records.get(media_id)
        if record is None:
            # the download cleared it (saved with sound) in the meantime
            return False
        if outcome == "saved with sound":
            records.pop(media_id)
            return
        if outcome not in (REFUSED, GONE, NOT_KEPT):
            return False
        record["checks"] = record.get("checks", 0) + 1
        if record["checks"] >= allowed:
            records.pop(media_id)
            log.info(
                f"Media {media_id}: no copy with sound after {record['checks']} "
                f"{'check' if record['checks'] == 1 else 'checks'}; keeping the "
                "video without sound"
            )

    _change(model_id, change)
