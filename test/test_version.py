import importlib.metadata
import importlib.util
import pathlib

import pytest

VERSION_FILE = pathlib.Path(__file__).parent.parent / "ofscraper" / "__version__.py"


def _load(monkeypatch, versions):
    asked = []

    def fake_version(name):
        asked.append(name)
        if name in versions:
            return versions[name]
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", fake_version)
    # a fresh copy, so the module everything else imported is left alone
    spec = importlib.util.spec_from_file_location("_version_under_test", VERSION_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.__version__, asked


def test_version_comes_from_the_ofscraper_community_distribution(monkeypatch):
    version, asked = _load(
        monkeypatch, {"ofscraper-community": "3.16.2", "ofscraper": "3.14.7"}
    )
    assert version == "3.16.2"
    assert asked == ["ofscraper-community"]


@pytest.mark.parametrize("installed", [{}, {"ofscraper": "3.14.7"}])
def test_version_falls_back_when_not_installed(monkeypatch, installed):
    # upstream's 'ofscraper' metadata is never mistaken for the fork's version
    version, _ = _load(monkeypatch, installed)
    assert version == "0.0.0"
