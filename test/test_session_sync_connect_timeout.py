"""The sync requests path must time out a TLS handshake that never completes.

It passed connect=None to httpx, which disables the connect timeout, and the
TLS handshake counts as connect time. Behind a VPN that dropped the
handshake reply, fetching the dynamic rules hung forever at "getting new
signature" (datawhores/OF-Scraper#652).
"""

import socket
import threading
import time
from types import SimpleNamespace

import httpx
import pytest

import ofscraper.utils.settings as settings
from ofscraper.managers.sessionmanager.sessionmanager import sessionManager


@pytest.fixture(autouse=True)
def plain_settings(monkeypatch):
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda: SimpleNamespace(ssl_verify="false", cached_disabled=True),
    )


class SilentTLSServer:
    """Accepts connections and never answers the ClientHello."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.held = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._accept, daemon=True)
        self.thread.start()

    def _accept(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.sock.accept()
                self.held.append(conn)
            except OSError:
                pass

    def close(self):
        self.stop.set()
        self.thread.join(2)
        for conn in self.held:
            conn.close()
        self.sock.close()


def test_stalled_handshake_times_out_with_the_session_connect_timeout():
    server = SilentTLSServer()
    quiet_log = SimpleNamespace(
        traceback_=lambda *a, **k: None, debug=lambda *a, **k: None
    )
    result = {}

    def fetch():
        start = time.monotonic()
        try:
            with sessionManager(
                connect_timeout=0.5, retries=1, wait_min=0, wait_max=0, log=quiet_log
            ) as c:
                with c.requests(f"https://127.0.0.1:{server.port}/rules.json"):
                    result["error"] = None
        except Exception as E:
            result["error"] = E
        result["seconds"] = time.monotonic() - start

    worker = threading.Thread(target=fetch, daemon=True)
    worker.start()
    worker.join(10)
    hung = worker.is_alive()
    server.close()
    worker.join(5)

    assert not hung, "the request was still waiting on the handshake after 10 s"
    assert isinstance(result["error"], httpx.ConnectTimeout)
    assert result["seconds"] < 5
