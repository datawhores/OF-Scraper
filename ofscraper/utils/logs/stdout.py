# logs stdout logs via a shared queue

from rich.logging import RichHandler

import ofscraper.utils.console as console
import ofscraper.utils.logs.classes.classes as log_class
from ofscraper.utils.logs.classes.handlers.text import TextHandler


import ofscraper.utils.logs.utils.level as log_helpers
import ofscraper.utils.settings as settings



def add_stdout_handler(log, clear=True, rich_array=None):
    if clear:
        log.handlers.clear()
    format = " \[%(module)s.%(funcName)s:%(lineno)d]  %(message)s"
    log.setLevel(1)
    log_helpers.addtraceback()
    log_helpers.addtrace()
    sh = RichHandler(
        markup=True,
        tracebacks_show_locals=True,
        show_time=False,
        show_level=False,
        console=console.get_console(),
    )
    sh.setLevel(log_helpers.getLevel(settings.get_settings().output_level))
    sh.setFormatter(log_class.SensitiveFormatter(format))
    sh.addFilter(log_class.NoTraceBack())
    tx = TextHandler()
    tx.setLevel(log_helpers.getLevel(settings.get_settings().output_level))
    tx.setFormatter(log_class.LogFileFormatter(format))
    log.addHandler(sh)
    log.addHandler(tx)

    if settings.get_settings().output_level in {"DEBUG"}:
        sh2 = RichHandler(
            rich_tracebacks=True,
            console=console.get_shared_console(),
            markup=True,
            tracebacks_show_locals=True,
            show_time=False,
        )
        sh2.setLevel(settings.get_settings().output_level)
        sh2.setFormatter(log_class.SensitiveFormatter(format))
        sh2.addFilter(log_class.TraceBackOnly())

        log.addHandler(sh2)

    return log

