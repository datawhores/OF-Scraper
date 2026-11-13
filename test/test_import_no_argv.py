"""Importing ofscraper doesn't parse the importing program's command line (#245).

The shared console's quiet setting follows the output options when it's used,
including options set later through settings.update_args."""

import io
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see conftest)
import ofscraper.utils.args.globals as global_args
import ofscraper.utils.console as console
import ofscraper.utils.settings as settings

ROOT = Path(__file__).resolve().parents[1]

IMPORT_SCRIPT = """
import sys
sys.argv = ["host_program", *sys.argv[1:]]
import ofscraper.__main__
import ofscraper.utils.args.globals as global_args
print("imported, args parsed:", global_args.args is not None)
"""


@pytest.mark.parametrize("argv", [["--port", "8080"], ["--help"]])
def test_import_with_another_programs_arguments_does_not_exit(argv):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run(
        [sys.executable, "-c", IMPORT_SCRIPT, *argv],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert "imported, args parsed: False" in out.stdout
    assert "Usage" not in out.stdout + out.stderr


def _console(monkeypatch):
    """A fresh shared console, made the way the app makes it, printing to a buffer."""
    monkeypatch.setattr(console, "shared_console", None)
    con = console.get_shared_console()
    buf = io.StringIO()
    con.file = buf
    return con, buf


def _args(output="NORMAL", no_rich=False):
    # --output is stored as output_level
    return SimpleNamespace(output_level=output, no_rich=no_rich)


@pytest.mark.parametrize(
    "output,no_rich,quiet",
    [("NORMAL", False, False), ("DEBUG", False, False), ("LOW", False, True),
     ("OFF", False, True), ("PROMPT", False, True), ("NORMAL", True, True)],
)
def test_quiet_follows_the_output_options(monkeypatch, output, no_rich, quiet):
    monkeypatch.setattr(settings, "get_args", lambda copy=False: _args(output, no_rich))
    con, buf = _console(monkeypatch)
    con.print("hello")
    assert con.quiet is quiet
    assert ("hello" in buf.getvalue()) is not quiet


def test_quiet_follows_options_set_later_through_update_args(monkeypatch):
    monkeypatch.setattr(global_args, "args", _args("NORMAL"))
    monkeypatch.setattr(settings, "setup_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(settings, "settings", settings.settings)
    con, buf = _console(monkeypatch)
    con.print("before")
    settings.update_args(_args("LOW"))
    con.print("hidden")
    settings.update_args(_args("NORMAL"))
    con.print("after")
    assert buf.getvalue().split() == ["before", "after"]


def test_assigning_quiet_overrides_the_options(monkeypatch):
    # the table app and the SUPRESS_*_DISPLAY settings assign quiet directly
    monkeypatch.setattr(settings, "get_args", lambda copy=False: _args("NORMAL"))
    con, buf = _console(monkeypatch)
    con.quiet = True
    con.print("hidden")
    assert con.quiet is True
    assert buf.getvalue() == ""
