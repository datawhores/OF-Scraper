from rich.live import Live

import ofscraper.utils.console as console_

live = live = Live(
    transient=False, refresh_per_second=4, console=console_.get_shared_console()
)


def get_live(recreate=False):
    global live
    if not live or recreate:
        live = Live(
            transient=False, refresh_per_second=4, console=console_.get_shared_console()
        )
    return live


def set_live(new_live):
    global live
    live = new_live
def stop_live():
    global live
    if live:
        live.stop()
        live = None
