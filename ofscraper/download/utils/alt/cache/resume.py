
import asyncio
from functools import partial


import ofscraper.download.utils.globals as common_globals
import ofscraper.utils.cache as cache


async def get_data(ele,item):
    data = await asyncio.get_event_loop().run_in_executor(
        common_globals.thread,
        partial(cache.get, f"{item['name']}_{ele.id}_{ele.username}_headers"),
    ) 
    return data
async def set_data(ele,item,data):
    data = await asyncio.get_event_loop().run_in_executor(
        common_globals.thread,
        partial(cache.set, f"{item['name']}_{ele.id}_{ele.username}_headers",data),
    )
    return data




