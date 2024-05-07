from textual.widgets import Button


class StyledButton(Button):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
