"""DRM key redaction, license URLs, and ffmpeg version checks."""

# ----------------------------------------------------------------------
# From test_drm_keys_not_logged.py
# Content keys never reach the log.
#
# The debug log is what people attach to bug reports, and a content key
# decrypts the video for anyone who has it. un_encrypt logged the key it got
# (from the cache or a key helper) and the key handed to ffmpeg, and the cdrm
# helper logged its whole reply, keys included.
# ----------------------------------------------------------------------

import asyncio
import contextlib
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import ofscraper.commands.scraper.actions.download.utils.keyhelpers as keyhelpers
from test.test_cdrm import use_cdrm_url
from test.test_drm_key_id import AUDIO_KEY, AUDIO_KID, VIDEO_KEY, VIDEO_KID, _encrypted_file


def _logged(log):
    return " ".join(str(a) for call in log.mock_calls for a in call.args)


@pytest.mark.parametrize("cached", [False, True])
def test_un_encrypt_logs_no_key(monkeypatch, tmp_path, cached):
    part = _encrypted_file(tmp_path / "tempvid.part", VIDEO_KID)
    saved = {f"lic#{VIDEO_KID}": f"{VIDEO_KID}:{VIDEO_KEY}"} if cached else {}
    monkeypatch.setattr(keyhelpers.settings, "get_settings", lambda: SimpleNamespace(key_mode="manual"))
    real_getattr = keyhelpers.of_env.getattr
    monkeypatch.setattr(keyhelpers.of_env, "getattr", lambda key, default=None:
                        True if key == "USE_WIV_CACHE_KEY" else real_getattr(key, default))
    monkeypatch.setattr(keyhelpers.cache, "get", lambda name: saved.get(name))
    monkeypatch.setattr(keyhelpers.cache, "set", lambda name, value, **kw: saved.__setitem__(name, value))
    monkeypatch.setattr(keyhelpers, "key_helper_manual", AsyncMock(return_value=f"{VIDEO_KID}:{VIDEO_KEY}"))
    monkeypatch.setattr(keyhelpers, "get_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(keyhelpers, "strip_pssh", Mock(return_value=0))
    monkeypatch.setattr(keyhelpers.stop, "check", lambda: None)

    async def decrypt(cmd, **kwargs):
        (tmp_path / "tempvid.mp4").write_bytes(b"clear")
        return SimpleNamespace()

    monkeypatch.setattr(keyhelpers, "async_run", decrypt)
    log = Mock()

    async def go():
        with ThreadPoolExecutor(1) as pool:
            monkeypatch.setattr(keyhelpers.common_globals, "thread", pool, raising=False)
            await keyhelpers.un_encrypt(
                {"path": part, "ext": "mp4", "pssh": "pssh"},
                None,
                SimpleNamespace(id=1, post_id=1, license="lic"),
                input_=log,
            )

    asyncio.run(go())
    assert log.debug.called
    assert VIDEO_KEY not in _logged(log)


def test_cdrm_reply_is_not_logged(monkeypatch):
    use_cdrm_url(monkeypatch)
    monkeypatch.setattr(keyhelpers.auth_requests, "make_headers", lambda: {})
    monkeypatch.setattr(keyhelpers.auth_requests, "get_cookies_str", lambda: "")
    monkeypatch.setattr(keyhelpers.auth_requests, "create_sign", lambda url, headers: None)
    monkeypatch.setattr(keyhelpers, "get_cmd_download_req_retries", lambda: 1)
    log = Mock()
    monkeypatch.setattr(keyhelpers, "log", log)
    message = f"{AUDIO_KID}:{AUDIO_KEY}\n{VIDEO_KID}:{VIDEO_KEY}"

    @contextlib.asynccontextmanager
    async def requests_async(**kw):
        yield SimpleNamespace(json_=AsyncMock(return_value={"message": message}))

    c = SimpleNamespace(requests_async=requests_async)
    asyncio.run(keyhelpers.key_helper_cdrm(c, "pssh", "https://lic", 1, VIDEO_KID))

    logged = _logged(log)
    assert "message" in logged  # the reply's fields are still logged
    assert AUDIO_KEY not in logged and VIDEO_KEY not in logged

# ----------------------------------------------------------------------
# From test_drm_license_url.py
# ----------------------------------------------------------------------

import pytest

import ofscraper.classes.of.posts as posts_
from ofscraper.classes.of.media import Media


def _media(post_data, responsetype=None):
    post = posts_.Post(post_data, 1, "model", responsetype=responsetype)
    media = Media({"id": 111}, 0, post)
    media.mpd = "https://cdn/manifest.mpd"
    return media


@pytest.mark.parametrize(
    "post_data,responsetype,kind",
    [
        ({"id": 5, "responseType": "post"}, None, "post"),
        ({"id": 5, "responseType": "message"}, None, "message"),
        ({"id": 5, "responseType": "post", "isArchived": True}, None, "post"),
        ({"id": 5}, "streams", "post"),
        # purchased tab: the raw responseType decides (#49)
        ({"id": 5, "responseType": "post"}, "Paid", "post"),
        ({"id": 5, "responseType": "message"}, "Paid", "message"),
        ({"id": 5}, "Paid", "message"),
    ],
)
def test_license_endpoint(post_data, responsetype, kind):
    url = _media(post_data, responsetype).license
    assert f"/users/media/111/drm/{kind}/5?" in url

# ----------------------------------------------------------------------
# From test_ffmpeg_version.py
# ----------------------------------------------------------------------

from types import SimpleNamespace

import pytest

import ofscraper.utils.system.ffmpeg as ffmpeg


def _fake_version(monkeypatch, line):
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda p: p)
    monkeypatch.setattr(
        ffmpeg, "run", lambda *a, **k: SimpleNamespace(stdout=line, stderr="")
    )
    monkeypatch.setattr(ffmpeg, "_ts_crash", lambda path: None)


@pytest.mark.parametrize(
    "line,ok",
    [
        ("ffmpeg version 5.1.6 Copyright", False),
        ("ffmpeg version 6.1.1 Copyright", True),
        ("ffmpeg version 7.1.1-essentials_build Copyright", True),
        # 8+ decrypts the same; it used to be rejected
        ("ffmpeg version 8.1.2-essentials_build Copyright", True),
        ("ffmpeg version 9.0.2-full_build Copyright", True),
        ("ffmpeg version N-118000-gabcdef Copyright", True),
        ("not ffmpeg", False),
    ],
)
def test_ffmpeg_version_gate(monkeypatch, line, ok):
    _fake_version(monkeypatch, line)
    assert ffmpeg._is_valid_ffmpeg("ffmpeg") is ok


@pytest.mark.parametrize(
    "code,said",
    [
        (0, None),
        (1, None),
        (None, None),
        (-11, "crashed (SIGSEGV)"),
        (-15, "was stopped (SIGTERM)"),
        (-200, "was stopped (signal 200)"),
        (0xC0000005, "crashed (Windows error 0xC0000005)"),
        (0xC0000409, "crashed (Windows error 0xC0000409)"),
        (0xE06D7363, "crashed (Windows error 0xE06D7363)"),  # an uncaught C++ exception
        # exit(-1) and exit(-2) as Windows reports them: errors, not crashes
        (0xFFFFFFFF, None),
        (0xFFFFFFFE, None),
        (0xF0000000, None),
    ],
)
def test_stop_reason(code, said):
    assert ffmpeg.stop_reason(code) == said


def test_ts_sample_is_read_by_a_working_ffmpeg():
    import shutil
    import subprocess

    found = shutil.which("ffmpeg")
    if not found:
        pytest.skip("no ffmpeg on PATH")
    result = subprocess.run(
        [found, "-nostdin", "-loglevel", "error", "-f", "mpegts", "-i", "pipe:0",
         "-c", "copy", "-f", "null", "-"],
        input=ffmpeg._TS_SAMPLE, capture_output=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert ffmpeg._ts_crash(found) is None


def test_ts_crash_reports_a_crashing_binary(tmp_path, monkeypatch):
    import sys

    # a stand-in ffmpeg that reads the sample, then crashes the way the
    # static build does (a bad memory read)
    script = tmp_path / "crash.py"
    # (Python turns a bad memory read into an exception on Windows, so fail
    # fast there)
    crash = (
        "import ctypes; ctypes.windll.kernel32.RaiseFailFastException(None, None, 0)"
        if sys.platform == "win32"
        else "import faulthandler; faulthandler._sigsegv()"
    )
    script.write_text(f"import sys\nsys.stdin.buffer.read()\n{crash}\n", encoding="utf-8")
    real = ffmpeg.subprocess.run
    monkeypatch.setattr(
        ffmpeg.subprocess, "run",
        lambda cmd, **k: real([sys.executable, "-I", str(script), *cmd[1:]], **k),
    )
    assert ffmpeg._ts_crash("ffmpeg").startswith("crashed (")


@pytest.mark.parametrize("code,name", [(-9, "SIGKILL"), (-15, "SIGTERM")])
def test_a_killed_check_is_not_a_crashing_ffmpeg(monkeypatch, caplog, code, name):
    """Killed from outside (out of memory, a shutdown) says nothing about the
    build: it is reported as stopped, and the ffmpeg is kept."""
    import subprocess

    if not hasattr(ffmpeg.signal, name):
        pytest.skip(f"no {name} here")
    monkeypatch.setattr(
        ffmpeg.subprocess, "run",
        lambda cmd, **k: subprocess.CompletedProcess(cmd, code, b"", b""),
    )
    with caplog.at_level("DEBUG", logger="shared"):
        assert ffmpeg._ts_crash("ffmpeg") is None
    assert f"was stopped ({name})" in caplog.text
    assert "crashed" not in caplog.text


@pytest.mark.parametrize(
    "code,said",
    [
        # Ctrl+C or the console closed: Python reports Windows codes
        # unsigned, but signed is the same 32 bits
        (0xC000013A, "was stopped (Windows 0xC000013A, Ctrl+C or the console closed)"),
        (0xC000013A - 2**32, "was stopped (Windows 0xC000013A, Ctrl+C or the console closed)"),
        # ended from a debugger or by Ctrl+C / Ctrl+Break under one
        (0x40010004, "was stopped (Windows 0x40010004, ended by a debugger)"),
        (0x40010005, "was stopped (Windows 0x40010005, Ctrl+C)"),
        (0x40010008, "was stopped (Windows 0x40010008, Ctrl+Break)"),
        # a signed crash code is still a crash
        (0xC0000005 - 2**32, "crashed (Windows error 0xC0000005)"),
    ],
)
def test_a_check_stopped_on_windows_is_not_a_crashing_ffmpeg(monkeypatch, caplog, code, said):
    import subprocess

    monkeypatch.setattr(
        ffmpeg.subprocess, "run",
        lambda cmd, **k: subprocess.CompletedProcess(cmd, code, b"", b""),
    )
    with caplog.at_level("DEBUG", logger="shared"):
        found = ffmpeg._ts_crash("ffmpeg")
    if said.startswith("crashed"):
        assert found == said
    else:
        assert found is None
        assert said in caplog.text and "crashed" not in caplog.text


@pytest.fixture
def lookup(monkeypatch):
    """get_ffmpeg with a settings path, no pyffmpeg, and fake binaries:
    ``crashes`` lists the paths that crash on the MPEG-TS sample."""
    import sys

    state = SimpleNamespace(crashes=set(), on_path=None)
    monkeypatch.setattr(ffmpeg, "_ffmpeg_path", None)
    monkeypatch.setattr(ffmpeg, "_crashed", [])
    monkeypatch.setitem(sys.modules, "pyffmpeg", None)
    monkeypatch.setattr(
        ffmpeg.settings, "get_settings", lambda: SimpleNamespace(ffmpeg="/static/ffmpeg")
    )
    monkeypatch.setattr(
        ffmpeg.shutil, "which",
        lambda p: state.on_path if p == "ffmpeg" else p,
    )
    monkeypatch.setattr(
        ffmpeg, "run",
        lambda *a, **k: SimpleNamespace(stdout="ffmpeg version 7.0.2-static", stderr=""),
    )
    monkeypatch.setattr(
        ffmpeg, "_ts_crash",
        lambda path: "crashed (SIGSEGV)" if path in state.crashes else None,
    )
    return state


def test_a_crashing_ffmpeg_is_skipped_for_a_working_one(lookup, caplog):
    lookup.crashes = {"/static/ffmpeg"}
    lookup.on_path = "/usr/bin/ffmpeg"
    with caplog.at_level("WARNING"):
        assert ffmpeg.get_ffmpeg() == "/usr/bin/ffmpeg"
    assert "'/static/ffmpeg' crashed (SIGSEGV) reading a small test video" in caplog.text


def test_a_crashing_ffmpeg_is_used_when_there_is_no_other(lookup, caplog):
    lookup.crashes = {"/static/ffmpeg"}
    with caplog.at_level("WARNING"):
        assert ffmpeg.get_ffmpeg() == "/static/ffmpeg"
    assert "No other FFmpeg was found" in caplog.text


def test_a_working_settings_ffmpeg_is_still_first(lookup):
    lookup.on_path = "/usr/bin/ffmpeg"
    assert ffmpeg.get_ffmpeg() == "/static/ffmpeg"


def test_the_same_crashing_ffmpeg_is_checked_once(lookup, caplog, monkeypatch):
    # config.json names the ffmpeg that is also the one on PATH
    lookup.crashes = {"/static/ffmpeg"}
    lookup.on_path = "/static/ffmpeg"
    checked = []
    crash = ffmpeg._ts_crash
    monkeypatch.setattr(ffmpeg, "_ts_crash", lambda path: checked.append(path) or crash(path))
    with caplog.at_level("WARNING"):
        assert ffmpeg.get_ffmpeg() == "/static/ffmpeg"
    assert checked == ["/static/ffmpeg"]
    assert caplog.text.count("reading a small test video") == 1


@pytest.mark.parametrize("spelling", ["relative", "symlink"])
def test_one_crashing_ffmpeg_spelt_two_ways_is_checked_once(
    lookup, caplog, monkeypatch, tmp_path, spelling
):
    # config.json names the ffmpeg on PATH by another path to the same file
    binary = tmp_path / "bin" / "ffmpeg"
    binary.parent.mkdir()
    binary.write_bytes(b"")
    if spelling == "relative":
        monkeypatch.chdir(tmp_path)
        configured = os.path.join("bin", "ffmpeg")
    else:
        link = tmp_path / "ffmpeg-link"
        try:
            link.symlink_to(binary)
        except OSError:
            pytest.skip("symbolic links can't be made here")
        configured = str(link)
    monkeypatch.setattr(
        ffmpeg.settings, "get_settings", lambda: SimpleNamespace(ffmpeg=configured)
    )
    lookup.crashes = {configured, str(binary)}
    lookup.on_path = str(binary)
    checked = []
    crash = ffmpeg._ts_crash
    monkeypatch.setattr(ffmpeg, "_ts_crash", lambda path: checked.append(path) or crash(path))
    with caplog.at_level("WARNING"):
        assert ffmpeg.get_ffmpeg() == configured
    assert checked == [configured]
    assert caplog.text.count("reading a small test video") == 1


def test_a_new_search_forgets_the_crashed_ffmpeg_of_the_last_one(lookup, monkeypatch):
    lookup.crashes = {"/static/ffmpeg"}
    assert ffmpeg.get_ffmpeg() == "/static/ffmpeg"  # no other, so used anyway
    # config.json no longer names it, and there is no other ffmpeg
    monkeypatch.setattr(ffmpeg, "_ffmpeg_path", None)
    monkeypatch.setattr(ffmpeg.settings, "get_settings", lambda: SimpleNamespace(ffmpeg=""))
    with pytest.raises(FileNotFoundError):
        ffmpeg.get_ffmpeg()
