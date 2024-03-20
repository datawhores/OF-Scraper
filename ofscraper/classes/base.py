import importlib
import re

from bs4 import BeautifulSoup

import ofscraper.utils.config.data as data

html_parser = "lxml" if importlib.util.find_spec("lxml") else "html.parser"


class base:
    def __init__(self):
        None

    def text_trunicate(self, text):
        text = str(text)
        if text == None:
            return "None"
        if len(text) == 0:
            return text
        length = int(data.get_textlength(mediatype="Text"))
        if length == 0:
            return text
        elif data.get_textType(mediatype="Text") == "letter":
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
        text = re.sub('[\n<>:"/\|?*:;]+', "", text)
        text = re.sub("-+", "_", text)
        text = re.sub(" +", " ", text)
        text = re.sub(" ", data.get_spacereplacer(mediatype=mediatype), text)
        return text

    def db_cleanup(self, string):
        text = str(text)
        string = re.sub("<[^>]*>", "", string)
        string = " ".join(string.split())
        string = BeautifulSoup(string, html_parser).get_text()
