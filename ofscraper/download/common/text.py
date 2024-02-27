import copy
import re
import textwrap

import aiofiles

import ofscraper.classes.placeholder as placeholder
import ofscraper.utils.constants as constants
import ofscraper.utils.settings as settings


async def get_text(ele, username, model_id):
    if "Text" not in settings.get_mediatypes():
        return
    elif bool(ele.text) == False:
        return
    placeholderObj = placeholder.Placeholders()
    file_data = await placeholderObj.get_final_trunicated_path(
        ele, username, model_id, "txt"
    )
    file_data = str(file_data)
    wrapped_text = textwrap.wrap(ele.text, width=constants.getattr("MAX_TEXT_LENGTH"))
    async with aiofiles.open(file_data, "w") as p:
        await p.writelines(wrapped_text)
