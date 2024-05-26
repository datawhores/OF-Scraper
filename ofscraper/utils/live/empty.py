import contextlib

from ofscraper.utils.live.live import get_live
import ofscraper.utils.console as console



@contextlib.contextmanager
def prompt_live():
    old_render = get_live().renderable
    get_live().stop()
    console.get_shared_console().clear()
    console.get_shared_console().clear_live()
    yield
    live = get_live(recreate=True)
    live.start()
    live.update(old_render)
