import asyncio
import warnings

import pytest

from ofscraper.utils.async_cached_property import async_cached_property


class Thing:
    def __init__(self):
        self.calls = 0

    @async_cached_property
    async def value(self):
        self.calls += 1
        await asyncio.sleep(0.01)
        return self.calls


def test_computes_once_and_caches():
    async def go():
        t = Thing()
        return await t.value, await t.value, t.calls
    assert asyncio.run(go()) == (1, 1, 1)


def test_concurrent_first_awaits_share_one_call():
    async def go():
        t = Thing()
        results = await asyncio.gather(*(t.value for _ in range(5)))
        return results, t.calls
    assert asyncio.run(go()) == ([1] * 5, 1)


def test_cache_is_per_instance():
    async def go():
        a, b = Thing(), Thing()
        await a.value
        return await b.value, a.calls, b.calls
    assert asyncio.run(go()) == (1, 1, 1)


def test_bare_access_leaves_no_unawaited_coroutine():
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        Thing().value  # noqa: B018
        import gc; gc.collect()


def test_set_and_delete_reset_the_cache():
    async def go():
        t = Thing()
        t.value = 42
        first = await t.value
        del t.value
        return first, await t.value
    assert asyncio.run(go()) == (42, 1)


def test_rejects_sync_getter():
    with pytest.raises(TypeError):
        async_cached_property(lambda self: 1)
