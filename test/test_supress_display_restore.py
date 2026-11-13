"""A SUPRESS_*_DISPLAY value applies only while its screen is up (#262).

Opening a screen set the shared console's quiet flag from its SUPRESS_* value
and nothing put it back, so with --output LOW and SUPRESS_DOWNLOAD_DISPLAY=False
the whole console stayed loud for the rest of the run."""

import io
import sys

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.args.globals as global_args
import ofscraper.utils.console as console
import ofscraper.utils.live.screens as screens
from ofscraper.utils.args.parse.commands.main import program


class _Live:
    """Stands in for the Rich live display, so no terminal is needed."""

    renderable = None
    is_started = True

    def start(self):
        pass

    def update(self, layout, refresh=False):
        self.renderable = layout


@pytest.fixture
def run(monkeypatch):
    def start(argv, **env):
        monkeypatch.setattr(sys, "argv", ["ofscraper", *argv])
        monkeypatch.setattr(global_args, "args", None)
        # parse_args registers the subcommands, which can only happen once a process
        if "manual" in program.commands:
            monkeypatch.setattr(program, "add_command", lambda *a, **k: None)
        for key, value in env.items():
            monkeypatch.setenv(key, value)  # the bare name is read on every lookup
        monkeypatch.setattr(screens, "get_live", _Live)
        monkeypatch.setattr(console, "shared_console", None)
        shared = console.get_shared_console()
        shared.file = io.StringIO()
        shared.width = 200
        return shared

    return start


def _seen(shared):
    return shared.file.getvalue().split()


def test_false_with_low_shows_only_the_download_screen(run):
    shared = run(["--output", "LOW"], SUPRESS_DOWNLOAD_DISPLAY="False")
    shared.print("before")
    with screens.setup_live("download"):
        assert shared.quiet is False
        shared.print("during")
    assert shared.quiet is True  # back to what --output LOW says
    shared.print("after")
    assert _seen(shared) == ["during"]


def test_true_hides_only_during_the_screen(run):
    shared = run(["--output", "NORMAL"], SUPRESS_DOWNLOAD_DISPLAY="True")
    shared.print("before")
    with screens.setup_live("download"):
        assert shared.quiet is True
        shared.print("during")
    assert shared.quiet is False
    shared.print("after")
    assert _seen(shared) == ["before", "after"]


def test_nested_screens_restore_in_order(run):
    shared = run(
        ["--output", "LOW"],
        SUPRESS_API_DISPLAY="False",
        SUPRESS_DOWNLOAD_DISPLAY="True",
    )
    with screens.setup_live("api"):  # shows
        assert shared.quiet is False
        with screens.setup_live("download"):  # hides
            assert shared.quiet is True
        assert shared.quiet is False  # back to the api screen's value
        with screens.setup_live("main_activity"):  # no SUPRESS_* key of its own
            assert shared.quiet is False
    assert shared.quiet is True


def test_restored_even_when_the_screen_raises(run):
    shared = run(["--output", "LOW"], SUPRESS_DOWNLOAD_DISPLAY="False")
    with pytest.raises(RuntimeError):
        with screens.setup_live("download"):
            raise RuntimeError("boom")
    assert shared.quiet is True


class _BrokenLive(_Live):
    def __init__(self, fail_on):
        self.fail_on = fail_on
        self.calls = 0

    def update(self, layout, refresh=False):
        self.calls += 1
        if self.calls == self.fail_on:
            raise RuntimeError("live update failed")
        self.renderable = layout


def test_restored_when_the_screen_fails_to_open(run, monkeypatch):
    shared = run(["--output", "LOW"], SUPRESS_DOWNLOAD_DISPLAY="False")
    monkeypatch.setattr(screens, "get_live", lambda: _BrokenLive(fail_on=1))
    with pytest.raises(RuntimeError):
        with screens.setup_live("download"):
            pass
    assert shared.quiet is True


def test_restored_when_closing_the_screen_fails(run, monkeypatch):
    shared = run(["--output", "LOW"], SUPRESS_DOWNLOAD_DISPLAY="False")
    live = _BrokenLive(fail_on=2)
    live.renderable = "previous screen"
    monkeypatch.setattr(screens, "get_live", lambda: live)
    with pytest.raises(RuntimeError):
        with screens.setup_live("download"):
            pass
    assert shared.quiet is True


def test_afterwards_the_console_follows_the_options_again(run):
    shared = run(["--output", "NORMAL"], SUPRESS_DOWNLOAD_DISPLAY="True")
    with screens.setup_live("download"):
        pass
    assert shared.quiet is False
    # the output level changes later in the run: quiet follows it, not a
    # value pinned by the screen
    global_args.args.output_level = "LOW"
    assert shared.quiet is True


def test_unset_leaves_quiet_alone(run, monkeypatch):
    monkeypatch.delenv("SUPRESS_DOWNLOAD_DISPLAY", raising=False)
    monkeypatch.delenv("OFSC_SUPRESS_DOWNLOAD_DISPLAY", raising=False)
    shared = run(["--output", "LOW"])
    with screens.setup_live("download"):
        assert shared.quiet is True
    assert shared.quiet is True
