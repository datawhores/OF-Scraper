import sys

from rich.console import Console
from rich.theme import Theme

from ofscraper.utils.args.accessors.output import low_output


def replace_unencodable_output(streams=None):
    """
    Model names and post text can contain emoji. On a stdout/stderr that is not
    UTF-8 (e.g. cp1252 on Windows when output is redirected, or in the bundled
    exe), printing them raised UnicodeEncodeError and aborted the run. Print a
    replacement character instead.
    """
    for stream in streams or (sys.stdout, sys.stderr):
        encoding = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if encoding in {"utf8", "utf16", "utf32"}:
            continue
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass  # not a TextIOWrapper (e.g. replaced by a test runner)


replace_unencodable_output()

theme = Theme(
    {
        "logging.level.error": "green",
        "logging.level.warning": "green",
        "logging.level.debug": "yellow",
        "logging.level.info": "white",
        "logging.level.traceback": "red",
    }
)

class SharedConsole(Console):
    """
    The shared console is quiet when the output options ask for low output.
    Those options come from the command line, which must not be parsed when
    the package is imported (a program importing ofscraper has its own
    arguments), so they're read when the console is used, not when it's made.
    Assigning ``quiet`` overrides the options from then on.
    """

    _quiet_override = None

    @property
    def quiet(self):
        if self._quiet_override is not None:
            return self._quiet_override
        return low_output() is True

    @quiet.setter
    def quiet(self, value):
        self._quiet_override = value


shared_console = None

other_console = None


def get_console():
    if not low_output():
        return get_shared_console()
    return get_other_console()


def get_shared_console():
    global shared_console
    if not shared_console:
        shared_console = SharedConsole(theme=theme, quiet=None, markup=True)

    return shared_console


def get_other_console():
    global other_console
    if not other_console:
        other_console = Console(theme=theme, markup=True)
    return other_console


def update_shared(console_):
    global shared_console
    shared_console = console_
