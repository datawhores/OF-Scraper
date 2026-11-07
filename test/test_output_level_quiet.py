"""--output LOW and --output PROMPT make the console quiet (#255).

low_output() read args.output, but the option is stored as output_level, so
the check never matched and only --no-rich made the console quiet. These
tests go through the real command-line parse."""

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
