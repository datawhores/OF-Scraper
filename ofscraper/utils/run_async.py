import asyncio
import ofscraper.utils.exit as exit

def run(coro):
    def inner(*args,**kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tasks=loop.run_until_complete(coro(*args,**kwargs))
            return tasks
        except KeyboardInterrupt as E:
            with exit.DelayedKeyboardInterrupt():
                try:
                    tasks.cancel()
                    loop.run_forever()
                    tasks.exception()
                except:
                    None
            raise E
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    return inner