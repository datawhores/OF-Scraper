import logging


class TextHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._widget = None

    def emit(self, record):
        # only emit after widget is set
        if self._widget is None:
            return
        log_entry = self.format(record)
        log_entry = f"{log_entry}"
        self._widget.write(log_entry)

    @property
    def widget(self):
        return self._widget

    @widget.setter
    def widget(self, widget):
        self._widget = widget
