"""Optional extras installed on first use (``ofscraper.utils.system.extras``).

No package is installed: ``subprocess.run`` is replaced, and conftest sets
``OFSC_INSTALL_EXTRAS=False`` so no other test can start a real install.
"""

import os
import pathlib
import site
import subprocess
import sys
import tomllib
from types import SimpleNamespace

import pytest

from ofscraper.utils.system import extras

ROOT = pathlib.Path(__file__).resolve().parents[1]


class _Terminal:
    """stdin of someone at a terminal."""

    def __init__(self, tty=True):
        self.tty = tty

    def isatty(self):
        return self.tty


@pytest.fixture
def runs(monkeypatch):
    """Turn installs on, answer yes at a terminal, and record each command
    instead of running it."""
    import ofscraper.utils.settings as settings

    monkeypatch.setenv("INSTALL_EXTRAS", "True")
    monkeypatch.delenv("SUDO_USER", raising=False)
    monkeypatch.setattr(sys, "stdin", _Terminal())
    answer = {"text": "y", "prompts": []}

    def ask(prompt=""):
        answer["prompts"].append(prompt)
        return answer["text"]

    monkeypatch.setattr("builtins.input", ask)
    monkeypatch.setattr(settings, "get_args", lambda *a, **k: SimpleNamespace(daemon=None))
    extras.install.cache_clear()
    extras.install_chromium.cache_clear()
    calls = []
    kwargs_seen = []
    result = {"code": 0, "stderr": ""}

    def run(cmd, **kwargs):
        calls.append(cmd)
        kwargs_seen.append(kwargs)
        return SimpleNamespace(returncode=result["code"], stdout="", stderr=result["stderr"])

    monkeypatch.setattr(extras.subprocess, "run", run)
    # whether this venv has pip or uv doesn't matter here
    monkeypatch.setattr(extras, "pip_command", lambda reqs: [sys.executable, "-m", "pip", "install", *reqs])
    yield SimpleNamespace(calls=calls, kwargs=kwargs_seen, result=result, answer=answer)
    extras.install.cache_clear()
    extras.install_chromium.cache_clear()


def test_the_extras_match_pyproject():
    with open(ROOT / "pyproject.toml", "rb") as f:
        declared = tomllib.load(f)["project"]["optional-dependencies"]
    for name, requirements in extras.EXTRAS.items():
        assert declared[name] == requirements


def test_the_postgres_driver_comes_with_the_scraper_where_it_has_wheels():
    from packaging.requirements import Requirement

    with open(ROOT / "pyproject.toml", "rb") as f:
        project = tomllib.load(f)["project"]
    [driver] = [Requirement(r) for r in project["dependencies"] if r.startswith("psycopg")]
    assert str(driver).split(";")[0] == Requirement(extras.EXTRAS["postgres"][0]).__str__()

    def on(sys_platform, machine):
        return driver.marker.evaluate({"sys_platform": sys_platform, "platform_machine": machine})

    for where in [("win32", "AMD64"), ("darwin", "arm64"), ("darwin", "x86_64"),
                  ("linux", "x86_64"), ("linux", "aarch64"), ("linux", "ppc64le"), ("linux", "riscv64")]:
        assert on(*where), where
    # no prebuilt driver: a required one would make the whole install fail there
    for where in [("win32", "ARM64"), ("android", "aarch64"), ("linux", "armv7l"),
                  # parts of a listed name: an "in '...'" marker matched these
                  ("linux", "ppc64"), ("linux", "x86"), ("linux", "64")]:
        assert not on(*where), where


def test_tests_never_install_anything():
    assert not extras.enabled()


def test_installs_the_extra_into_the_running_python_once(runs, monkeypatch):
    monkeypatch.setattr(extras, "pip_command", lambda reqs: [sys.executable, "-m", "pip", "install", *reqs])
    assert extras.install("postgres") is True
    assert extras.install("postgres") is True
    assert runs.calls == [[sys.executable, "-m", "pip", "install", "psycopg[binary,pool]>=3.3.9"]]


def test_uses_uv_when_this_python_has_no_pip(monkeypatch, tmp_path):
    monkeypatch.setattr(extras.importlib.util, "find_spec", lambda name: None)
    uv = tmp_path / ("uv.exe" if sys.platform == "win32" else "uv")
    uv.write_text("")
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    # --no-config: a uv.toml or pyproject.toml where OF-Scraper runs can't add an index
    cmd = extras.pip_command(["x"])
    assert os.path.normcase(cmd[0]) == os.path.normcase(str(uv))  # Windows may say uv.EXE
    assert cmd[1:] == ["pip", "install", "--no-config", "--python", sys.executable, "x"]


def test_uv_in_the_working_directory_is_not_used(monkeypatch, tmp_path):
    # an empty PATH entry (a trailing separator is common on Windows) means
    # the working directory, and so does "."
    monkeypatch.setattr(extras.importlib.util, "find_spec", lambda name: None)
    planted = tmp_path / ("uv.exe" if sys.platform == "win32" else "uv")
    planted.write_text("")
    planted.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tmp_path / "empty"), ".", ""]))
    assert extras.pip_command(["x"]) is None


def test_pip_in_the_working_directory_is_not_run(monkeypatch, tmp_path):
    # `python -m pip` imports pip.py from the working directory first
    marker = tmp_path / "ran"
    (tmp_path / "pip.py").write_text(f"open({str(marker)!r}, 'w').close()\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(extras.importlib.util, "find_spec", lambda name: object())
    cmd = extras.pip_command([])
    cmd[cmd.index("install")] = "--version"
    extras._run(cmd, "pip")
    assert not marker.exists()


def test_the_install_keeps_pythonuserbase(monkeypatch, tmp_path):
    # pip --user installs under PYTHONUSERBASE, and this run imports from
    # there, so the install has to see the same value
    monkeypatch.setenv("PYTHONUSERBASE", str(tmp_path))
    r = subprocess.run(
        [*extras.PYTHON, "-c", "import site; print(site.getuserbase())"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=extras._env(),
    )
    assert os.path.normcase(r.stdout.strip()) == os.path.normcase(str(tmp_path))


def test_the_install_sees_what_pythonpath_adds(monkeypatch, tmp_path):
    # pip_command checks for pip in this run, which reads PYTHONPATH; the
    # install has to find the same pip
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "ofs_pythonpath_probe.py").write_text("")
    monkeypatch.setenv("PYTHONPATH", str(lib))
    r = subprocess.run(
        [*extras.PYTHON, "-c", "import ofs_pythonpath_probe"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=extras._env(),
    )
    assert r.returncode == 0, r.stderr


def test_the_install_runs_from_an_empty_directory(runs, monkeypatch, tmp_path):
    (tmp_path / "uv.toml").write_text('index-url = "http://127.0.0.1:9/"\n')
    monkeypatch.chdir(tmp_path)
    seen = []

    def run(cmd, **kwargs):
        seen.append((kwargs.get("cwd"), os.listdir(kwargs.get("cwd") or ".")))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(extras.subprocess, "run", run)
    assert extras.install("postgres") is True
    assert extras.install_chromium() is True
    assert len(seen) == 2
    for cwd, listing in seen:
        assert cwd and pathlib.Path(cwd) != tmp_path
        assert listing == []


def test_the_chromium_download_does_not_read_the_working_directory(runs):
    assert extras.install_chromium() is True
    assert runs.calls[0][:2] == [sys.executable, "-P"]


def test_asks_before_installing(runs):
    runs.answer["text"] = "n"
    assert extras.install("live") is False
    assert extras.install("live") is False
    assert runs.calls == []
    assert len(runs.answer["prompts"]) == 1  # asked once per run
    assert "playwright" in runs.answer["prompts"][0]


def test_without_a_terminal_it_says_the_command_instead(runs, monkeypatch, caplog):
    # cron, a service, docker run without -it
    monkeypatch.setattr(sys, "stdin", _Terminal(tty=False))
    with caplog.at_level("WARNING", logger="shared"):
        assert extras.install("postgres") is False
        assert extras.install_chromium() is False
    assert runs.calls == [] and runs.answer["prompts"] == []
    assert "pip install 'psycopg[binary,pool]>=3.3.9'" in caplog.text or (
        'pip install "psycopg[binary,pool]>=3.3.9"' in caplog.text
    )
    assert "playwright install chromium" in caplog.text


def test_without_stdin_it_says_the_command_instead(runs, monkeypatch):
    monkeypatch.setattr(sys, "stdin", None)
    assert extras.install("postgres") is False
    assert runs.calls == []


def test_the_daemon_does_not_install(runs, monkeypatch, caplog):
    import ofscraper.utils.settings as settings

    monkeypatch.setattr(settings, "get_args", lambda *a, **k: SimpleNamespace(daemon=60))
    with caplog.at_level("WARNING", logger="shared"):
        assert extras.install("live") is False
    assert runs.calls == [] and runs.answer["prompts"] == []
    assert "playwright" in caplog.text


def test_root_under_sudo_does_not_install(runs, monkeypatch, caplog):
    monkeypatch.setattr(extras.os, "geteuid", lambda: 0, raising=False)
    monkeypatch.setenv("SUDO_USER", "someone")
    with caplog.at_level("WARNING", logger="shared"):
        assert extras.install("postgres") is False
    assert runs.calls == [] and runs.answer["prompts"] == []
    assert "sudo" in caplog.text


def test_the_install_uses_ofsc_proxy(runs, monkeypatch):
    import ofscraper.utils.of_env.of_env as of_env

    real = of_env.getattr
    proxy = "http://user:secret@proxy.example:3128"
    monkeypatch.setattr(of_env, "getattr", lambda key, *a, **k: proxy if key == "PROXY" else real(key, *a, **k))
    assert extras.install("postgres") is True
    assert extras.install_chromium() is True
    for kwargs in runs.kwargs:
        env = kwargs["env"]
        assert env["HTTPS_PROXY"] == env["https_proxy"] == proxy
        assert env["HTTP_PROXY"] == env["http_proxy"] == proxy
    # in the environment, not on a command line other users can read
    assert not any(proxy in arg for cmd in runs.calls for arg in cmd)


def test_without_ofsc_proxy_the_environment_is_left_alone(runs, monkeypatch):
    monkeypatch.delenv("OFSC_PROXY", raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://already.example:1")
    assert extras.install("postgres") is True
    assert runs.kwargs[0]["env"]["HTTPS_PROXY"] == "http://already.example:1"


def test_without_pip_or_uv_nothing_runs(runs, monkeypatch, caplog):
    monkeypatch.setattr(extras, "pip_command", lambda reqs: None)
    with caplog.at_level("WARNING", logger="shared"):
        assert extras.install("live") is False
    assert runs.calls == []
    assert "neither pip nor uv" in caplog.text


def test_the_standalone_download_installs_nothing(runs, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert extras.install("live") is False
    assert runs.calls == []


def test_turned_off_installs_nothing(runs, monkeypatch):
    monkeypatch.setenv("INSTALL_EXTRAS", "False")
    assert extras.install("live") is False
    assert extras.install_chromium() is False
    assert runs.calls == []


def test_a_failed_install_says_why_and_is_not_retried(runs, caplog):
    runs.result.update(code=1, stderr="line 1\nERROR: no matching distribution")
    with caplog.at_level("WARNING", logger="shared"):
        assert extras.install("live") is False
        assert extras.install("live") is False
    assert len(runs.calls) == 1  # --live-watch polls again; it shouldn't reinstall each time
    assert "no matching distribution" in caplog.text


def test_a_install_that_cannot_start_is_a_failure(runs, monkeypatch):
    def broken(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(extras.subprocess, "run", broken)
    assert extras.install("live") is False


def test_chromium_is_downloaded_with_this_pythons_playwright(runs):
    assert extras.install_chromium() is True
    assert extras.install_chromium() is True
    assert runs.calls == [[sys.executable, "-P", "-m", "playwright", "install", "chromium"]]


@pytest.mark.parametrize("value, on", [(" True ", True), ("1\n", True), (" false", False), ("0", False)])
def test_ofsc_install_extras_ignores_surrounding_spaces(monkeypatch, value, on):
    from ofscraper.utils.of_env.values import system

    monkeypatch.setenv("OFSC_INSTALL_EXTRAS", value)
    assert system.load_system_config()["INSTALL_EXTRAS"] is on


def test_installs_at_the_same_time_run_pip_once(runs, monkeypatch):
    # the postgres driver can be asked for from several threads at once
    import threading
    import time

    started = []

    def slow(cmd, **kwargs):
        started.append(cmd)
        time.sleep(0.3)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(extras.subprocess, "run", slow)
    results = []
    threads = [threading.Thread(target=lambda: results.append(extras.install("postgres"))) for _ in range(4)]
    threads += [threading.Thread(target=lambda: results.append(extras.install_chromium())) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [True] * 8
    assert len(started) == 2  # one pip install, one Chromium download


def test_a_user_install_can_be_imported_straight_away(runs, monkeypatch, tmp_path):
    # pip installs with --user when site-packages isn't writable; on a first
    # install the user site directory didn't exist at startup, so it isn't on
    # sys.path yet
    user_site = tmp_path / "user-site"
    monkeypatch.setattr(site, "ENABLE_USER_SITE", True)
    monkeypatch.setattr(site, "getusersitepackages", lambda: str(user_site))
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "ofs_user_site_extra", raising=False)

    def user_install(cmd, **kwargs):
        user_site.mkdir()
        (user_site / "ofs_user_site_extra.py").write_text("FOUND = True\n")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(extras.subprocess, "run", user_install)
    assert extras.install("postgres") is True
    import ofs_user_site_extra

    assert ofs_user_site_extra.FOUND
    monkeypatch.delitem(sys.modules, "ofs_user_site_extra")


def test_a_disabled_user_site_is_not_added(runs, monkeypatch, tmp_path):
    user_site = tmp_path / "user-site"
    user_site.mkdir()
    monkeypatch.setattr(site, "ENABLE_USER_SITE", False)
    monkeypatch.setattr(site, "getusersitepackages", lambda: str(user_site))
    monkeypatch.setattr(sys, "path", list(sys.path))
    assert extras.install("postgres") is True
    assert str(user_site) not in sys.path
