import asyncio

import ofscraper.utils.context.exit as exit


def run(coro):
    def inner(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        if not loop.is_running():
            try:
                asyncio.set_event_loop(loop)
                tasks = loop.run_until_complete(coro(*args, **kwargs))
                return tasks
            except RuntimeError:
                return coro(*args, **kwargs)
            except KeyboardInterrupt as E:
                with exit.DelayedKeyboardInterrupt():
                    try:
                        tasks.cancel()
                        loop.run_forever()
                        tasks.exception()
                    except Exception:
                        None
                raise E
            except Exception as E:
                raise E
            finally:
                try:
                    loop.close()
                except:
                    None
                asyncio.set_event_loop(None)
        return coro(*args, **kwargs)

    return inner


def run_forever(coro):
    def inner(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        if not loop.is_running():
            try:
                asyncio.set_event_loop(loop)
                tasks = loop.run_until_complete(coro(*args, **kwargs))
                loop.run_forever()
                return tasks
            except RuntimeError:
                return coro(*args, **kwargs)
            except KeyboardInterrupt as E:
                with exit.DelayedKeyboardInterrupt():
                    try:
                        tasks.cancel()
                        loop.run_forever()
                        tasks.exception()
                    except Exception:
                        None
                raise E
            except Exception as E:
                raise E
            finally:
                try:
                    loop.close()
                except:
                    None
                asyncio.set_event_loop(None)
        return coro(*args, **kwargs)

    return inner
