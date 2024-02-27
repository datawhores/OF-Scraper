import asyncio
import platform

import ofscraper.download.common.globals as common_globals


def set_send_msg():
    global send_msg_helper
    if platform.system() != "Windows":
        send_msg_helper = send_msg_unix
    else:
        send_msg_helper = send_msg_win


async def send_msg(msg):
    global send_msg_helper
    await send_msg_helper(msg)


async def send_msg_win(msg):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        common_globals.lock_pool, common_globals.pipe_lock.acquire
    )
    try:
        await common_globals.pipe.coro_send(msg)
    finally:
        await loop.run_in_executor(
            common_globals.lock_pool, common_globals.pipe_lock.release
        )


async def send_msg_unix(msg):
    await common_globals.pipe.coro_send(msg)
