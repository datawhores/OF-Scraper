"""Download and livestream events that other code (a TUI, a GUI, a plugin) can subscribe to.

- ``item_downloaded(ele, path)``: a media file is saved at ``path`` (a
  ``pathlib.Path``) and recorded in the database, before the
  after_download_script runs. All three downloaders send it: normal files,
  DRM videos and Fansly HLS/DASH streams. A stop during the script still
  counts the item as downloaded. The Fansly check of videos saved without
  sound, after a run's downloads, sends it for a video it saves again, with
  no item_finished.
- ``item_finished(ele, username, result, reason)``: the download loop has
  counted one item. ``result`` is "downloaded", "failed", "skipped" or
  "stopped". ``reason`` says why an item failed or was skipped (see
  ``download.run``); it is None for the other results. An item a stop ended
  before it started gets no event.
- ``live_watcher``, ``live_poll``, ``live_stream``, ``live_chat``: lifecycle,
  polling, per-creator recording state, and Fansly chat events emitted by the
  livestream watcher and recorders via ``emit_sync``.

Subscribers get the event's values as keyword arguments, in the order they
subscribed. They run in the download's own thread and event loop: a plain
function is called, and an ``async def`` one is awaited. Either one holds up
that download while it runs, so a GUI should hand the event to its own
thread and return. An exception in a subscriber is logged at debug level and
never fails the download. ``emit_sync`` dispatches synchronously to plain
function subscribers without awaiting (async subscribers are skipped with a
debug log). With no subscribers, sending an event costs one dict lookup.
"""

import inspect
import logging
import threading

EVENTS = (
    "item_downloaded",
    "item_finished",
    "live_watcher",
    "live_poll",
    "live_stream",
    "live_chat",
)

_subscribers = {}
_lock = threading.Lock()


def subscribe(name, fn):
    """Call fn on every ``name`` event. Subscribing it again does nothing."""
    if name not in EVENTS:
        raise ValueError(f"unknown event {name!r}: one of {', '.join(EVENTS)}")
    with _lock:
        current = _subscribers.get(name, ())
        if fn not in current:
            _subscribers[name] = current + (fn,)


def unsubscribe(name, fn):
    """Stop calling fn on ``name`` events. Not subscribed: nothing happens."""
    with _lock:
        current = _subscribers.get(name, ())
        if fn in current:
            # ==, not is: a bound method is a new object on every access
            _subscribers[name] = tuple(f for f in current if f != fn)


async def emit(name, **kwargs):
    # a tuple, replaced on (un)subscribe: another thread may change the list
    for fn in _subscribers.get(name, ()):
        try:
            result = fn(**kwargs)
            if inspect.isawaitable(result):
                await result
        except Exception as E:
            logging.getLogger("shared").debug(
                f"{name} subscriber {getattr(fn, '__qualname__', fn)} failed: {E}",
                exc_info=True,
            )


def emit_sync(name, **kwargs):
    """Send an event without awaiting; subscribers must be plain functions."""
    for fn in _subscribers.get(name, ()):
        try:
            result = fn(**kwargs)
            if inspect.isawaitable(result):
                if hasattr(result, "close"):
                    result.close()
                logging.getLogger("shared").debug(
                    f"{name} async subscriber {getattr(fn, '__qualname__', fn)} skipped in emit_sync"
                )
        except Exception as E:
            logging.getLogger("shared").debug(
                f"{name} subscriber {getattr(fn, '__qualname__', fn)} failed: {E}",
                exc_info=True,
            )
