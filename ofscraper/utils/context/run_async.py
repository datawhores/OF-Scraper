import asyncio

import ofscraper.utils.context.exit as exit

# utils/context/run_async.py

import asyncio
import ofscraper.utils.context.exit as exit


def run(coro):
    def inner(*args, **kwargs):
        try:
            # Get the loop or create a new one
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if not loop.is_running():
            try:
                # Use run_until_complete for the top-level coro
                return loop.run_until_complete(coro(*args, **kwargs))
            except KeyboardInterrupt as E:
                # Keep the protection, but simplify the exit
                with exit.DelayedKeyboardInterrupt():
                    # Let the normal cleanup happen in 'finally'
                    pass
                raise E
            finally:
                # Soft cleanup: shut down generators without killing the loop instantly
                if loop.is_running():
                    loop.run_until_complete(loop.shutdown_asyncgens())
        # If the loop is ALREADY running (nested call), just return the coro
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
