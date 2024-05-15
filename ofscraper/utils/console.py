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


def get_shared_console(quiet=None):
    import ofscraper.utils.args.read as read_args
    quiet= read_args.retriveArgs().output in { "OFF", "LOW", "PROMPT"} if quiet==None else quiet
    shared_console.quiet=quiet
    return shared_console

def get_temp_console(quiet=None):
    import ofscraper.utils.args.read as read_args
    quiet= read_args.retriveArgs().output in { "OFF", "LOW", "PROMPT"} if quiet==None else quiet
    return Console(
    theme=Theme(
        {
            "logging.level.error": "green",
            "logging.level.warning": "green",
            "logging.level.debug": "yellow",
            "logging.level.info": "white",
            "logging.level.traceback": "red",
        }
    ),quiet=quiet
)

def update_shared(console_):
    global shared_console
    shared_console = console_
