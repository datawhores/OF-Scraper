"""The two read-only Fansly calls livestream recording needs.

- ``streaming/followingstreams/online``: who of the followed creators is live
- ``streaming/channel/{accountId}``: a creator's channel, whose
  ``stream.playbackUrl`` carries a short-lived ``?token=``

Both are plain GETs through the API session (token and signed headers come
from the session routing). Nothing is ever posted.
"""

import logging

from ofscraper.sites.fansly import constants

log = logging.getLogger("shared")

ONLINE_URL = constants.api_url("streaming/followingstreams/online")
LIVE_STATUS = 2


def channel_url(account_id) -> str:
    return constants.api_url(f"streaming/channel/{account_id}")


def unwrap(data):
    if not isinstance(data, dict) or str(data.get("success")).lower() != "true":
        raise ValueError("Fansly answered without success")
    return data.get("response")


def parse_online(data) -> list:
    """One dict per live creator: accountId, username, streamId, channelId, title, startedAt."""
    response = unwrap(data) or {}
    accounts = {
        str(a.get("id")): a for a in (response.get("aggregationData") or {}).get("accounts") or []
    }
    out = []
    for s in response.get("streams") or []:
        account_id = str(s.get("accountId") or "")
        if not account_id:
            continue
        account = accounts.get(account_id) or {}
        out.append(
            {
                "accountId": account_id,
                "username": account.get("username") or account_id,
                "streamId": s.get("id"),
                "channelId": s.get("channelId"),
                "title": s.get("title"),
                "startedAt": s.get("startedAt"),
                "status": s.get("status"),
            }
        )
    return out


def parse_channel(data) -> dict:
    """The channel object, plus ``live`` and the tokenised ``playbackUrl``."""
    channel = dict(unwrap(data) or {})
    stream = channel.get("stream") or {}
    channel["live"] = channel.get("status") == LIVE_STATUS
    channel["playbackUrl"] = stream.get("playbackUrl") or channel.get("playbackUrl")
    return channel


async def get_online_streams(c) -> list:
    async with c.requests_async(url=ONLINE_URL) as r:
        return parse_online(await r.json_())


async def get_channel(c, account_id) -> dict:
    async with c.requests_async(url=channel_url(account_id)) as r:
        return parse_channel(await r.json_())
