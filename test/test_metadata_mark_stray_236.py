"""metadata -ms means --mark-stray-locked, not --mass-skip (#236)."""

from ofscraper.utils.args.parse.commands.main import program
from ofscraper.utils.args.parse.commands.metadata import metadata


def _parse(command, args):
    params, _ = command.main(args=args, standalone_mode=False, prog_name="OF-Scraper")
    return params


def test_metadata_short_ms_marks_stray():
    params = _parse(metadata, ["-ms", "--metadata", "check"])
    assert params["mark_stray"] is True
    assert params["mass_msg"] is None


def test_metadata_mass_skip_long_name_still_works():
    params = _parse(metadata, ["--mass-skip", "--metadata", "check"])
    assert params["mass_msg"] is False
    assert not params["mark_stray"]


def test_main_program_short_ms_still_skips_mass():
    assert _parse(program, ["-ms"])["mass_msg"] is False
