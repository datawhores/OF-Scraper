import contextlib
import time

from ofscraper.utils.live.live import get_live, stop_live
from ofscraper.utils.live.clear import clear


@contextlib.contextmanager
def prompt_live():
    old_render = get_live().renderable
    stop_live()
    clear()
    # give time for screen to clear
    time.sleep(0.3)
    try:
        yield
    finally:
        # stop again for nested calls
        stop_live()
        live = get_live(recreate=True)
        live.start()
        live.update(old_render)
