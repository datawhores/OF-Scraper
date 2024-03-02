from collections import abc
from contextlib import asynccontextmanager
from functools import partial, singledispatch

import ofscraper.download.common.globals as common_globals
from ofscraper.classes.semaphoreDelayed import semaphoreDelayed


@singledispatch
def sem_wrapper(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return sem_wrapper(args[0])
    return sem_wrapper(**kwargs)


@sem_wrapper.register
def _(input_sem: semaphoreDelayed):
    return partial(sem_wrapper, input_sem=input_sem)


@sem_wrapper.register
@asynccontextmanager
async def _(input_sem: semaphoreDelayed):
    await input_sem.acquire()
    try:
        yield
    except Exception as E:
        raise E
    finally:
        input_sem.release()


@sem_wrapper.register
def _(func: abc.Callable, input_sem: None | semaphoreDelayed = None):
    async def inner(*args, input_sem=input_sem, **kwargs):
        input_sem = input_sem or common_globals.sem
        await input_sem.acquire()
        try:
            return await func(*args, **kwargs)
        except Exception as E:
            raise E
        finally:
            input_sem.release()

    return inner
