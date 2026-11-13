"""--block-ads is accepted, --env-files is loaded, --length-max/min take seconds (#201)."""

from types import SimpleNamespace

import click
import pytest

import ofscraper.utils.settings as settings
from ofscraper.utils.args.parse.commands.main import program


def _parse(args):
    params, _ = program.main(args=args, standalone_mode=False, prog_name="OF-Scraper")
    return params


def test_block_ads_is_accepted():
    assert _parse(["--block-ads"])["block_ads"] is True
    assert _parse([])["block_ads"] is False


def test_length_filters_take_plain_seconds():
    params = _parse(["--length-max", "90", "--length-min", "5"])
    # whole seconds as ints: the table view splits them into h/m/s inputs
    assert params["length_max"] == 90 and type(params["length_max"]) is int
    assert params["length_min"] == 5


@pytest.mark.parametrize("value", ["1m", "1.5", "nan", "inf", "-1"])
def test_length_filters_reject_anything_but_whole_seconds(value):
    with pytest.raises(click.BadParameter):
        _parse(["--length-max", value])


@pytest.fixture
def loaded(monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "load_env_files", lambda files: calls.append(files))
    monkeypatch.setattr(settings.of_env, "get_all_configs", lambda **k: None)
    monkeypatch.setattr(settings, "merged_settings", lambda: SimpleNamespace())
    monkeypatch.setattr(settings, "settings", None)
    return calls


def test_env_files_from_the_command_line_are_loaded(monkeypatch, loaded):
    monkeypatch.setattr(settings, "get_args", lambda *a, **k: SimpleNamespace(env_files=("cli.env",)))
    monkeypatch.setattr(settings.config_data, "get_env_files", lambda *a, **k: ["config.env"])
    settings.setup_settings()
    assert loaded == [["cli.env"]]


def test_config_env_files_are_loaded_without_the_option(monkeypatch, loaded):
    monkeypatch.setattr(settings, "get_args", lambda *a, **k: SimpleNamespace(env_files=()))
    monkeypatch.setattr(settings.config_data, "get_env_files", lambda *a, **k: "a.env, b.env")
    settings.setup_settings()
    assert loaded == [["a.env", "b.env"]]


def test_neg_filter_does_not_grow_on_each_settings_build(monkeypatch):
    from ofscraper.utils.args.main import AutoDotDict

    args = AutoDotDict(_parse(["--block-ads", "--neg-filter", "foo"]))
    args.command = "OF-Scraper"
    monkeypatch.setattr(settings.read_args, "retriveArgs", lambda *a, **k: args)
    first = settings.merged_settings().neg_filter
    second = settings.merged_settings().neg_filter
    assert args.neg_filter == ["foo"]
    assert first == second and len(second) == 2


def test_table_time_field_accepts_decimal_seconds():
    # config.json can hold a decimal length; the table view splits it into h/m/s
    from ofscraper.classes.table.fields.timefield import TimeField

    inputs = [SimpleNamespace(value=None) for _ in range(3)]
    field = object.__new__(TimeField)
    field.query_one = lambda *a: SimpleNamespace(query=lambda *a: inputs)
    field.update_table_max(5400.0)
    assert [i.value for i in inputs] == ["1", "30", "0"]
    field.update_table_min(90.7)
    assert [i.value for i in inputs] == ["0", "1", "30"]
