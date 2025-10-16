from rich.console import Console
from rich.theme import Theme

from ofscraper.utils.args.accessors.output import low_output

theme = Theme(
    {
        "logging.level.error": "green",
        "logging.level.warning": "green",
        "logging.level.debug": "yellow",
        "logging.level.info": "white",
        "logging.level.traceback": "red",
    }
)

quiet = low_output() is True
shared_console = None

other_console = None


def get_console():
    if not low_output():
        return get_shared_console()
    return get_other_console()


def get_shared_console():
    global shared_console
    if not shared_console:
        shared_console = Console(theme=theme, quiet=quiet, markup=True)

    return shared_console


def get_other_console():
    global other_console
    if not other_console:
        other_console = Console(theme=theme, markup=True)
    return other_console


def update_shared(console_):
    global shared_console
    shared_console = console_
