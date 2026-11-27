"""Tests for ``--live-jitter`` and ``LIVE_JITTER`` / ``OFSC_LIVE_JITTER``."""

from types import SimpleNamespace

import click
import pytest

import ofscraper.__main__  # noqa: F401  (import order: avoids a circular import)
import ofscraper.sites.fansly.live as fansly_live
import ofscraper.utils.args.parse.commands.main as main_cmd
import ofscraper.utils.of_env as of_env_pkg
import ofscraper.utils.of_env.of_env as of_env


@pytest.fixture
def reset_of_env(monkeypatch):
    """Clear LIVE_JITTER / OFSC_LIVE_JITTER and reload cached env config after each test."""
    monkeypatch.delenv("LIVE_JITTER", raising=False)
    monkeypatch.delenv("OFSC_LIVE_JITTER", raising=False)
    of_env_pkg.get_all_configs(forced=True)
    yield
    monkeypatch.delenv("LIVE_JITTER", raising=False)
    monkeypatch.delenv("OFSC_LIVE_JITTER", raising=False)
    of_env_pkg.get_all_configs(forced=True)


def test_cli_parses_live_jitter_and_rejects_negative():
    ctx_default = main_cmd.program.make_context("ofscraper", ["--live-watch"])
    assert ctx_default.params["live_jitter"] is None

    ctx_zero = main_cmd.program.make_context("ofscraper", ["--live-watch", "--live-jitter", "0"])
    assert ctx_zero.params["live_jitter"] == 0.0

    ctx_frac = main_cmd.program.make_context("ofscraper", ["--live-watch", "--live-jitter", "2.5"])
    assert ctx_frac.params["live_jitter"] == 2.5

    with pytest.raises(click.BadParameter):
        main_cmd.program.make_context("ofscraper", ["--live-watch", "--live-jitter", "-1"])


def test_live_jitter_zero_overrides_default_and_env(monkeypatch, reset_of_env):
    monkeypatch.setenv("LIVE_JITTER", "7.5")
    s = SimpleNamespace(live_jitter=0.0)
    assert fansly_live.options(s)["jitter"] == 0.0


def test_live_jitter_cli_float_and_non_finite_fallback(monkeypatch, reset_of_env):
    assert fansly_live.options(SimpleNamespace(live_jitter=2.5))["jitter"] == 2.5
    assert fansly_live.options(SimpleNamespace(live_jitter=float("nan")))["jitter"] == 10.0
    assert fansly_live.options(SimpleNamespace(live_jitter=float("inf")))["jitter"] == 10.0
    assert fansly_live.options(SimpleNamespace(live_jitter=float("-inf")))["jitter"] == 10.0
    assert fansly_live.options(SimpleNamespace(live_jitter="not-a-number"))["jitter"] == 10.0


def test_live_jitter_env_fractional_values(monkeypatch, reset_of_env):
    monkeypatch.setenv("LIVE_JITTER", "2.5")
    assert fansly_live.options(SimpleNamespace(live_jitter=None))["jitter"] == 2.5


def test_ofsc_live_jitter_env_fractional_values(monkeypatch, reset_of_env):
    monkeypatch.setenv("OFSC_LIVE_JITTER", "2.5")
    of_env_pkg.get_all_configs(forced=True)
    assert fansly_live.options(SimpleNamespace(live_jitter=None))["jitter"] == 2.5


@pytest.mark.parametrize("raw", ["abc", "nan", "inf", "-inf"])
def test_invalid_live_jitter_env_falls_back_to_default(monkeypatch, reset_of_env, raw):
    monkeypatch.setenv("LIVE_JITTER", raw)
    assert fansly_live.options(SimpleNamespace(live_jitter=None))["jitter"] == 10.0


@pytest.mark.parametrize("raw", ["abc", "nan", "inf", "-inf"])
def test_invalid_ofsc_live_jitter_env_falls_back_to_default(monkeypatch, reset_of_env, raw):
    monkeypatch.setenv("OFSC_LIVE_JITTER", raw)
    of_env_pkg.get_all_configs(forced=True)
    assert of_env.getattr("LIVE_JITTER") == 10.0
    assert fansly_live.options(SimpleNamespace(live_jitter=None))["jitter"] == 10.0
