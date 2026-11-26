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


def test_successful_run_exits_0(monkeypatch):
    monkeypatch.setattr(run, "check_database", lambda: None)
    monkeypatch.setattr(run, "start_manager", lambda: None)
    with pytest.raises(SystemExit) as exit_info:
        run.main()
    assert exit_info.value.code == 0


def test_exit_status_most_severe_wins_regardless_of_order():
    import ofscraper.main.close.exit_status as exit_status

    ordered = [
        exit_status.OK,
        exit_status.USAGE,
        exit_status.PARTIAL,
        exit_status.UNAVAILABLE,
        exit_status.AUTH,
        exit_status.CONFIG,
        exit_status.ERROR,
        exit_status.INTERRUPTED,
    ]
    try:
        for i, low in enumerate(ordered):
            for high in ordered[i + 1 :]:
                exit_status.reset()
                exit_status.record(low)
                exit_status.record(high)
                assert exit_status.code() == int(high)

                exit_status.reset()
                exit_status.record(high)
                exit_status.record(low)
                assert exit_status.code() == int(high)
    finally:
        exit_status.reset()


def test_run_main_exit_codes(monkeypatch):
    import ofscraper.commands.utils.command as command_mod
    import ofscraper.data.posts.post as post_mod
    import ofscraper.db.postgres as postgres
    import ofscraper.main.close.exit_status as exit_status
    import ofscraper.main.close.final.final as final_mod
    import ofscraper.managers.stats as stats_mod

    monkeypatch.setattr(run, "check_database", lambda: None)
    monkeypatch.setattr(run.exit_manager, "shutdown", lambda: None)
    monkeypatch.setattr(run.exit_manager, "forcedShutDown", lambda: None)
    monkeypatch.setattr(
        run.console, "get_shared_console", lambda: SimpleNamespace(print=lambda *a, **k: None)
    )

    # creator failure -> 4
    monkeypatch.setattr(
        run,
        "start_manager",
        lambda: command_mod.log_user_failure("a_creator", RuntimeError("boom")),
    )
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.PARTIAL

    # area failure -> 4
    monkeypatch.setattr(
        post_mod,
        "log",
        SimpleNamespace(warning=lambda *a: None, traceback_=lambda *a: None),
    )
    monkeypatch.setattr(
        run,
        "start_manager",
        lambda: post_mod.log_area_failure("a_creator", "Timeline", RuntimeError("boom")),
    )
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.PARTIAL

    # download failure via final_action + StatsManager -> 4
    sm = stats_mod.StatsManager()
    dl = sm._get_stat_obj("a_creator", "download")
    dl.failed_count = 1
    monkeypatch.setattr(final_mod, "final_script", lambda *a: None)
    monkeypatch.setattr(final_mod, "printEndValues", lambda: None)
    monkeypatch.setattr(
        final_mod.manager,
        "Manager",
        SimpleNamespace(stats_manager=sm, _stats_manager=sm),
    )
    monkeypatch.setattr(run, "start_manager", final_mod.final_action)
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.PARTIAL

    # skipped files only -> 0
    sm_clean = stats_mod.StatsManager()
    dl_clean = sm_clean._get_stat_obj("a_creator", "download")
    dl_clean.skipped_count = 5
    monkeypatch.setattr(
        final_mod.manager,
        "Manager",
        SimpleNamespace(stats_manager=sm_clean, _stats_manager=sm_clean),
    )
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.OK

    # auth failure -> 3
    def auth_fail():
        raise SystemExit(exit_status.AUTH)

    monkeypatch.setattr(run, "start_manager", auth_fail)
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.AUTH

    # maintenance -> 5
    def maintenance():
        raise SystemExit(exit_status.UNAVAILABLE)

    monkeypatch.setattr(run, "start_manager", maintenance)
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.UNAVAILABLE

    # database configuration error -> 6
    def db_down():
        raise postgres.PostgresUnavailable("db unreachable")

    monkeypatch.setattr(run, "start_manager", db_down)
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.CONFIG

    # KeyboardInterrupt -> 130
    def interrupt():
        raise KeyboardInterrupt

    monkeypatch.setattr(run, "start_manager", interrupt)
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.INTERRUPTED


def test_auth_fail_and_unreadable_auth_exit_3(monkeypatch):
    import ofscraper.main.close.exit_status as exit_status
    import ofscraper.sites.fansly.auth as fansly_auth
    import ofscraper.utils.auth.file as auth_file
    import ofscraper.utils.auth.make as auth_make

    monkeypatch.setattr(
        auth_make.settings, "get_settings", lambda: SimpleNamespace(auth_fail=True)
    )
    with pytest.raises(SystemExit) as exc:
        auth_make.make_auth()
    assert exc.value.code == exit_status.AUTH

    with pytest.raises(SystemExit) as exc:
        fansly_auth.make_auth()
    assert exc.value.code == exit_status.AUTH

    monkeypatch.setattr(
        auth_file.auth_dict,
        "get_auth_dict",
        lambda: (_ for _ in ()).throw(FileNotFoundError("missing")),
    )
    monkeypatch.setattr(auth_file.auth_error, "handle_auth_errors", lambda e: "quit")
    with pytest.raises(SystemExit) as exc:
        auth_file.read_auth()
    assert exc.value.code == exit_status.AUTH


def test_rejected_login_without_a_console_exits_3(monkeypatch, tmp_path):
    # a scheduled run or a --profiles child: no one can answer the Auth Menu,
    # so the run ends with "login failed", not the generic error
    import ofscraper.data.api.init as init
    import ofscraper.main.close.exit_status as exit_status
    import ofscraper.sites.fansly.auth as fansly_auth
    import ofscraper.utils.checkers as checkers
    import ofscraper.utils.interactive as interactive

    monkeypatch.setattr(run, "check_database", lambda: None)
    monkeypatch.setattr(run.exit_manager, "shutdown", lambda: None)
    monkeypatch.setattr(interactive, "is_interactive", lambda: False)
    monkeypatch.setattr(init, "auth_status", lambda: ("DOWN", None))
    monkeypatch.setattr(checkers.auth_file, "read_auth", lambda: {})
    monkeypatch.setattr(
        checkers.make.settings, "get_settings", lambda: SimpleNamespace(auth_fail=False)
    )
    monkeypatch.setattr(checkers.make.common_paths, "get_auth_file", lambda: tmp_path / "auth.json")
    monkeypatch.setattr(fansly_auth, "auth_path", lambda: tmp_path / "fansly_auth.json")
    monkeypatch.setattr(run, "start_manager", checkers.check_auth)
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.AUTH

    monkeypatch.setattr(checkers.sites, "is_fansly", lambda: True)
    monkeypatch.setattr(fansly_auth, "load", lambda: {})
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.AUTH


def test_unreadable_config_in_load_exits_6(monkeypatch):
    import ofscraper.main.close.exit_status as exit_status
    import ofscraper.main.open.load as load

    def bad_config():
        raise ValueError("broken config")

    monkeypatch.setattr(load, "systemSet", lambda: None)
    monkeypatch.setattr(load, "settings_loader", lambda: None)
    monkeypatch.setattr(load, "setdate", lambda: None)
    monkeypatch.setattr(load, "readConfig", bad_config)
    with pytest.raises(SystemExit) as exc:
        load.main()
    assert exc.value.code == exit_status.CONFIG


def test_malformed_config_json_exits_6(monkeypatch, tmp_path):
    # the real loader: settings are read before readConfig(), and they open
    # config.json first
    import ofscraper.main.close.exit_status as exit_status
    import ofscraper.main.open.load as load
    import ofscraper.utils.config.config as config_
    import ofscraper.utils.settings as settings

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    config_dir = tmp_path / ".config" / "ofscraper"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(settings, "settings", {})
    monkeypatch.setattr(config_, "config", None)
    monkeypatch.setattr(load, "systemSet", lambda: None)
    with pytest.raises(SystemExit) as exc:
        load.main()
    assert exc.value.code == exit_status.CONFIG


def test_corrupt_fansly_auth_file_exits_3(monkeypatch, tmp_path):
    import ofscraper.main.close.exit_status as exit_status
    import ofscraper.sites.fansly.auth as fansly_auth

    for text in ("{not json", "[1, 2]"):
        path = tmp_path / "fansly_auth.json"
        path.write_text(text, encoding="utf-8")
        monkeypatch.setattr(fansly_auth, "auth_path", lambda: path)
        with pytest.raises(SystemExit) as exc:
            fansly_auth.load()
        assert exc.value.code == exit_status.AUTH
        path.unlink()


def test_ctrl_c_during_error_shutdown_exits_130(monkeypatch):
    import ofscraper.main.close.exit_status as exit_status

    def interrupted_shutdown():
        raise KeyboardInterrupt

    monkeypatch.setattr(run, "check_database", lambda: None)
    monkeypatch.setattr(run, "start_manager", _fail)
    monkeypatch.setattr(run.exit_manager, "shutdown", interrupted_shutdown)
    monkeypatch.setattr(run.exit_manager, "forcedShutDown", lambda: None)
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == exit_status.INTERRUPTED


def test_daemon_pass_logs_outcome_and_resets_status(monkeypatch, caplog):
    import queue
    import ofscraper.commands.scraper.scraper as scraper
    import ofscraper.main.close.exit_status as exit_status

    class TwoPassQueue(queue.Queue):
        def get(self, *args, **kwargs):
            if self.empty():
                raise KeyboardInterrupt
            return super().get(*args, **kwargs)

    pass_num = 0

    def runner():
        nonlocal pass_num
        pass_num += 1
        if pass_num == 1:
            exit_status.record(exit_status.PARTIAL)

    jobs = TwoPassQueue()
    monkeypatch.setattr(scraper, "jobqueue", jobs)
    monkeypatch.setattr(scraper.exit, "sigterm_as_keyboard_interrupt", lambda: None)
    monkeypatch.setattr(scraper.checkers, "check_auth", lambda: None)
    monkeypatch.setattr(scraper, "scraperManager", lambda: SimpleNamespace(runner=runner))
    monkeypatch.setattr(
        scraper.settings, "get_settings", lambda: SimpleNamespace(output_level="NORMAL")
    )
    monkeypatch.setattr(
        scraper.manager,
        "Manager",
        SimpleNamespace(current_model_manager=SimpleNamespace(sync_models=lambda: None)),
    )
    monkeypatch.setattr(scraper.actions, "select_areas", lambda: None)
    monkeypatch.setattr(scraper, "set_schedule", lambda fn, **kw: jobs.put(fn))
    monkeypatch.setattr(scraper.live, "watch_enabled", lambda: False)
    monkeypatch.setattr(scraper.action_prompts, "restore_session_args", lambda: None)

    with caplog.at_level(logging.INFO, logger="shared"):
        with pytest.raises(KeyboardInterrupt):
            scraper.daemon_process()

    assert "Daemon pass finished with status 4 (partial)" in caplog.text
    assert "Daemon pass finished with status 0 (ok)" in caplog.text
    assert exit_status.code() == exit_status.OK


def test_keyboard_interrupt_in_run_exits_130(monkeypatch):
    def interrupt():
        raise KeyboardInterrupt

    shutdowns = []
    monkeypatch.setattr(run, "check_database", lambda: None)
    monkeypatch.setattr(run, "start_manager", interrupt)
    monkeypatch.setattr(run.exit_manager.time, "sleep", lambda s: None)
    # the ordinary shutdown, which closes the logs: the Discord handler sends
    # what it has queued (the "stopped" summary) as it closes
    monkeypatch.setattr(run.exit_manager.close_log, "gracefulClose", lambda: shutdowns.append("logs"))
    monkeypatch.setattr(run.exit_manager, "forcedShutDown", lambda: shutdowns.append("forced"))
    monkeypatch.setattr(
        run.console, "get_shared_console", lambda: SimpleNamespace(print=lambda *a, **k: None)
    )
    with pytest.raises(SystemExit) as exit_info:
        run.main()
    assert exit_info.value.code == 130
    assert shutdowns == ["logs"]


def test_second_ctrl_c_during_shutdown_skips_to_the_forced_shutdown(monkeypatch):
    import signal

    def interrupt():
        raise KeyboardInterrupt

    steps = []

    def slow_close():
        steps.append("logs")
        signal.raise_signal(signal.SIGINT)  # the second Ctrl+C
        steps.append("logs closed")

    old = signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        monkeypatch.setattr(run, "check_database", lambda: None)
        monkeypatch.setattr(run, "start_manager", interrupt)
        monkeypatch.setattr(run.exit_manager.time, "sleep", lambda s: None)
        monkeypatch.setattr(run.exit_manager.close_log, "gracefulClose", slow_close)
        monkeypatch.setattr(run.exit_manager, "forcedShutDown", lambda: steps.append("forced"))
        monkeypatch.setattr(
            run.console, "get_shared_console", lambda: SimpleNamespace(print=lambda *a, **k: None)
        )
        with pytest.raises(SystemExit) as exit_info:
            run.main()
    finally:
        signal.signal(signal.SIGINT, old)
    assert exit_info.value.code == 130
    # the second Ctrl+C stops the ordinary shutdown instead of waiting for it
    assert steps == ["logs", "forced"]


def test_sigterm_interrupt_in_run_exits_0(monkeypatch):
    def sigterm():
        raise run.exit_context.SigtermInterrupt

    shutdowns = []
    monkeypatch.setattr(run, "check_database", lambda: None)
    monkeypatch.setattr(run, "start_manager", sigterm)
    monkeypatch.setattr(run.exit_manager.time, "sleep", lambda s: None)
    monkeypatch.setattr(run.exit_manager.close_log, "gracefulClose", lambda: shutdowns.append("logs"))
    monkeypatch.setattr(run.exit_manager, "forcedShutDown", lambda: shutdowns.append("forced"))
    monkeypatch.setattr(
        run.console, "get_shared_console", lambda: SimpleNamespace(print=lambda *a, **k: None)
    )
    run.main()
    assert shutdowns == ["logs"]


def test_startup_error_in_load_exits_1(monkeypatch):
    import ofscraper.main.open.load as load

    def boom():
        raise RuntimeError("startup failed")

    monkeypatch.setattr(load, "systemSet", lambda: None)
    monkeypatch.setattr(load, "settings_loader", lambda: None)
    monkeypatch.setattr(load, "setdate", lambda: None)
    monkeypatch.setattr(load, "readConfig", lambda: None)
    monkeypatch.setattr(load, "setLogger", boom)
    with pytest.raises(SystemExit) as exit_info:
        load.main()
    assert exit_info.value.code == 1

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
