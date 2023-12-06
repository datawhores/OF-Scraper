from rich.console import Console
from rich.theme import Theme

shared_console = Console(
    theme=Theme(
        {
            "logging.level.error": "green",
            "logging.level.warning": "green",
            "logging.level.debug": "yellow",
            "logging.level.info": "white",
            "logging.level.traceback": "red",
        }
    )
)


def get_shared_console():
    return shared_console


def update_shared(console_):
    global shared_console
    shared_console = console_
