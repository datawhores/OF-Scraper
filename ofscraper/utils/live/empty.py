import contextlib

from ofscraper.utils.live.live import get_live


@contextlib.contextmanager
def prompt_live():
    old_render = get_live().renderable
    get_live().stop()
    yield
    live = get_live(recreate=True)
    live.start()
    live.update(old_render)
