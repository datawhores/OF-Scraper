from rich.live import Live

import ofscraper.utils.console as console_

live=live=Live( transient=False,refresh_per_second=4,console=console_.get_shared_console())
def get_live():
    global live
    if not live:
        live=Live( transient=False,refresh_per_second=4,console=console_.get_shared_console())
    return live