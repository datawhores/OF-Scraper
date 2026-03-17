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
    # No TaskGroup needed. Just build the coroutines and run them concurrently.
    tasks = [get_text_process(username, value) for value in values]

    await asyncio.gather(*tasks, return_exceptions=True)


async def get_text_process(username, ele):
    log = logging.getLogger("shared")
    dupe = (
        settings.get_settings().force_all or settings.get_settings().force_model_unique
    )

    if bool(ele.text) is False:
        return

    try:
        new_ele = copy.deepcopy(ele)
        new_ele.mediatype = "Text"

        placeholderObj = await placeholder.Textholders(new_ele, "txt").init()

        # Check for existing file BEFORE marking the attempt
        if pathlib.Path(placeholderObj.filepath).exists() and not dupe:
            # Returning without marking attempt will accurately log it as "skipped" in stats
            return

        # Now that we know we are writing to disk, officially mark the attempt
        ele.mark_text_download_attempt()

        wrapped_text = textwrap.wrap(
            new_ele.text, width=of_env.getattr("MAX_TEXT_LENGTH")
        )

        async with aiofiles.open(placeholderObj.filepath, "w") as p:
            await p.writelines(wrapped_text)

        await after_download_script(placeholderObj.filepath)

        # Verify it actually wrote to disk to log success/failure
        if placeholderObj.filepath.exists():
            ele.mark_text_downloaded(True)
        else:
            ele.mark_text_downloaded(False)

    except Exception as E:
        log.traceback_(f"{E}")
        log.traceback_(f"{traceback.format_exc()}")
        # If an error happens, ensure it's marked as an attempt so it logs as "failed"
        ele.mark_text_download_attempt()
        ele.mark_text_downloaded(False)
        return
