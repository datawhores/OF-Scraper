import sys


class NoConsoleError(Exception):
    """A prompt was needed, but there's no interactive console to show it on."""


def is_interactive():
    """
    Whether someone can answer a prompt: stdin is a terminal, and on Windows
    stdout is too.

    Not when the run is scheduled or another program started it. On Windows,
    prompt_toolkit also needs a console on stdout (it raised
    NoConsoleScreenBufferError when output was redirected). On Linux and macOS
    it falls back to plain text, so `| tee` and `> file` still work.
    """
    streams = (sys.stdin, sys.stdout) if sys.platform == "win32" else (sys.stdin,)
    for stream in streams:
        try:
            if stream is None or not stream.isatty():
                return False
        except (AttributeError, ValueError):  # no isatty, or a closed stream
            return False
    return True


def require_console(question):
    """Raise NoConsoleError, naming the question, when no one can answer it."""
    if not is_interactive():
        raise NoConsoleError(
            f"The run needs an answer to {question!r}, but there's no interactive "
            "console to ask it on. Run it in a terminal, or pass the options that "
            "answer it on the command line."
        )
