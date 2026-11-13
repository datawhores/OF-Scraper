from textual.widgets import RichLog

import ofscraper.utils.logs.logger as logger


class OutConsole(RichLog):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def on_unmount(self) -> None:
        # the table app is closing: stop the log from writing here
        logger.remove_widget(self)
