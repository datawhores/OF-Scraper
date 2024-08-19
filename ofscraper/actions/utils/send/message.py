import asyncio
import platform

import ofscraper.actions.utils.globals as common_globals


def set_send_msg():
    global send_msg_helper
    global send_msg_alt_helper

    if platform.system() != "Windows":
        send_msg_helper = send_msg_unix
        send_msg_alt_helper = send_msg_alt_unix
    else:
        send_msg_helper = send_msg_win
        send_msg_alt_helper = send_msg_alt_win


async def send_msg(msg):
    global send_msg_helper
    await send_msg_helper(msg)


async def send_msg_alt(msg):
    global send_msg_helper
    await send_msg_alt_helper(msg)


async def send_msg_win(msg):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        common_globals.lock_pool, common_globals.pipe_lock.acquire
    )
    try:
        await common_globals.pipe.coro_send(msg)
    finally:
        common_globals.pipe_lock.release()


async def send_msg_alt_win(msg):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        common_globals.lock_pool, common_globals.pipe_alt_lock.acquire
    )
    try:
        await common_globals.pipe_alt.coro_send(msg)
    finally:
        common_globals.pipe_alt_lock.release()


async def send_msg_unix(msg):
    await common_globals.pipe.coro_send(msg)


async def send_msg_alt_unix(msg):
    await common_globals.pipe_alt.coro_send(msg)
