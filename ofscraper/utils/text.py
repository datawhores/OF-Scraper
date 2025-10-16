import asyncio
import copy
import logging
import pathlib
import textwrap
import traceback

import aiofiles

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.of_env.of_env as of_env
import ofscraper.utils.settings as settings
from ofscraper.scripts.after_download_script import after_download_script


async def get_text(username, values):
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(get_text_process(username, value)) for value in values]
    for task in asyncio.as_completed(tasks):
        await task


async def get_text_process(username, ele):
    log = logging.getLogger("shared")
    dupe = (
        settings.get_settings().force_all or settings.get_settings().force_model_unique
    )
    try:
        if bool(ele.text) is False:
            return
        # make new text mediatype
        new_ele = copy.deepcopy(ele)
        new_ele.mediatype = "text"

        placeholderObj = await placeholder.Textholders(new_ele, "txt").init()
        if pathlib.Path(placeholderObj.filepath).exists() and not dupe:
            return
        ele.mark_text_download_attempt()
        wrapped_text = textwrap.wrap(
            new_ele.text, width=of_env.getattr("MAX_TEXT_LENGTH")
        )
        async with aiofiles.open(placeholderObj.filepath, "w") as p:
            await p.writelines(wrapped_text)
        after_download_script(placeholderObj.filepath)
    except Exception as E:
        log.traceback_(f"{E}")
        log.traceback_(f"{traceback.format_exc()}")
    if placeholderObj.filepath.exists():
        ele.mark_text_downloaded(True)
    else:
        ele.mark_text_downloaded(False)
