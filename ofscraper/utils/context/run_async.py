import asyncio

import ofscraper.utils.context.exit as exit


def run(coro):
    def inner(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tasks = loop.run_until_complete(coro(*args, **kwargs))
            return tasks
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

    return inner
