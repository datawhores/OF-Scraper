import signal
import threading

_HELD_SIGNALS = (signal.SIGINT, signal.SIGTERM)


class DelayedKeyboardInterrupt:
    """Hold Ctrl+C (SIGINT) and SIGTERM while a block runs; deliver them after.

    A signal received in the block is raised again when it ends, through the
    handlers that were in place before (so SIGTERM with no handler of
    ofscraper's still terminates). Blocks can nest.

    Use it for a short synchronous block, and don't await inside one: blocks
    in concurrent tasks could end out of order and restore the wrong handler.
    Outside the main thread it does nothing: Python runs signal handlers, and
    so raises KeyboardInterrupt, only in the main thread.
    """

    def __enter__(self):
        self._held = []
        self._saved = {}
        if threading.current_thread() is threading.main_thread():
            self._saved = {
                sig: signal.signal(sig, self._hold) for sig in _HELD_SIGNALS
            }
        return self

    def __exit__(self, *exc):
        for sig, handler in self._saved.items():
            # None: the handler was set outside Python; use the default.
            signal.signal(sig, signal.SIG_DFL if handler is None else handler)
        for sig in dict.fromkeys(self._held):
            signal.raise_signal(sig)
        return False

    def _hold(self, signum, frame):
        self._held.append(signum)


def _raise_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt


def sigterm_as_keyboard_interrupt():
    """
    Make SIGTERM take the same shutdown path as Ctrl+C.

    Python installs no SIGTERM handler, and the kernel ignores default-handled
    signals sent to PID 1, so in a container (where ofscraper is PID 1 via the
    entrypoint's exec) `docker stop` was ignored until SIGKILL.
    """
    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)


def exit_wrapper(func):
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            with DelayedKeyboardInterrupt():
                raise KeyboardInterrupt
        except Exception as E:
            try:
                with DelayedKeyboardInterrupt():
                    raise E
            except KeyboardInterrupt:
                raise KeyboardInterrupt

    return inner
