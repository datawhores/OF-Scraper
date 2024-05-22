import contextlib
from rich.live import Live
import ofscraper.utils.live.progress as progress

@contextlib.contextmanager
def prompt_live():
    old_render=progress.live.renderable
    progress.live.stop()
    yield
    progress.live=Live(old_render)
    progress.live.start(refresh=True)

