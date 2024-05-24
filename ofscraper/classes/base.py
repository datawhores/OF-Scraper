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
        length = int(settings.get_textlength(mediatype=self.mediatype))
        if length == 0:
            return text
        elif settings.get_text_type() == "letter":
            return f"{''.join(list(text)[:length])}"
        else:
            # split and reduce
            wordarray = list(filter(lambda x: len(x) != 0, re.split("( )", text)))
            splitArray = wordarray[: length + 1]
            text = f"{''.join(splitArray)}"
        text = re.sub(" +$", "", text)
        return text

    def file_cleanup(self, text, mediatype=None):
        text = str(text)
        text = re.sub("<[^>]*>", "", text)
        text = re.sub('[\n<>:"/\|?*:;]+', "", text)
        text = re.sub("-+", "_", text)
        text = re.sub(" +", " ", text)
        text = re.sub(" ", settings.get_space_replacer(mediatype=mediatype), text)
        return text

    def db_cleanup(self, string):
        string = string or ""
        string = re.sub("<[^>]*>", "", string)
        string = " ".join(string.split())
        string = BeautifulSoup(string, html_parser).get_text()
        return string
