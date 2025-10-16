from textual.containers import Container


class Sidebar(Container):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def toggle_hidden(self):
        self.toggle_class("-hidden")
        self.toggle_class("-show")
