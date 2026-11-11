import logging


class TextHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self._widget = None

    def emit(self, record):
        widget = self._widget
        # only while the widget is in a running app: once the app has exited,
        # writing to it raises (a log call must never raise)
        if widget is None or not widget.is_attached:
            return
        try:
            widget.write(self.format(record))
        except Exception:
            self.handleError(record)

    @property
    def widget(self):
        return self._widget

    @widget.setter
    def widget(self, widget):
        self._widget = widget
