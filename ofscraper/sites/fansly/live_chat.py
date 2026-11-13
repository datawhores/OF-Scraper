"""Read-only livestream chat recorder (off by default, ``--live-chat``).

The chat socket (``wss://chatws.fansly.com/?v=3``) gets exactly two kinds of
frame from us, and ``ChatRecorder._send`` refuses anything else:

- the auth frame ``{"t":1,"d":"{\\"token\\":\\"<token>\\",\\"v\\":3}"}``, once;
- the keep-alive ``p``, every 20-25 s (jittered).

No chat-room join, subscription alerts, likes, tips, messages or acks are ever
sent. Received chat messages (service 46, ``chatRoomMessage``) are appended to
``..._chat.jsonl``, one JSON object per line.
"""

import asyncio
import datetime
import json
import logging
import random

from ofscraper.sites.fansly import constants

log = logging.getLogger("shared")

CHAT_WS_URL = "wss://chatws.fansly.com/?v=3"
PING = "p"
PING_INTERVAL = (20, 25)
TYPE_ERROR = 0
TYPE_SESSION = 1
TYPE_SERVICE_EVENT = 10000
TYPE_BATCH = 10001
CHAT_SERVICE_ID = 46


class ForbiddenFrame(Exception):
    """Raised instead of sending anything other than auth or keep-alive."""


def auth_frame(token: str) -> str:
    return json.dumps({"t": TYPE_SESSION, "d": json.dumps({"token": token, "v": 3})})


def _loads(value):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def chat_messages(frame, chat_room_id=None) -> list:
    """Chat messages carried by one received frame (batches included)."""
    msg = _loads(frame)
    if not isinstance(msg, dict):
        return []
    t, data = msg.get("t"), _loads(msg.get("d"))
    if t == TYPE_BATCH and isinstance(data, list):
        out = []
        for item in data:
            out.extend(chat_messages(item, chat_room_id))
        return out
    if t != TYPE_SERVICE_EVENT or not isinstance(data, dict):
        return []
    if str(data.get("serviceId")) != str(CHAT_SERVICE_ID):
        return []
    event = _loads(data.get("event"))
    if not isinstance(event, dict) or not isinstance(event.get("chatRoomMessage"), dict):
        return []
    message = event["chatRoomMessage"]
    room = message.get("chatRoomId")
    if chat_room_id and room and str(room) != str(chat_room_id):
        return []
    return [message]


class ChatRecorder:
    """``connect()`` returns a socket with async ``send(str)``, ``recv()`` and ``close()``."""

    def __init__(self, connect, token: str, ping_interval=PING_INTERVAL):
        self.connect = connect
        self.token = token
        self.ping_interval = ping_interval
        self.ws = None
        self.received = 0

    async def _send(self, frame: str):
        if frame != PING and frame != auth_frame(self.token):
            raise ForbiddenFrame("only the auth frame and the keep-alive may be sent")
        await self.ws.send(frame)

    async def _pinger(self):
        low, high = self.ping_interval
        while True:
            await asyncio.sleep(random.uniform(low, high))
            await self._send(PING)

    async def run(self, channel: dict, out_path, stop: asyncio.Event = None):
        stop = stop or asyncio.Event()
        chat_room_id = (channel or {}).get("chatRoomId")
        self.ws = await self.connect()
        pinger = None
        try:
            await self._send(auth_frame(self.token))
            pinger = asyncio.ensure_future(self._pinger())
            while not stop.is_set():
                frame = await self.ws.recv()
                if frame is None:
                    break
                msg = _loads(frame)
                if isinstance(msg, dict) and msg.get("t") == TYPE_ERROR:
                    code = (_loads(msg.get("d")) or {}).get("code")
                    log.info(f"live chat closed by Fansly (code {code})")
                    break
                messages = chat_messages(frame, chat_room_id)
                if messages:
                    self._append(out_path, messages)
        finally:
            if pinger:
                pinger.cancel()
                await asyncio.gather(pinger, return_exceptions=True)
            await self.ws.close()

    def _append(self, out_path, messages):
        now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        with open(out_path, "a", encoding="utf-8") as f:
            for m in messages:
                f.write(json.dumps({"receivedAt": now, "chatRoomMessage": m}, ensure_ascii=False) + "\n")
        self.received += len(messages)


class _AiohttpSocket:
    def __init__(self, session, ws):
        self.session = session
        self.ws = ws

    async def send(self, frame: str):
        await self.ws.send_str(frame)

    async def recv(self):
        import aiohttp

        msg = await self.ws.receive()
        if msg.type in (aiohttp.WSMsgType.TEXT,):
            return msg.data
        if msg.type == aiohttp.WSMsgType.BINARY:
            return msg.data.decode("utf-8", errors="replace")
        return None

    async def close(self):
        try:
            await self.ws.close()
        finally:
            await self.session.close()


def aiohttp_connect(user_agent: str):
    """Connector for the real chat socket; only browser headers, no cookies."""

    async def connect():
        import aiohttp

        session = aiohttp.ClientSession()
        try:
            ws = await session.ws_connect(
                CHAT_WS_URL,
                headers={"User-Agent": user_agent or "", "Origin": constants.ORIGIN},
                autoping=True,
            )
        except Exception:
            await session.close()
            raise
        return _AiohttpSocket(session, ws)

    return connect
