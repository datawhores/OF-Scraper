"""--dynamic-rules accepts the same rule names as config.json (#232)."""

import click
import pytest

import ofscraper.utils.config.data as data
from ofscraper.utils.args.parse.commands.main import program
from ofscraper.utils.const import DYNAMIC_ALIASES, DYNAMIC_OPTIONS


def _parse(args):
    params, _ = program.main(args=args, standalone_mode=False, prog_name="OF-Scraper")
    return params


@pytest.mark.parametrize("name", ["digital", "dc", "digitals", "digitalcriminal", "DC"])
def test_short_names_are_accepted(name):
    assert _parse(["--dynamic-rules", name])["dynamic_rules"] == name.lower()


@pytest.mark.parametrize("name", DYNAMIC_OPTIONS)
def test_full_names_are_still_accepted(name):
    assert _parse(["-dr", name])["dynamic_rules"] == name


def test_command_line_and_config_accept_the_same_names():
    for name in [*DYNAMIC_OPTIONS, *DYNAMIC_ALIASES]:
        cfg = {"advanced_options": {"dynamic-mode-default": name}}
        assert data.get_dynamic(config=cfg) == name
        assert _parse(["-dr", name])["dynamic_rules"] == name


@pytest.mark.parametrize("name", ["dv", "dev", "nope"])
def test_unknown_names_are_rejected(name):
    with pytest.raises(click.BadParameter):
        _parse(["-dr", name])
