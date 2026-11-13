import sys

import pytest

import ofscraper.utils.args.main as args_main


@pytest.mark.parametrize(
    "argv, message",
    [
        (["--action", "download", "--bogus-flag"], "No such option"),
        (["--action", "download", "--after", "13/01/2021"], "isn't a date"),
    ],
)
def test_usage_error_prints_a_message_and_exits_2(monkeypatch, capsys, argv, message):
    # a mistake on the command line gets click's usage message, not a traceback
    monkeypatch.setattr(sys, "argv", ["OF-Scraper", *argv])
    # parse_args registers the subcommands each call, and cloup refuses a second
    # registration; the options tested here are on the main program
    monkeypatch.setattr(args_main.main.program, "add_command", lambda *a, **k: None)
    with pytest.raises(SystemExit) as exit_info:
        args_main.parse_args()
    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "Usage:" in err
    assert message in err
