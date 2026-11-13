import importlib
import re

from bs4 import BeautifulSoup

import ofscraper.utils.settings as settings

html_parser = "lxml" if importlib.util.find_spec("lxml") else "html.parser"


class base:
    def __init__(self):
        None

    def text_trunicate(self, text):
        text = str(text)
        if text is None:
            return "None"
        if len(text) == 0:
            return text
        length = int(settings.get_settings().text_length)
        if length == 0:
            return text
        elif settings.get_settings().text_type == "letter":
            return f"{''.join(list(text)[:length])}"
        else:
            # text has usually been through file_cleanup already, which swaps
            # spaces for space_replacer, so words are split on that. If the
            # original text already contained that character (e.g. "_" in a
            # caption with "_" as the replacer), it also counts as a word
            # break; the original spaces can't be told apart at this point.
            sep = settings.get_settings().space_replacer or " "
            if sep not in text:
                sep = " "
            words = [x for x in text.split(sep) if x]
            text = sep.join(words[:length])
        text = re.sub(" +$", "", text)
        return text

    def file_cleanup(self, text):
        text = str(text)
        text = re.sub("<[^>]*>", "", text)
        text = re.sub(r'[\n<>:"/\|?*:;]+', "", text)
        text = re.sub("-+", "_", text)
        text = re.sub(" +", " ", text)
        text = re.sub(" ", settings.get_settings().space_replacer, text)
        return text

    def db_cleanup(self, string):
        string = string or ""
        string = re.sub("<[^>]*>", "", string)
        string = " ".join(string.split())
        string = BeautifulSoup(string, html_parser).get_text()
        return string
