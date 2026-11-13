"""
Cached async properties: ``await obj.prop`` runs the getter once per instance.

Replaces the async-property package, whose last release reads
asyncio.iscoroutinefunction at decoration time; that is removed in Python 3.16.
"""

import asyncio
import functools
import inspect

_STATE_ATTR = "__async_cached_property__"


class _Awaitable:
    """Starts the load only when awaited, so a bare access leaves no coroutine behind."""

    __slots__ = ("_load",)

    def __init__(self, load):
        self._load = load

    def __await__(self):
        return self._load().__await__()


class async_cached_property:
    def __init__(self, fget):
        if not inspect.iscoroutinefunction(fget):
            raise TypeError("async_cached_property needs an async def getter")
        self.fget = fget
        self.name = fget.__name__
        functools.update_wrapper(self, fget)

    def __set_name__(self, owner, name):
        self.name = name

    def _state(self, instance):
        try:
            return object.__getattribute__(instance, _STATE_ATTR)
        except AttributeError:
            state = ({}, {})  # cache, locks
            object.__setattr__(instance, _STATE_ATTR, state)
            return state

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        cache, locks = self._state(instance)

        async def load():
            if self.name in cache:
                return cache[self.name]
            # concurrent first awaits share one call
            async with locks.setdefault(self.name, asyncio.Lock()):
                if self.name not in cache:
                    cache[self.name] = await self.fget(instance)
                return cache[self.name]

        return _Awaitable(load)

    def __set__(self, instance, value):
        self._state(instance)[0][self.name] = value

    def __delete__(self, instance):
        self._state(instance)[0].pop(self.name, None)
