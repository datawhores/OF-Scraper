# =============================================================================
# DelayedKeyboardInterrupt implementation.
# This code can be moved into separate python package.
# =============================================================================

import os
import signal

__all__ = [
    "SIGNAL_TRANSLATION_MAP",
]

SIGNAL_TRANSLATION_MAP = {
    signal.SIGINT: "SIGINT",
    signal.SIGTERM: "SIGTERM",
}


class DelayedKeyboardInterrupt:
    def __init__(self, propagate_to_forked_processes=None):
        """
        Constructs a context manager that suppresses SIGINT & SIGTERM signal handlers
        for a block of code.

        The signal handlers are called on exit from the block.

        Inspired by: https://stackoverflow.com/a/21919644

        :param propagate_to_forked_processes: This parameter controls behavior of this context manager
        in forked processes.
        If True, this context manager behaves the same way in forked processes as in parent process.
        If False, signals received in forked processes are handled by the original signal handler.
        If None, signals received in forked processes are ignored (default).
        """
        self._pid = os.getpid()
        self._propagate_to_forked_processes = propagate_to_forked_processes
        self._sig = None
        self._frame = None
        self._old_signal_handler_map = None

    def __enter__(self):
        self._old_signal_handler_map = {
            sig: signal.signal(sig, self._handler)
            for sig, _ in SIGNAL_TRANSLATION_MAP.items()
        }

    def __exit__(self, exc_type, exc_val, exc_tb):
        for sig, handler in self._old_signal_handler_map.items():
            signal.signal(sig, handler)
        if self._sig is None:
            return
        self._old_signal_handler_map[self._sig](self._sig, self._frame)

    def _handler(self, sig, frame):
        self._sig = sig
        self._frame = frame

        #
        # Protection against fork.
        #
        if os.getpid() != self._pid:
            if self._propagate_to_forked_processes is False:
                print(
                    f"!!! DelayedKeyboardInterrupt._handler: {SIGNAL_TRANSLATION_MAP[sig]} received; "
                    f"PID mismatch: {os.getpid()=}, {self._pid=}, calling original handler"
                )
                self._old_signal_handler_map[self._sig](self._sig, self._frame)
            elif self._propagate_to_forked_processes is None:
                print(
                    f"!!! DelayedKeyboardInterrupt._handler: {SIGNAL_TRANSLATION_MAP[sig]} received; "
                    f"PID mismatch: {os.getpid()=}, ignoring the signal"
                )
                return
            # elif self._propagate_to_forked_processes is True:
            #   ... passthrough

        print(
            f"!!! DelayedKeyboardInterrupt._handler: {SIGNAL_TRANSLATION_MAP[sig]} received; delaying KeyboardInterrupt"
        )


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
