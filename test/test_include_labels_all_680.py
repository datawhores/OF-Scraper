"""OFSC_INCLUDE_LABELS_ALL adds labels to `all` (#680)."""

from types import SimpleNamespace

import pytest

import ofscraper.main.open.load  # noqa: F401  (import order, see AGENTS.md)
import ofscraper.utils.args.accessors.areas as areas
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.utils.of_env.values.main import load_main_config


def _use(monkeypatch, include_labels, **picked):
    real = of_env.getattr

    def fake(key, default=None):
        if key == "INCLUDE_LABELS_ALL":
            return include_labels
        return real(key, default)

    monkeypatch.setattr(of_env, "getattr", fake)
    args = {"posts": [], "like_area": [], "download_area": []}
    args.update(picked)
    monkeypatch.setattr(settings, "get_settings", lambda: SimpleNamespace(**args))


@pytest.mark.parametrize(
    "getter,field",
    [
        (areas.get_download_area, "posts"),
        (areas.get_download_area, "download_area"),
        (areas.get_like_area, "posts"),
        (areas.get_like_area, "like_area"),
    ],
)
def test_all_includes_labels_when_on(monkeypatch, getter, field):
    _use(monkeypatch, True, **{field: ["All"]})
    assert "Labels" in getter()


@pytest.mark.parametrize("getter", [areas.get_download_area, areas.get_like_area])
def test_all_skips_labels_when_off(monkeypatch, getter):
    _use(monkeypatch, False, posts=["All"])
    result = getter()
    assert "Labels" not in result
    assert "Timeline" in result


@pytest.mark.parametrize("value", [None, "False", "false", "0", ""])
def test_default_is_off(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("OFSC_INCLUDE_LABELS_ALL", raising=False)
    else:
        monkeypatch.setenv("OFSC_INCLUDE_LABELS_ALL", value)
    assert load_main_config()["INCLUDE_LABELS_ALL"] is False


@pytest.mark.parametrize("value", ["True", "true", "1"])
def test_env_turns_it_on(monkeypatch, value):
    monkeypatch.setenv("OFSC_INCLUDE_LABELS_ALL", value)
    assert load_main_config()["INCLUDE_LABELS_ALL"] is True
