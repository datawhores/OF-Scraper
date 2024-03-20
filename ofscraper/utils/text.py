import asyncio
import copy
import logging
import pathlib
import textwrap
import traceback
from concurrent.futures import ThreadPoolExecutor

import aiofiles

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.args.read as read_args
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
from ofscraper.utils.context.run_async import run


async def get_text(values):
    with ThreadPoolExecutor(
        max_workers=constants.getattr("MAX_TEXT_WORKER")
    ) as executor:
        asyncio.get_event_loop().set_default_executor(executor)
        dupe = read_args.retriveArgs().dupe
        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(get_text_process(value, dupe=dupe)) for value in values
            ]
            results = []
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
        return (
            len(list(filter(lambda x: x == True, results))),
            len(list(filter(lambda x: x == False, results))),
            len(list(filter(lambda x: x == "exists", results))),
        )


async def get_text_process(ele, dupe=None):
    log = logging.getLogger("shared")
    try:
        if "Text" not in settings.get_mediatypes():
            return
        elif bool(ele.text) == False:
            return
        # make new text mediatype
        new_ele = copy.deepcopy(ele)
        new_ele.mediatype = "text"

        placeholderObj = placeholder.Textholders(new_ele, "txt")
        await placeholderObj.init()
        if pathlib.Path(placeholderObj.filepath).exists() and not dupe:
            return "exists"
        wrapped_text = textwrap.wrap(
            new_ele.text, width=constants.getattr("MAX_TEXT_LENGTH")
        )
        async with aiofiles.open(placeholderObj.filepath, "w") as p:
            await p.writelines(wrapped_text)
        return True
    except Exception as E:
        log.traceback_(f"{E}")
        log.traceback_(f"{traceback.format_exc()}")
        return False
