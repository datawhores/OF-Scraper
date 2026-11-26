"""Tests for running offline tools as ``ofscraper <tool>``."""

import os
import pathlib
import subprocess
import sys

import pytest

import ofscraper.__main__ as entrypoint
import ofscraper.commands.tools as tools
import ofscraper.utils.args.parse.commands.main as main_cmd

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("tool_name", sorted(tools.TOOLS))
def test_every_tool_in_table_imports(tool_name):
    loader, summary = tools.TOOLS[tool_name]
    assert summary
    fn = loader()
    assert callable(fn)


@pytest.mark.parametrize("tool_name", sorted(tools.TOOLS))
def test_tool_name_routes_to_module_main_with_remaining_args(monkeypatch, tool_name):
    received = {}
    load_called = False

    def fake_main(argv=None):
        received["argv"] = argv
        received["prog"] = sys.argv[0]
        return 7

    def fake_load():
        nonlocal load_called
        load_called = True

    monkeypatch.setitem(tools.TOOLS, tool_name, (lambda: fake_main, "summary"))
    monkeypatch.setattr(entrypoint.load, "main", fake_load)

    saved_argv = list(sys.argv)
    code = entrypoint.main([tool_name, "--flag", "value"])
    assert code == 7
    assert received == {"argv": ["--flag", "value"], "prog": f"ofscraper {tool_name}"}
    assert not load_called
    assert sys.argv == saved_argv


@pytest.mark.parametrize("argv", [[], ["--help"], ["db", "--help"], ["--profile", "x", "stash_sync"]])
def test_non_tool_first_arg_reaches_load_main(monkeypatch, argv):
    called = []
    monkeypatch.setattr(entrypoint.load, "main", lambda: called.append(True))
    result = entrypoint.main(argv)
    assert result is None
    assert called == [True]


@pytest.mark.slow
@pytest.mark.parametrize("tool_name", sorted(tools.TOOLS))
def test_tool_help_in_empty_home_creates_nothing(tmp_path, tool_name):
    empty_home = tmp_path / "home"
    empty_home.mkdir()
    env = {
        **os.environ,
        "HOME": str(empty_home),
        "USERPROFILE": str(empty_home),
        "PYTHONPATH": str(ROOT),
        # unreachable PostgreSQL URL: normal startup would try to connect and fail
        "OFSC_DATABASE_URL": "postgresql://user:pass@127.0.0.1:1/nonexistent",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "ofscraper", tool_name, "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert f"usage: ofscraper {tool_name}" in proc.stdout
    assert list(empty_home.iterdir()) == []


def test_main_help_lists_offline_tools():
    assert main_cmd.program.epilog is not None
    assert "Offline tools" in main_cmd.program.epilog
    for name in tools.TOOLS:
        assert name in main_cmd.program.epilog
