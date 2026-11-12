"""Shared prompt cancellation and the menu boundaries that consume it."""

from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps


class PromptCancelled(BaseException):
    """Unwind a prompt flow without treating cancellation as an error."""


_can_cancel = ContextVar("prompt_can_cancel", default=False)


@contextmanager
def cancel_scope(restore_args=False, saved_args=None):
    """Discard this menu choice on Esc; leave Ctrl+C untouched."""
    if restore_args:
        import ofscraper.utils.settings as settings

        saved = settings.get_args(copy=True) if saved_args is None else saved_args
    token = _can_cancel.set(True)
    try:
        yield
    except PromptCancelled:
        if restore_args:
            settings.update_args(saved)
    finally:
        _can_cancel.reset(token)


def back_to_menu(function):
    @wraps(function)
    def inner(*args, **kwargs):
        with cancel_scope():
            return function(*args, **kwargs)

    return inner


def top_level(function):
    @wraps(function)
    def inner(*args, **kwargs):
        token = _can_cancel.set(False)
        try:
            return function(*args, **kwargs)
        finally:
            _can_cancel.reset(token)

    return inner


def cancel(event):
    if _can_cancel.get():
        # Exit with an exception so InquirerPy never validates or filters a
        # cancelled answer (filters may reject None or have side effects).
        event.app.exit(exception=PromptCancelled())
