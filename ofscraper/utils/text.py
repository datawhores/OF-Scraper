import asyncio
import copy
import logging
import pathlib
import textwrap
import traceback

import aiofiles

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.args.accessors.read as read_args
import ofscraper.utils.constants as constants


async def get_text(values):
    dupe = (
        read_args.retriveArgs().force_all
        or read_args.retriveArgs().force_model_unique
    )
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(get_text_process(value, dupe=dupe)) for value in values]
        results = []
    for task in asyncio.as_completed(tasks):
        result = await task
        results.append(result)
    return (
        len(list(filter(lambda x: x is True, results))),
        len(list(filter(lambda x: x is False, results))),
        len(list(filter(lambda x: x == "exists", results))),
    )


async def get_text_process(ele, dupe=None):
    log = logging.getLogger("shared")
    try:
        if bool(ele.text) is False:
            return
        # make new text mediatype
        new_ele = copy.deepcopy(ele)
        new_ele.mediatype = "text"

        placeholderObj = await placeholder.Textholders(new_ele, "txt").init()
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
