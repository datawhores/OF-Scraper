"""Record one OnlyFans livestream in a Chromium browser (Playwright).

Ported from the Live Stream Monitor plugin by cjb900 (cjb900/OF-Scraper-GUI),
which worked these steps out against the live site:

1. Start a browser with the auth.json login: the ``sess``, ``auth_id`` and
   ``auth_uid`` cookies, its user agent, and its x-bc in ``localStorage``
   (``bcTokenSha``), where the web app reads it. Without that x-bc the app
   makes a new one and treats the session as logged out.
2. Open ``https://onlyfans.com/{username}/live`` and click JOIN LIVE STREAM,
   closing any OnlyFans alert over it without accepting anything.
3. Wait for the player and its sound, then record the video and audio tracks
   with MediaRecorder (WebM). The page queues 5-second chunks; Python drains
   them into the file every 5 s.
4. Stop when asked, when the page leaves ``/live``, when the page says the
   live video has ended and OnlyFans agrees, when OnlyFans twice says the
   stream is over, or after 5 minutes without data.
5. Remux the file with ffmpeg so players show its length.

Playwright and its Chromium are optional: ``pip install "ofscraper-community[live]"``
then ``playwright install chromium``. Nothing here posts to OnlyFans except
what the stream page itself sends.
"""

import base64
import json
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qs, quote, unquote, urlparse, urlsplit

import ofscraper.utils.events as events

log = logging.getLogger("shared")

INSTALL_HINT = (
    'OnlyFans livestreams are recorded with a Chromium browser. Install it with: '
    'pip install "{dist}[live]" (or uv/pipx the same way), then '
    "playwright install chromium"
)


FROZEN_HINT = (
    "OnlyFans livestreams are recorded with a Chromium browser, which the "
    "standalone download doesn't include: use the pip, uv or pipx install to "
    "record them."
)


def install_hint() -> str:
    """INSTALL_HINT for the installed package (datawhores publishes it as ``ofscraper``)."""
    if getattr(sys, "frozen", False):
        return FROZEN_HINT  # pip can't add a package to the standalone download
    from ofscraper.__version__ import __dist_name__

    return INSTALL_HINT.format(dist=__dist_name__)

DRAIN_SECONDS = 5
LIVE_CHECK_SECONDS = 60
NOT_LIVE_CHECKS_TO_STOP = 2
NO_DATA_STOP_SECONDS = 300
PAGE_ENDED_CHECK_SECONDS = 10
PAGE_ENDED_STOP_SECONDS = 30
LIVE_PAGE_WAIT_SECONDS = 5
PLAYER_WAIT_SECONDS = 60
PLAYER_NOT_PLAYING_SECONDS = 10
AUDIO_WAIT_SECONDS = 8
JOIN_ATTEMPTS = 3
JOIN_CLICK_TIMEOUT_MS = 10000

BROWSER_ARGS = [
    "--autoplay-policy=no-user-gesture-required",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
    "--password-store=basic",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--disable-background-media-suspend",
]

# ------------------------------------------------------------------ page scripts

# The browser looks like an ordinary one to the page.
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
if (typeof WebGLRenderingContext !== 'undefined') {
    const _getParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {
        if (p === 37445) return 'Intel Open Source Technology Center';
        if (p === 37446) return 'Mesa DRI Intel(R) HD Graphics 520 (Skylake GT2)';
        return _getParam.call(this, p);
    };
}
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){}, app: {} };
const _origQuery = navigator.permissions.query;
navigator.permissions.query = (params) =>
    params.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : _origQuery(params);
"""

# Agora often plays the sound through Web Audio or an Audio() element that
# isn't in the page. These hooks keep a copy of either so it can be recorded.
AUDIO_TAP_JS = """
(() => {
    const _origConnect = AudioNode.prototype.connect;
    window._lsm_taps = new Map();
    window._lsm_chunks = [];
    window._lsm_audio_plays = [];
    AudioNode.prototype.connect = function(dest, outCh, inCh) {
        if (dest instanceof AudioDestinationNode) {
            const ctx = this.context;
            if (!window._lsm_taps.has(ctx)) {
                window._lsm_taps.set(ctx, null);
                try { window._lsm_taps.set(ctx, ctx.createMediaStreamDestination()); } catch(e) {}
            }
            const tap = window._lsm_taps.get(ctx);
            if (tap) {
                try {
                    inCh !== undefined ? _origConnect.call(this, tap, outCh, inCh)
                    : outCh !== undefined ? _origConnect.call(this, tap, outCh)
                    : _origConnect.call(this, tap);
                } catch(e) {}
            }
        }
        return inCh !== undefined ? _origConnect.call(this, dest, outCh, inCh)
             : outCh !== undefined ? _origConnect.call(this, dest, outCh)
             : _origConnect.call(this, dest);
    };
    window._lsm_get_audio_track = () => {
        for (const [, tap] of window._lsm_taps) {
            if (!tap) continue;
            const t = tap.stream.getAudioTracks();
            if (t.length) return t[0];
        }
        return null;
    };
    const _origPlay = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function() {
        if (this.srcObject instanceof MediaStream) {
            const at = this.srcObject.getAudioTracks();
            if (at.length && !window._lsm_audio_plays.includes(this)) window._lsm_audio_plays.push(this);
        }
        return _origPlay.call(this);
    };
})();
"""

LIVE_PAGE_STATE_JS = """() => {
    if (location.href.includes('return_to')) return 'login';
    const join = [...document.querySelectorAll('button')]
        .some(b => /join\\s+live\\s+stream/i.test(b.textContent || ''));
    if (join) return 'join button';
    if (document.querySelector('video')) return 'video';
    return '';
}"""

# 0 = no <video>, 1 = <video> but no live picture yet, 2 = playing.
PLAYER_STATE_JS = """() => {
    const v = document.querySelector('video');
    if (!v) return 0;
    if (v.srcObject instanceof MediaStream
        && v.srcObject.getVideoTracks().some(t => t.readyState === 'live')) return 2;
    return v.readyState >= 2 ? 2 : 1;
}"""

AUDIO_SOURCE_JS = """() => {
    const live = s => s instanceof MediaStream
        && s.getAudioTracks().some(t => t.readyState !== 'ended');
    const v = document.querySelector('video');
    if (v && live(v.srcObject)) return 'video.srcObject';
    const els = [...document.querySelectorAll('audio'), ...(window._lsm_audio_plays || [])];
    for (const el of els) {
        if (live(el.srcObject)) return el.isConnected ? 'audio-element.srcObject' : 'non-dom-audio-play';
    }
    if (typeof window._lsm_get_audio_track === 'function' && window._lsm_get_audio_track())
        return 'web-audio-lazy-tap';
    return '';
}"""

# innerText includes CSS text-transform, so "LIVE VIDEO HAS ENDED" matches too.
PAGE_ENDED_JS = (
    "() => /\\blive\\s+(video|stream)\\s+has\\s+ended\\b/i"
    ".test((document.body && document.body.innerText) || '')"
)

# Close an OnlyFans alert without agreeing to anything: never a button that
# accepts, agrees, acknowledges or consents, and in a Terms / Privacy / policy
# notice not OK / Continue / Yes either.
ALERT_SELECTOR = '#ModalUserAlert.show, .modal.show[role="dialog"]'
DISMISS_ALERT_JS = """() => {
    const m = document.querySelector('%(sel)s');
    if (!m) return null;
    const squash = s => (s || '').replace(/\\s+/g, ' ').trim();
    const body = m.querySelector('.modal-body') || m;
    const text = squash(body.innerText).slice(0, 300) || '(no text)';
    const label = b => squash(b.textContent) || squash(b.getAttribute('aria-label'));
    const agrees = /accept|agree|acknowledge|consent/i;
    const legal = /terms|privacy|policy|agreement/i.test(squash(m.innerText));
    const safe = [...m.querySelectorAll('button')].filter(b => !agrees.test(label(b)));
    const closeX = safe.find(b => b.matches('button.close, [aria-label="Close"]'));
    const neutral = /^(close|cancel|not now|(maybe )?later|dismiss|no thanks|skip|\\u00d7)$/i;
    const okish = /^(ok|okay|got it|continue|yes|confirm)$/i;
    const pick = closeX
        || safe.find(b => neutral.test(label(b)))
        || (legal ? null : safe.find(b => okish.test(label(b))));
    if (pick) pick.click();
    return {text, legal, button: pick ? (label(pick) || 'close') : ''};
}""" % {"sel": ALERT_SELECTOR}
ALERT_OPEN_JS = "() => !!document.querySelector('%s')" % ALERT_SELECTOR
HIDE_ALERT_JS = """() => {
    const m = document.querySelector('%(sel)s');
    if (!m) return false;
    m.classList.remove('show');
    m.style.display = 'none';
    m.setAttribute('aria-hidden', 'true');
    document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
    document.body.classList.remove('modal-open');
    return true;
}""" % {"sel": ALERT_SELECTOR}

START_RECORDER_JS = """() => {
    const video = document.querySelector('video');
    if (!video) return {ok: false, reason: 'no video'};
    let videoTrack = null;
    if (video.srcObject instanceof MediaStream) {
        const vt = video.srcObject.getVideoTracks();
        if (vt.length) videoTrack = vt[0];
    }
    if (!videoTrack && video.captureStream) {
        try { const vt = video.captureStream().getVideoTracks(); if (vt.length) videoTrack = vt[0]; } catch(e) {}
    }
    let audioTrack = null;
    let audioSource = 'none';
    if (video.srcObject instanceof MediaStream) {
        const at = video.srcObject.getAudioTracks();
        if (at.length) { audioTrack = at[0]; audioTrack.enabled = true; audioSource = 'video.srcObject'; }
    }
    if (!audioTrack) {
        const seen = new Set();
        for (const el of [...document.querySelectorAll('audio'), ...(window._lsm_audio_plays || [])]) {
            if (seen.has(el)) continue;
            seen.add(el);
            if (el.srcObject instanceof MediaStream) {
                const at = el.srcObject.getAudioTracks().filter(t => t.readyState !== 'ended');
                if (at.length) {
                    audioTrack = at[0]; audioTrack.enabled = true;
                    audioSource = el.isConnected ? 'audio-element.srcObject' : 'non-dom-audio-play';
                    break;
                }
            }
            if (!audioTrack && el.captureStream) {
                try {
                    const at = el.captureStream().getAudioTracks();
                    if (at.length) { audioTrack = at[0]; audioSource = 'audio-element.captureStream'; break; }
                } catch(e) {}
            }
        }
    }
    if (!audioTrack && typeof window._lsm_get_audio_track === 'function') {
        const t = window._lsm_get_audio_track();
        if (t) { audioTrack = t; audioSource = 'web-audio-lazy-tap'; }
    }
    const tracks = [videoTrack, audioTrack].filter(Boolean);
    if (!tracks.length) return {ok: false, reason: 'no tracks'};
    const types = ['video/webm;codecs=vp8,opus', 'video/webm;codecs=vp9,opus',
                   'video/webm;codecs=h264,opus', 'video/webm'];
    const mimeType = types.find(t => MediaRecorder.isTypeSupported(t)) || 'video/webm';
    try {
        const rec = new MediaRecorder(new MediaStream(tracks), {mimeType});
        // one chain, so chunks are queued in the order they were recorded
        window._lsm_chain = Promise.resolve();
        rec.ondataavailable = (e) => {
            if (!e.data || e.data.size === 0) return;
            const data = e.data;
            window._lsm_chain = window._lsm_chain.then(() => data.arrayBuffer()).then(ab => {
                const bytes = new Uint8Array(ab);
                let binary = '';
                for (let i = 0; i < bytes.length; i += 8192)
                    binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
                (window._lsm_chunks = window._lsm_chunks || []).push(btoa(binary));
            }).catch(() => {});
        };
        window._lsm_stopped = new Promise(resolve => { rec.onstop = resolve; });
        rec.start(5000);
        window._lsm_recorder = rec;
        return {ok: true, video: !!videoTrack, audio: audioSource, mimeType};
    } catch (err) {
        return {ok: false, reason: String(err)};
    }
}"""

DRAIN_JS = "() => { const c = window._lsm_chunks || []; window._lsm_chunks = []; return c; }"
# Stop, then wait (at most 10 s) until the last chunk is queued.
STOP_RECORDER_JS = """async () => {
    const rec = window._lsm_recorder;
    if (!rec) return;
    if (rec.state !== 'inactive') rec.stop();
    const done = (window._lsm_stopped || Promise.resolve())
        .then(() => window._lsm_chain || Promise.resolve());
    await Promise.race([done, new Promise(r => setTimeout(r, 10000))]);
}"""


# ------------------------------------------------------------------ plain helpers

class BrowserMissing(Exception):
    """Playwright is installed but its Chromium isn't."""


def browser_proxy(proxy: str) -> dict:
    """``OFSC_PROXY`` as Playwright wants it: login details apart from the address."""
    u = urlsplit(proxy)
    if not u.username:
        return {"server": proxy}
    host = f"[{u.hostname}]" if ":" in u.hostname else u.hostname  # IPv6 keeps its brackets
    server = f"{u.scheme}://{host}" + (f":{u.port}" if u.port else "")
    return {"server": server, "username": unquote(u.username), "password": unquote(u.password or "")}


def has_playwright() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


def chromium_installed() -> bool:
    """Whether Playwright's Chromium has been downloaded. Not inside an asyncio loop."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            return os.path.exists(p.chromium.executable_path)
    except Exception as e:
        log.debug(f"couldn't find Playwright's Chromium: {e}")
        return False


def playwright_ready() -> bool:
    """Whether Playwright and its Chromium are installed.

    On first use, installs whichever is missing (``OFSC_INSTALL_EXTRAS``);
    otherwise logs how to install them. Not inside an asyncio loop: Playwright's
    sync API refuses to start there.
    """
    from ofscraper.utils.system import extras

    if not (has_playwright() or (extras.install("live") and has_playwright())):
        log.warning(install_hint())
        return False
    if not (chromium_installed() or (extras.install_chromium() and chromium_installed())):
        log.warning(install_hint())
        return False
    return True


def login_cookies(auth: dict) -> list:
    """The auth.json login as browser cookies for .onlyfans.com."""

    def cookie(name, value):
        return {"name": name, "value": str(value), "domain": ".onlyfans.com", "path": "/"}

    auth_id = str(auth.get("auth_id") or "").strip()
    auth_uid = str(auth.get("auth_uid") or "").strip()
    out = []
    if auth_id:
        out.append(cookie("auth_id", auth_id))
    if auth.get("sess"):
        out.append(cookie("sess", auth["sess"]))
    if auth_uid or auth_id:
        out.append(cookie("auth_uid_", auth_uid or auth_id))
    # auth_uid_<id> is the real 2FA cookie: only when auth_uid was given
    if auth_uid and auth_id:
        out.append(cookie(f"auth_uid_{auth_id}", auth_uid))
    return out


def xbc_script(auth: dict) -> str:
    """Put x-bc where the web app reads it, before any page script runs."""
    xbc = str(auth.get("x-bc") or auth.get("x_bc") or "").strip()
    if not xbc:
        return ""
    return (
        "try { if (location.hostname.endsWith('onlyfans.com')) "
        f"localStorage.setItem('bcTokenSha', {json.dumps(xbc)}); }} catch (e) {{}}"
    )


def is_live_page(url: str, username: str) -> bool:
    """True only for ``/{username}/live``, not a login page that mentions it."""
    try:
        u = urlparse(url or "")
        if "return_to" in parse_qs(u.query or ""):
            return False
        path = unquote(u.path or "").rstrip("/").lower()
        return path == f"/{(username or '').strip().lower()}/live"
    except Exception:
        return False


def needs_no_sandbox() -> bool:
    """Chromium's sandbox can't run as root (e.g. in Docker)."""
    return hasattr(os, "geteuid") and os.geteuid() == 0


def first_line(err) -> str:
    """Playwright errors carry a long call log; the first line says what failed."""
    text = str(err).strip()
    return text.splitlines()[0] if text else type(err).__name__


class EndWatch:
    """Decides when a recording should stop because the stream is over.

    ``check()`` asks OnlyFans: True (live), False (ended) or None (couldn't ask).
    """

    def __init__(self, check, clock=time.monotonic):
        self.check = check
        self.clock = clock
        self.last_check = self.last_data = clock()
        self.not_live = 0
        self.page_ended_since = None
        self.last_page_check = None
        self.page_answer = None

    def page_shows_ended(self, shown: bool):
        if not shown:
            self.page_ended_since = self.last_page_check = self.page_answer = None
        elif self.page_ended_since is None:
            self.page_ended_since = self.clock()

    def got_data(self):
        self.last_data = self.clock()

    def reason(self):
        """Why to stop now, or None to keep recording."""
        now = self.clock()
        if self.page_ended_since is not None:
            # the words alone could be in chat: ask OnlyFans
            if self.last_page_check is None or now - self.last_page_check >= PAGE_ENDED_CHECK_SECONDS:
                # this answer also counts as the minute check
                self.last_page_check = self.last_check = now
                self.page_answer = self.check()
                self.not_live = self.not_live + 1 if self.page_answer is False else 0
                if self.page_answer is False:
                    return "the page says the live video has ended and OnlyFans agrees"
            if self.page_answer is None and now - self.page_ended_since >= PAGE_ENDED_STOP_SECONDS:
                return f"the page has said the live video ended for {PAGE_ENDED_STOP_SECONDS} s"
        if now - self.last_check >= LIVE_CHECK_SECONDS:
            self.last_check = now
            live = self.check()
            self.not_live = self.not_live + 1 if live is False else 0
            if self.not_live >= NOT_LIVE_CHECKS_TO_STOP:
                return "OnlyFans says the stream has ended"
        if now - self.last_data >= NO_DATA_STOP_SECONDS:
            return f"no new data for {NO_DATA_STOP_SECONDS // 60} minutes"
        return None


def remux(ffmpeg, path: pathlib.Path) -> bool:
    """Stream-copy the WebM so it records its length (MediaRecorder leaves it out)."""
    if not ffmpeg:
        return False
    tmp = path.with_name(path.stem + ".tmp.webm")
    size_mb = path.stat().st_size / (1024 * 1024)
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-c", "copy", str(tmp)],
            capture_output=True, stdin=subprocess.DEVNULL, timeout=int(max(300, size_mb / 10)),
        )
        if proc.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            os.replace(tmp, path)
            return True
    except Exception as e:
        log.debug(f"remux of {path.name} failed: {e}")
    tmp.unlink(missing_ok=True)
    return False


def poll_until(probe, done, timeout, interval, halt):
    """Call ``probe()`` until ``done(result)``, ``timeout`` or ``halt``.

    Returns ``(result, seconds waited, halted)``.
    """
    start = time.monotonic()
    result = None
    while True:
        if halt.is_set():
            return result, time.monotonic() - start, True
        try:
            result = probe()
        except Exception:
            result = None
        if done(result) or time.monotonic() - start >= timeout:
            return result, time.monotonic() - start, False
        halt.wait(interval)


# ------------------------------------------------------------------ the recording

def close_alert(page) -> str:
    """Close an OnlyFans alert without accepting anything; say what happened."""
    try:
        alert = page.evaluate(DISMISS_ALERT_JS)
    except Exception:
        return ""
    if not alert:
        return ""
    how = f'closed it with "{alert["button"]}"' if alert.get("button") else "closed it with Escape"
    if not alert.get("button"):
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
            if page.evaluate(ALERT_OPEN_JS):
                page.evaluate(HIDE_ALERT_JS)
                how = "hid it (nothing in it was clicked)"
        except Exception:
            how = "couldn't close it"
    note = f'OnlyFans showed an alert: "{alert.get("text", "")}"; {how}'
    if alert.get("legal"):
        note += ". Nothing was accepted: accept the new terms yourself on onlyfans.com to stop this notice"
    return note


def launch(p, profile: str, auth: dict, proxy=None):
    no_sandbox = needs_no_sandbox()
    kwargs = {
        "user_data_dir": profile,
        "headless": True,
        # the full browser in Chrome's new headless mode, not the stripped shell
        "channel": "chromium",
        "viewport": {"width": 1280, "height": 720},
        "args": BROWSER_ARGS + (["--no-sandbox", "--disable-setuid-sandbox"] if no_sandbox else []),
        "chromium_sandbox": not no_sandbox,
    }
    # OnlyFans ties sess to the user agent it was made with
    if auth.get("user_agent"):
        kwargs["user_agent"] = auth["user_agent"]
    if proxy:
        # the browser goes through the same proxy as the API requests
        kwargs["proxy"] = browser_proxy(proxy)
    try:
        ctx = p.chromium.launch_persistent_context(**kwargs)
    except Exception as e:
        if "executable doesn't exist" in str(e).lower() or "playwright install" in str(e).lower():
            raise BrowserMissing(install_hint()) from e
        raise
    ctx.add_cookies(login_cookies(auth))
    script = xbc_script(auth)
    if script:
        ctx.add_init_script(script)
    ctx.add_init_script(STEALTH_JS)
    ctx.add_init_script(AUDIO_TAP_JS)
    return ctx


def join(page, username, halt) -> bool:
    """Open the live page and join; False (with a log line) if it can't be done."""
    url = f"https://onlyfans.com/{quote(username, safe='')}/live"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
    except Exception as e:
        log.debug(f"{username}: opening the live page: {first_line(e)}")
    state, _, halted = poll_until(
        lambda: "left" if not is_live_page(page.url, username) and "return_to" not in page.url
        else page.evaluate(LIVE_PAGE_STATE_JS),
        bool, LIVE_PAGE_WAIT_SECONDS, 0.25, halt,
    )
    if halted:
        return False
    if state == "login" or "return_to" in page.url:
        log.warning(
            f"{username}: OnlyFans showed its login page to the recording browser. "
            "Check that auth.json is current (cookie, user agent and x-bc from the same browser)"
        )
        return False
    if not is_live_page(page.url, username):
        log.info(f"{username}: the livestream ended before recording could start")
        return False
    button = page.locator("button:has-text('JOIN LIVE STREAM')")
    try:
        if button.count() > 0:
            for attempt in range(1, JOIN_ATTEMPTS + 1):
                if halt.is_set():
                    return False
                note = close_alert(page)
                if note:
                    log.info(f"{username}: {note}")
                    page.wait_for_timeout(500)
                try:
                    button.first.click(timeout=JOIN_CLICK_TIMEOUT_MS)
                    page.wait_for_timeout(1000)
                    break
                except Exception as e:
                    log.debug(f"{username}: join attempt {attempt}/{JOIN_ATTEMPTS}: {first_line(e)}")
            else:
                log.info(f"{username}: couldn't click JOIN LIVE STREAM; trying to record anyway")
    except Exception as e:
        log.debug(f"{username}: join button: {first_line(e)}")

    seen = {"at": None}

    def player():
        if not is_live_page(page.url, username):
            return "left"
        state = page.evaluate(PLAYER_STATE_JS)
        if state and seen["at"] is None:
            seen["at"] = time.monotonic()
        return state

    def ready(state):
        # a <video> that never shows a picture: go on after a while
        return state in ("left", 2) or (
            state == 1 and time.monotonic() - seen["at"] >= PLAYER_NOT_PLAYING_SECONDS
        )

    state, waited, halted = poll_until(player, ready, PLAYER_WAIT_SECONDS, 1.0, halt)
    if halted:
        return False
    if state == "left":
        log.info(f"{username}: the live page closed; the stream ended or didn't load")
        return False
    if not state:
        log.info(f"{username}: no stream player appeared in {PLAYER_WAIT_SECONDS} s")
        return False
    log.debug(f"{username}: stream player ready after {waited:.1f} s")
    audio, waited, halted = poll_until(
        lambda: page.evaluate(AUDIO_SOURCE_JS), bool, AUDIO_WAIT_SECONDS, 0.5, halt
    )
    if halted:
        return False
    if not audio:
        log.info(f"{username}: no sound found after {AUDIO_WAIT_SECONDS} s; recording anyway")
    return True


def drain(page, file) -> int:
    """Write the chunks the page has queued; returns how many bytes."""
    written = 0
    for chunk in page.evaluate(DRAIN_JS) or []:
        data = base64.b64decode(chunk)
        file.write(data)
        written += len(data)
    if written:
        file.flush()
    return written


def capture(username: str, out: pathlib.Path, auth: dict, halt, still_live, ffmpeg=None, proxy=None, account_id=None):
    """Record ``username``'s livestream to ``out`` until it ends or ``halt`` is set.

    Returns the saved path, or None when nothing was recorded.
    """
    from playwright.sync_api import sync_playwright

    out.parent.mkdir(parents=True, exist_ok=True)
    # a fresh private browser profile each time: leftovers from an older
    # session made OnlyFans show the login page even with the right cookies
    profile = tempfile.mkdtemp(prefix="ofscraper-live-")
    saved = False
    try:
        with sync_playwright() as p:
            ctx = launch(p, profile, auth, proxy)
            try:
                page = ctx.new_page()
                if not join(page, username, halt):
                    return None
                result = page.evaluate(START_RECORDER_JS)
                if not (isinstance(result, dict) and result.get("ok")):
                    reason = result.get("reason") if isinstance(result, dict) else result
                    log.info(f"{username}: couldn't start recording ({reason})")
                    return None
                log.info(f"{username}: recording livestream to {out.name}")
                log.debug(f"{username}: recorder {result}")
                events.emit_sync(
                    "live_stream",
                    site="onlyfans",
                    account_id=account_id,
                    username=username,
                    status="recording",
                    part_path=out,
                    part_num=1,
                    started_at=time.time(),
                    reason=f"{out.name} ({result.get('audio', 'no-audio')})",
                )
                saved = record_loop(page, username, out, halt, EndWatch(still_live))
            finally:
                try:
                    ctx.close()
                except Exception:
                    pass
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        if not saved and out.exists() and out.stat().st_size == 0:
            out.unlink()
    if not saved:
        log.info(f"{username}: no livestream data was recorded")
        return None
    if halt.is_set():
        # stopped by hand: don't hold up the exit with a remux of a big file
        log.info(
            f"{username}: livestream saved to {out.name}. Players may not show its length; "
            f"to add it, run: ffmpeg -i {out.name} -c copy fixed.webm"
        )
        return out
    events.emit_sync(
        "live_stream",
        site="onlyfans",
        account_id=account_id,
        username=username,
        status="remuxing",
        part_path=out,
        part_num=1,
        reason="Remuxing WebM duration with ffmpeg...",
    )
    remux(ffmpeg, out)
    log.info(f"{username}: livestream saved to {out.name}")
    return out


def record_loop(page, username, out, halt, end_watch) -> bool:
    """Drain chunks into ``out`` until the stream ends; True if any were saved."""
    total = 0
    with open(out, "xb") as file:
        while not halt.wait(DRAIN_SECONDS):
            if page.is_closed():
                log.info(f"{username}: the recording page closed")
                break
            try:
                got = drain(page, file)
            except Exception as e:
                log.debug(f"{username}: chunk drain failed: {first_line(e)}")
                got = 0
            if got:
                total += got
                end_watch.got_data()
            if not is_live_page(page.url, username):
                log.info(f"{username}: the live page closed; the stream ended")
                break
            try:
                end_watch.page_shows_ended(bool(page.evaluate(PAGE_ENDED_JS)))
            except Exception:
                end_watch.page_shows_ended(False)
            reason = end_watch.reason()
            if reason:
                log.info(f"{username}: stopping the recording: {reason}")
                break
        # let MediaRecorder hand over its last chunk, then save it
        try:
            page.evaluate(STOP_RECORDER_JS)
            total += drain(page, file)
        except Exception:
            pass
    return total > 0
