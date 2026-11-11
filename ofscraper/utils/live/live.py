from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress
from rich.text import Text

import ofscraper.utils.console as console_

live = Live(
    transient=False,
    refresh_per_second=1,
    console=console_.get_shared_console(),
    auto_refresh=True,
)


def get_live(recreate=False):
    global live
    if not live or recreate:
        live = Live(
            transient=False,
            refresh_per_second=1,
            console=console_.get_shared_console(),
            auto_refresh=True,
        )
    return live


def set_live(new_live):
    global live
    live = new_live


def shows_something(renderable):
    """Whether the live display would draw more than empty panels.

    A panel whose progress tasks are all hidden (what clear_tasks_by_name
    leaves) draws only its border and title. Anything not handled here
    counts as showing something.
    """
    if renderable is None:
        return False
    if isinstance(renderable, str):
        return bool(renderable.strip())
    if isinstance(renderable, Text):
        return bool(renderable.plain.strip())
    if isinstance(renderable, Progress):
        return any(task.visible for task in renderable.tasks)
    if isinstance(renderable, Group):
        return any(shows_something(item) for item in renderable.renderables)
    if isinstance(renderable, Panel):
        return shows_something(renderable.renderable)
    return True


def stop_live():
    """Stop the live display and drop it; get_live() makes a new one.

    The live display isn't transient, so rich leaves its last frame on the
    screen when it stops. That frame is kept when it shows progress, and
    erased when it is only empty panels.
    """
    global live
    if live:
        transient = live.transient
        if live.is_started and not shows_something(live.renderable):
            live.transient = True
        try:
            live.stop()
        finally:
            live.transient = transient
        live = None


def start_live(renderable=None, refresh=True):
    """Start the live display if none is running.

    stop_live() drops the live display, so this makes a new one then.
    renderable, if given, is what it shows.
    """
    global live
    if live and live.is_started:
        return
    live = get_live()
    if renderable is not None:
        live.update(renderable)
    live.start(refresh=refresh)
