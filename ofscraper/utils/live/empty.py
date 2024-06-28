import contextlib
import time

import ofscraper.utils.console as console
from ofscraper.utils.live.live import get_live, stop_live


@contextlib.contextmanager
def prompt_live():
    old_render = get_live().renderable
    stop_live()
    console.get_shared_console().clear_live()
    console.get_shared_console().line(2)
    # give time for screen to clear
    time.sleep(0.3)
    yield
    # stop again for nested calls
    stop_live()
    live = get_live(recreate=True)
    live.start()
    live.update(old_render)
