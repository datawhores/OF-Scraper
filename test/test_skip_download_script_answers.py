"""How skip_download_script reads the script's answer (#351).

`false` (any case) or nothing skips the file in this run; `skip-permanent`
(any case, spaces around it ignored) skips it for good; any other output, or
a script that fails, lets the download proceed. The script's run is replaced,
so each test hands back the stdout it would print.
"""

import asyncio
import subprocess
from types import SimpleNamespace

import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.scripts.skip_download_script as script_mod
import ofscraper.utils.settings as settings
from ofscraper.scripts.skip_download_script import SKIP_PERMANENT, skip_download_script


@pytest.fixture
def ask(monkeypatch, tmp_path):
    script = tmp_path / "script"
    script.write_text("")
    monkeypatch.setattr(
        settings,
        "get_settings",
        lambda *a, **k: SimpleNamespace(skip_download_script=str(script)),
    )
    ele = SimpleNamespace(
        media={}, post=SimpleNamespace(post={}), username="a-creator",
        model_id=1, post_id=2, id=3,
    )

    def run(stdout=None, error=None):
        async def fake_run(*a, **k):
            if error:
                raise error
            return SimpleNamespace(stdout=stdout, stderr="")

        monkeypatch.setattr(script_mod, "async_run", fake_run)
        return asyncio.run(skip_download_script(1000, ele))

    return run


@pytest.mark.parametrize(
    "stdout, answer",
    [
        ("false", True),
        ("False\n", True),
        ("", True),
        ("  \n", True),
        ("skip-permanent", SKIP_PERMANENT),
        ("  SKIP-Permanent \n", SKIP_PERMANENT),
        ("true", False),
        ("download", False),
        ("skip-permanently", False),
        ("skip permanent", False),
    ],
)
def test_answers(ask, stdout, answer):
    assert ask(stdout) == answer


def test_failed_script_downloads(ask):
    assert ask(error=subprocess.CalledProcessError(1, "script")) is False
