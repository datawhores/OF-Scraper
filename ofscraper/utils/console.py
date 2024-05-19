from rich.console import Console
from rich.theme import Theme
from ofscraper.utils.args.output import low_output

theme= Theme(
        {
            "logging.level.error": "green",
            "logging.level.warning": "green",
            "logging.level.debug": "yellow",
            "logging.level.info": "white",
            "logging.level.traceback": "red",
        }
    )

quiet =low_output()==True
shared_console = Console(
   theme=theme,
   quiet=quiet
)

other_console = Console(
   theme=theme
)

def get_console():
    if not low_output():
        return get_shared_console()
    return get_other_console()

def get_shared_console():
    global shared_console
    return shared_console


def get_other_console():
    global other_console
    return other_console

    


def update_shared(console_):
    global shared_console
    shared_console = console_
