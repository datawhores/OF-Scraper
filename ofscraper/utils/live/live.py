from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress
from rich.text import Text

import ofscraper.utils.console as console_


class ResizeAwareLive(Live):
    """Discard the previous frame's cursor position when the terminal resizes."""

    _last_size = None

    def refresh(self):
        with self._lock:
            size = self.console.size
            if (
                self.console.is_interactive
                and self._last_size is not None
                and size != self._last_size
            ):
                self.console.clear()
                # Reflow makes Rich's saved height invalid. Draw at home rather
                # than moving up by that height after clearing the screen.
                self._live_render._shape = None
            self._last_size = size
            super().refresh()


live = ResizeAwareLive(
    transient=False,
    refresh_per_second=1,
    console=console_.get_shared_console(),
    auto_refresh=True,
)


def get_live(recreate=False):
    global live
    if not live or recreate:
        live = ResizeAwareLive(
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
    # walked with a stack, not recursion, so a deep tree can't raise
    # RecursionError; seen guards against a renderable that contains itself
    stack = [renderable]
    seen = set()
    while stack:
        node = stack.pop()
        if node is None:
            continue
        if isinstance(node, str):
            if node.strip():
                return True
        elif isinstance(node, Text):
            if node.plain.strip():
                return True
        elif isinstance(node, Progress):
            if any(task.visible for task in node.tasks):
                return True
        elif isinstance(node, (Group, Panel)):
            if id(node) in seen:
                continue
            seen.add(id(node))
            if isinstance(node, Group):
                stack.extend(node.renderables)
            else:
                stack.append(node.renderable)
        else:
            return True
    return False


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
