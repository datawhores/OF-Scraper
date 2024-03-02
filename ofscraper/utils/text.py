import asyncio
import pathlib
import textwrap
import traceback
from concurrent.futures import ThreadPoolExecutor

import aiofiles

import ofscraper.classes.placeholder as placeholder
import ofscraper.download.common.globals as common_globals
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
from ofscraper.utils.context.run_async import run


@run
async def get_text(values):
    return
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_TEXT_WORKER")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        async with asyncio.TaskGroup() as tg:
            [tg.create_task(get_text_process(value)) for value in values]


async def get_text_process(ele):
    username = ele.username
    model_id = ele.model_id
    try:
        if "Text" not in settings.get_mediatypes():
            return
        elif bool(ele.text) == False:
            return
        placeholderObj = placeholder.Placeholders()
        file_data = await placeholderObj.get_final_trunicated_path(
            ele, username, model_id, "txt"
        )
        if pathlib.Path(file_data).exists():
            return
        file_data = str(file_data)
        wrapped_text = textwrap.wrap(
            ele.text, width=constants.getattr("MAX_TEXT_LENGTH")
        )
        async with aiofiles.open(file_data, "w") as p:
            await p.writelines(wrapped_text)
    except Exception as E:
        common_globals.log.traceback_(f"{E}")
        common_globals.log.traceback_(f"{traceback.format_exc()}")
