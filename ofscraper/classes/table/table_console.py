from textual.widgets import RichLog


class OutConsole(RichLog):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
