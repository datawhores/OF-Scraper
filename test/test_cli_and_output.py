"""CLI usage errors, exit status, quiet output, URL logging, and temp/resource cleanup."""

# ----------------------------------------------------------------------
# From test_cli_usage_errors.py
# ----------------------------------------------------------------------

import sys

import pytest

import ofscraper.utils.args.main as args_main


@pytest.mark.parametrize(
    "argv, message",
    [
        (["--action", "download", "--bogus-flag"], "No such option"),
        (["--action", "download", "--after", "13/01/2021"], "isn't a date"),
    ],
)
def test_usage_error_prints_a_message_and_exits_2(monkeypatch, capsys, argv, message):
    # a mistake on the command line gets click's usage message, not a traceback
    monkeypatch.setattr(sys, "argv", ["OF-Scraper", *argv])
    # parse_args registers the subcommands each call, and cloup refuses a second
    # registration; the options tested here are on the main program
    monkeypatch.setattr(args_main.main.program, "add_command", lambda *a, **k: None)
    with pytest.raises(SystemExit) as exit_info:
        args_main.parse_args()
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "Usage:" in err
    assert message in err

# ----------------------------------------------------------------------
# From test_output_level_quiet.py
# --output LOW and --output PROMPT make the console quiet (#255).
#
# low_output() read args.output, but the option is stored as output_level, so
# the check never matched and only --no-rich made the console quiet. These
# tests go through the real command-line parse.
# ----------------------------------------------------------------------

import io
import sys

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.args.globals as global_args
import ofscraper.utils.console as console
from ofscraper.utils.args.accessors.output import low_output
from ofscraper.utils.args.parse.commands.main import program


def _parsed(monkeypatch, argv):
    """Parse argv the way the app does on its first settings read."""
    monkeypatch.setattr(sys, "argv", ["ofscraper", *argv])
    monkeypatch.setattr(global_args, "args", None)
    # parse_args registers the subcommands, which can only happen once a process
    if "manual" in program.commands:
        monkeypatch.setattr(program, "add_command", lambda *a, **k: None)


def _console(monkeypatch):
    monkeypatch.setattr(console, "shared_console", None)
    con = console.get_shared_console()
    buf = io.StringIO()
    con.file = buf
    return con, buf


@pytest.mark.parametrize(
    "argv,quiet",
    [
        (["--output", "LOW"], True),
        (["--output", "PROMPT"], True),
        (["-p", "low"], True),  # the short form, lower case
        (["--output", "NORMAL"], False),
        (["--output", "DEBUG"], False),
        ([], False),  # the default is NORMAL
        (["--no-rich"], True),
    ],
)
def test_output_option_sets_console_quiet(monkeypatch, argv, quiet):
    _parsed(monkeypatch, argv)
    con, buf = _console(monkeypatch)
    con.print("hello")
    assert low_output() is quiet
    assert con.quiet is quiet
    assert ("hello" in buf.getvalue()) is not quiet


def test_output_off_is_quiet(monkeypatch):
    # OFF isn't one of --output's choices, but low_output() treats it as
    # quiet; parse NORMAL, then set the stored value to OFF
    _parsed(monkeypatch, [])
    con, buf = _console(monkeypatch)
    con.print("before")
    global_args.args.output_level = "OFF"
    con.print("hidden")
    assert con.quiet is True
    assert buf.getvalue().split() == ["before"]

# ----------------------------------------------------------------------
# From test_run_exit_status.py
# ----------------------------------------------------------------------

import logging

import pytest

import ofscraper.main.open.run as run


def _fail():
    raise RuntimeError("simulated failure")


def test_failed_run_exits_with_status_1_and_logs_the_error(monkeypatch):
    monkeypatch.setattr(run, "start_manager", _fail)
    monkeypatch.setattr(run.exit_manager, "shutdown", lambda: None)
    records = []
    handler = logging.Handler(level=logging.ERROR)
    handler.emit = records.append
    logger = logging.getLogger("shared")
    logger.addHandler(handler)
    try:
        with pytest.raises(SystemExit) as exit_info:
            run.main()
    finally:
        logger.removeHandler(handler)
    assert exit_info.value.code == 1
    assert any("simulated failure" in r.getMessage() for r in records)


def test_successful_run_returns_normally(monkeypatch):
    monkeypatch.setattr(run, "start_manager", lambda: None)
    run.main()

# ----------------------------------------------------------------------
# From test_url_log.py
# ----------------------------------------------------------------------

from types import SimpleNamespace

import ofscraper.commands.scraper.actions.utils.log as log_utils


def _media(url, filename):
    return SimpleNamespace(url=url, mpd=None, filename=filename)


def test_filename_with_regex_characters_is_hidden():
    # a profile header uploaded as "Untitled design (7).png": Media.filename
    # strips the trailing ")", leaving an unbalanced "(" at position 16
    url = "https://public.onlyfans.com/files/a/ab/abc/123/Untitled design (7).png"
    logged = log_utils.get_url_log(_media(url, "Untitled design (7"))
    assert "Untitled design (7" not in logged and "{hidden}" in logged


def test_ordinary_filename_is_hidden():
    url = "https://cdn2.onlyfans.com/files/a/ab/abc/1000x1800_cb46.jpeg"
    logged = log_utils.get_url_log(_media(url, "1000x1800_cb46"))
    assert "1000x1800_cb46" not in logged

# ----------------------------------------------------------------------
# From test_batch_tempfile_cleanup_env.py
# OFSC_BATCH_TEMPFILE_CLEANUP accepts "true" like the other flags (#184).
# ----------------------------------------------------------------------

import pytest

from ofscraper.utils.of_env.values.path.general import load_general_paths_config


@pytest.mark.parametrize(
    "value,expected",
    [("true", True), ("True", True), ("TRUE", True), ("1", True),
     ("false", False), ("0", False), ("", False)],
)
def test_batch_tempfile_cleanup_flag(monkeypatch, value, expected):
    monkeypatch.setenv("OFSC_BATCH_TEMPFILE_CLEANUP", value)
    assert load_general_paths_config()["BATCH_TEMPFILE_CLEANUP"] is expected


def test_batch_tempfile_cleanup_defaults_to_off(monkeypatch):
    monkeypatch.delenv("OFSC_BATCH_TEMPFILE_CLEANUP", raising=False)
    assert load_general_paths_config()["BATCH_TEMPFILE_CLEANUP"] is False

# ----------------------------------------------------------------------
# From test_temp_cleanup_prefix.py
# temp_cleanup() removes temp_ files by name, not by full path.
# ----------------------------------------------------------------------

from types import SimpleNamespace

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.paths.paths as paths


def _run_cleanup(monkeypatch, root):
    real_getattr = paths.of_env.getattr

    def fake_getattr(key, *args, **kwargs):
        if key == "BATCH_TEMPFILE_CLEANUP":
            return True
        return real_getattr(key, *args, **kwargs)

    monkeypatch.setattr(paths.of_env, "getattr", fake_getattr)
    monkeypatch.setattr(
        paths.settings, "get_settings", lambda: SimpleNamespace(auto_resume=False)
    )
    monkeypatch.setattr(paths.data, "get_TempDir", lambda *a, **k: str(root))
    paths.temp_cleanup()


def test_removes_temp_prefixed_files(monkeypatch, tmp_path):
    sub = tmp_path / "creator" / "Videos"
    sub.mkdir(parents=True)
    temp_top = tmp_path / "temp_123.mp4"
    temp_nested = sub / "temp_456.mp4"
    part = sub / "video.mp4.part"
    for f in (temp_top, temp_nested, part):
        f.write_bytes(b"x")

    _run_cleanup(monkeypatch, tmp_path)

    assert not temp_top.exists()
    assert not temp_nested.exists()
    assert not part.exists()


def test_keeps_other_files_and_folders(monkeypatch, tmp_path):
    # A folder named temp_ is left alone, and so is a file inside it or
    # with temp_ in the middle of its name.
    temp_dir = tmp_path / "temp_folder"
    temp_dir.mkdir()
    inside = temp_dir / "keep.mp4"
    middle = tmp_path / "my_temp_clip.mp4"
    done = tmp_path / "finished.mp4"
    for f in (inside, middle, done):
        f.write_bytes(b"x")

    _run_cleanup(monkeypatch, tmp_path)

    assert temp_dir.is_dir()
    assert inside.exists()
    assert middle.exists()
    assert done.exists()

# ----------------------------------------------------------------------
# From test_resource_cleanup.py
# ----------------------------------------------------------------------

import logging
import logging.handlers
import queue
import threading
from types import SimpleNamespace

import diskcache

import ofscraper.utils.cache.cache as cache_mod
import ofscraper.utils.logs.close as close_mod
import ofscraper.utils.logs.other as other_logs


def test_cache_get_on_worker_thread_closes_its_connection(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod.settings, "get_settings", lambda: SimpleNamespace(cached_disabled=False))
    monkeypatch.setattr(cache_mod.common_paths, "getcachepath", lambda: str(tmp_path))
    monkeypatch.setattr(cache_mod.data, "get_cache_mode", lambda: diskcache.Disk)
    monkeypatch.setattr(cache_mod, "cache", None)
    cache_mod.set("k", "v")
    left_open = []

    def worker():
        assert cache_mod.get("k") == "v"
        left_open.append(getattr(cache_mod.cache._local, "con", None))

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert left_open == [None]
    cache_mod.close()


def test_graceful_close_closes_log_files(tmp_path, monkeypatch):
    fh = logging.FileHandler(tmp_path / "x.log", encoding="utf-8")
    q = queue.Queue()
    listener = logging.handlers.QueueListener(q, fh)
    listener.start()
    monkeypatch.setattr(other_logs, "log_queue_listener", listener, raising=False)
    shared = logging.getLogger("shared")
    qh = logging.handlers.QueueHandler(q)
    shared.addHandler(qh)
    close_mod.gracefulClose()
    assert fh.stream is None  # FileHandler.close() drops the stream
    assert shared.handlers == []
