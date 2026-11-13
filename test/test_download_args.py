import click
import pytest
from click.testing import CliRunner

from ofscraper.utils.args.helpers.hide_args import hide_check_mode
from ofscraper.utils.args.parse.arguments.download import download_sem_option


@pytest.fixture
def command():
    @click.command()
    @download_sem_option
    def cmd(download_sem):
        click.echo(download_sem)

    return cmd


def test_download_sem_option_names(command):
    opts = command.params[0].opts
    assert {"--download-sems", "--download-sem", "--sem", "-sd"} <= set(opts)
    assert not any("--download-sems--" in o for o in opts)


@pytest.mark.parametrize("flag", ["--download-sems", "--download-sem", "--sems", "-sd"])
def test_download_sem_flags_parse(command, flag):
    result = CliRunner().invoke(command, [flag, "4"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "4"


def test_check_mode_hides_download_sem(command):
    hide_check_mode(command)
    assert command.params[0].name == "download_sem"
    assert command.params[0].hidden is True
