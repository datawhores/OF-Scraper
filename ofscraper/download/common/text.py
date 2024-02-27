import textwrap
import traceback

import aiofiles

import ofscraper.classes.placeholder as placeholder
import ofscraper.download.common.globals as common_globals
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings
from ofscraper.download.common.common import get_medialog


async def get_text(ele, username, model_id):
    try:
        if "Text" not in settings.get_mediatypes():
            return
        elif bool(ele.text) == False:
            return
        placeholderObj = placeholder.Placeholders()
        file_data = await placeholderObj.get_final_trunicated_path(
            ele, username, model_id, "txt"
        )
        file_data = str(file_data)
        wrapped_text = textwrap.wrap(
            ele.text, width=constants.getattr("MAmoX_TEXT_LENGTH")
        )
        async with aiofiles.open(file_data, "w") as p:
            await p.writelines(wrapped_text)
    except Exception as E:
        common_globals.log.traceback_(f"{get_medialog(ele)} {E}")
        common_globals.log.traceback_(f"{get_medialog(ele)} {traceback.format_exc()}")
