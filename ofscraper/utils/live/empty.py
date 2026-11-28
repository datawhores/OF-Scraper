import contextlib
import time

from ofscraper.utils.live.clear import clear
from ofscraper.utils.live.live import get_live, start_live, stop_live


@contextlib.contextmanager
def prompt_live():
    # not .renderable, which wraps the content in a new Group each time
    old_render = get_live().get_renderable()
    stop_live()
    clear()
    # give time for screen to clear
    time.sleep(0.3)
    try:
        yield
    finally:
        # stop again for nested calls
        stop_live()
        start_live(old_render, refresh=True)
