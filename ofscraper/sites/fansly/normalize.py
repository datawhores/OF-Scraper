"""Turn Fansly API responses into the post and media dicts OF-Scraper reads.

Fansly spreads one post over several lists in the same response: the post
names its attachments, an attachment points to an accountMedia or a bundle
of them, and each accountMedia embeds the Media (with its variants and
locations) and, for locked items, a preview Media. The functions here join
those lists into dicts shaped like OnlyFans posts and media, so ``Post``,
``Media``, the filters, the database and the downloaders work unchanged.

Each media dict also carries the Fansly details under ``"fansly"``:
``accountMediaId`` and ``mediaId`` (separate id spaces), ``isPreview`` and
``media``, the raw Media object with its variants and locations.
"""

import json
import logging
import re

import arrow

from ofscraper.sites.fansly import video

log = logging.getLogger("shared")

# attachment contentType values
ACCOUNT_MEDIA = 1
BUNDLE = 2
AGGREGATED_POST = 8

# locationId of the plain file on the CDN (102 is HLS, 103 is DASH)
DIRECT_LOCATION = "1"

HASHTAG_RE = re.compile(r"#+(\w+)")


def to_seconds(value):
    """Epoch seconds from a Fansly time: above 1e10 is milliseconds, else seconds."""
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return arrow.get(value).float_timestamp
    value = float(value)
    return value / 1000 if value > 1e10 else value


def iso(value):
    seconds = to_seconds(value)
    if seconds is None:
        return None
    return arrow.get(seconds).to("utc").isoformat()


def hashtags(text):
    """``#word`` tags from the text, lowercased, in order, without repeats."""
    out = []
    for tag in HASHTAG_RE.findall(text or ""):
        tag = tag.lower()
        if tag not in out:
            out.append(tag)
    return out


def parse_json(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        data = json.loads(value)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def price_mills(obj):
    """Price in thousandths of a dollar.

    The real price is in ``permissions.permissionFlags[].metadata``: a JSON
    string whose key ``"1"`` holds ``{"price": <mills>}``. The plain ``price``
    field is 0 even for locked items, so it is not used.
    """
    flags = list((obj.get("permissions") or {}).get("permissionFlags") or [])
    if isinstance(obj.get("permissionFlags"), list):
        flags += obj["permissionFlags"]
    for flag in flags:
        if not isinstance(flag, dict):
            continue
        price = parse_json(parse_json(flag.get("metadata")).get("1")).get("price")
        if price:
            return int(price)
    return 0


def media_type(mimetype):
    mimetype = (mimetype or "").lower()
    if mimetype.startswith("image/"):
        return "photo"
    if mimetype.startswith("video/") or mimetype == "application/vnd.apple.mpegurl":
        return "video"
    if mimetype.startswith("audio/"):
        return "audio"
    return None


def direct_url(media):
    for location in media.get("locations") or []:
        if str(location.get("locationId")) == DIRECT_LOCATION:
            return location.get("location") or None
    return None


def file_url(media):
    """The item's URL: for a video, its largest MP4 (its own or a variant's),
    else its best HLS or DASH stream; for anything else, its own file.

    Some videos have no file of their own, only variants. Without a URL the
    item counts as not viewable and is dropped. A stream is downloaded by the
    Fansly stream downloader, which picks it from the raw Media; the URL is
    what the normal downloader fetches.
    """
    if media_type(media.get("mimetype")) != "video":
        # e.g. a GIF with an mp4 variant keeps its own .gif
        return direct_url(media)
    direct = [c for c in video.candidates(media) if c.kind == video.DIRECT]
    if direct:
        return max(direct, key=lambda c: c.area).url
    best = video.select_best(media)
    return best.url if best else direct_url(media)


def duration(media):
    # whole seconds, like OnlyFans (Fansly gives a float)
    value = parse_json(media.get("metadata")).get("duration")
    return int(round(value)) if isinstance(value, (int, float)) else None


def media_dict(account_media, media, is_preview, can_view, fallback_date=None):
    kind = media_type(media.get("mimetype"))
    if kind is None or media.get("id") is None:
        log.debug(f"skipping Fansly media with mimetype {media.get('mimetype')!r}")
        return None
    return {
        "id": int(media["id"]),
        "type": kind,
        "canView": bool(can_view),
        "createdAt": iso(media.get("createdAt"))
        or iso(account_media.get("createdAt"))
        or fallback_date,
        "duration": duration(media),
        "files": {"full": {"url": file_url(media) if can_view else None}},
        "fansly": {
            "accountMediaId": str(account_media["id"]),
            "mediaId": str(media["id"]),
            "isPreview": bool(is_preview),
            "media": media,
        },
    }


def media_for(account_media, fallback_date=None):
    """The media dicts one accountMedia gives.

    The full Media is always listed; it is viewable only when ``access`` is
    true. A locked item (``access`` false) with a ``previewId`` also gives
    its preview Media, as a viewable preview.
    """
    out = []
    access = bool(account_media.get("access"))
    if account_media.get("media"):
        out.append(media_dict(account_media, account_media["media"], False, access, fallback_date))
    if not access and account_media.get("previewId") is not None and account_media.get("preview"):
        out.append(media_dict(account_media, account_media["preview"], True, True, fallback_date))
    return [m for m in out if m]


class Lookup:
    """Index of the side lists in one response (plus backfilled accountMedia)."""

    def __init__(self, response, extra_account_media=()):
        response = response or {}
        self.account_media = {}
        for item in list(response.get("accountMedia") or []) + list(extra_account_media or []):
            if isinstance(item, dict) and item.get("id") is not None:
                self.account_media.setdefault(str(item["id"]), item)
        self.bundles = {
            str(b["id"]): b for b in response.get("accountMediaBundles") or [] if b.get("id")
        }
        self.aggregated = {
            str(p["id"]): p for p in response.get("aggregatedPosts") or [] if p.get("id")
        }


def bundle_member_ids(bundle):
    content = bundle.get("bundleContent") or []
    if content:
        ordered = sorted(content, key=lambda x: x.get("pos") or 0)
        return [str(x["accountMediaId"]) for x in ordered if x.get("accountMediaId")]
    return [str(x) for x in bundle.get("accountMediaIds") or []]


def _attachments(item):
    return sorted(item.get("attachments") or [], key=lambda x: x.get("pos") or 0)


def attached(item, lookup, _seen=None):
    """``(accountMedia, bundle or None)`` pairs for an item's attachments, in order."""
    seen = _seen if _seen is not None else {str(item.get("id"))}
    for attachment in _attachments(item):
        kind = attachment.get("contentType")
        content_id = str(attachment.get("contentId"))
        if kind == ACCOUNT_MEDIA:
            if content_id in lookup.account_media:
                yield lookup.account_media[content_id], None
        elif kind == BUNDLE:
            bundle = lookup.bundles.get(content_id)
            if not bundle:
                continue
            for member in bundle_member_ids(bundle):
                if member in lookup.account_media:
                    yield lookup.account_media[member], bundle
        elif kind == AGGREGATED_POST and content_id not in seen:
            seen.add(content_id)
            inner = lookup.aggregated.get(content_id)
            if inner:
                # an aggregated post shares the outer response's side lists
                yield from attached(inner, lookup, seen)


def missing_account_media_ids(response):
    """accountMedia ids that attachments or bundles name but the response lacks.

    Timeline and message responses embed at most 5 members of a bundle; the
    rest have to be fetched with ``account/media?ids=``.
    """
    lookup = Lookup(response)
    wanted = []
    items = list(response.get("posts") or []) + list(response.get("messages") or [])
    items += list(response.get("aggregatedPosts") or [])
    for item in items:
        for attachment in _attachments(item):
            if attachment.get("contentType") == ACCOUNT_MEDIA:
                wanted.append(str(attachment.get("contentId")))
    for bundle in lookup.bundles.values():
        wanted.extend(bundle_member_ids(bundle))
    for order in response.get("accountMediaOrders") or []:
        if order.get("accountMediaId"):
            wanted.append(str(order["accountMediaId"]))
    out = []
    for account_media_id in wanted:
        if account_media_id not in lookup.account_media and account_media_id not in out:
            out.append(account_media_id)
    return out


def _price(pairs):
    """A priced bundle counts once; an unpriced bundle counts each member."""
    total = 0
    counted = set()
    for account_media, bundle in pairs:
        if bundle is not None:
            bundle_price = price_mills(bundle)
            if bundle_price:
                if bundle["id"] not in counted:
                    counted.add(bundle["id"])
                    total += bundle_price
                continue
        total += price_mills(account_media)
    return total


def _item_dict(item, lookup, response_type):
    created = iso(item.get("createdAt"))
    pairs = list(attached(item, lookup))
    media = [m for account_media, _ in pairs for m in media_for(account_media, created)]
    out = {
        "id": int(item["id"]),
        "text": item.get("content") or "",
        "createdAt": created,
        "postedAt": created,
        "price": _price(pairs) / 1000,
        "isOpened": bool(pairs) and all(a.get("access") for a, _ in pairs),
        "responseType": response_type,
        "hashtags": hashtags(item.get("content")),
        "media": media,
    }
    if item.get("expiresAt"):
        out["expiresAt"] = iso(item["expiresAt"])
    return out


def posts(response, extra_account_media=()):
    """Post dicts for a timeline or ``post?ids=`` response."""
    response = response or {}
    lookup = Lookup(response, extra_account_media)
    return [
        _item_dict(post, lookup, "post")
        for post in response.get("posts") or []
        if post.get("id") is not None
    ]


def messages(response, extra_account_media=()):
    """Message dicts for a ``message?groupId=`` response.

    Like OnlyFans messages they carry ``fromUser`` (the sender), and also
    ``groupId``. A message without id, sender or date is skipped.
    """
    response = response or {}
    lookup = Lookup(response, extra_account_media)
    out = []
    for message in response.get("messages") or []:
        if message.get("id") is None or not message.get("senderId") or not message.get("createdAt"):
            continue
        item = _item_dict(message, lookup, "message")
        item["fromUser"] = {"id": int(message["senderId"])}
        item["groupId"] = str(message.get("groupId")) if message.get("groupId") else None
        out.append(item)
    return out


def purchases(response, account_id, extra_account_media=()):
    """One post dict per purchased accountMedia of one creator.

    Fansly lists purchases as accountMedia orders, not posts, so each item
    becomes its own post, keyed by its accountMedia id.
    """
    response = response or {}
    lookup = Lookup(response, extra_account_media)
    out = []
    seen = set()
    for order in response.get("accountMediaOrders") or []:
        account_media = lookup.account_media.get(str(order.get("accountMediaId")))
        if not account_media or str(account_media.get("accountId")) != str(account_id):
            continue
        if account_media["id"] in seen:
            continue
        seen.add(account_media["id"])
        created = iso(order.get("createdAt")) or iso(account_media.get("createdAt"))
        out.append(
            {
                "id": int(account_media["id"]),
                "text": "",
                "createdAt": created,
                "postedAt": created,
                "price": price_mills(account_media) / 1000,
                "isOpened": bool(account_media.get("access")),
                "responseType": "purchased",
                "hashtags": [],
                "media": media_for(account_media, created),
            }
        )
    return out


def model(account):
    """An OnlyFans-shaped model dict (what ``Model`` reads) from a Fansly account."""
    subscription = account.get("subscription") or {}
    price = subscription.get("price")
    avatar = account.get("avatar") or {}
    header = account.get("banner") or {}
    return {
        "id": int(account["id"]),
        "username": account.get("username"),
        "name": account.get("displayName") or account.get("username"),
        "avatar": direct_url(avatar) if avatar else None,
        "header": direct_url(header) if header else None,
        "currentSubscribePrice": (price or 0) / 1000,
        "subscribePrice": (price or 0) / 1000,
        "subscribedByData": None,
        "subscribedByExpireDate": iso(subscription.get("endsAt")) if subscription else None,
        "lastSeen": None,
        "fansly": {"subscribed": bool(account.get("subscribed")), "following": bool(account.get("following"))},
    }
