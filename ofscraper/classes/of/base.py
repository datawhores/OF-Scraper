import importlib
import re

from bs4 import BeautifulSoup

import ofscraper.utils.settings as settings

html_parser = "lxml" if importlib.util.find_spec("lxml") else "html.parser"

# Fansly caption formatting, from the Fansly web app's caption parser:
# **bold**, *italic*, ~~strike~~, [s:lg]size[/s], [c:blue]colour[/c],
# [text](url) links, and a backslash before * ~ [ ] \ to show it as written
FANSLY_ESCAPED = re.compile(r"\\([*~\[\]\\])")
FANSLY_LINK = re.compile(r"\[([^\[\]]*)\]\([^()\s]*\)")
FANSLY_TAG = re.compile(r"\[(?:[sc]:[\w-]+|/[sc])\]|~~", re.IGNORECASE)
FANSLY_BOLD = re.compile(r"\*\*(?=\S)(.+?)\*\*", re.DOTALL)
FANSLY_ITALIC = re.compile(r"\*(?=\S)([^*]+?)\*")
# escaped characters are parked in the Private Use Area while markup is removed
_ESCAPABLE = "*~[]\\"
_PARK = 0xE000


def strip_fansly_markup(text):
    """The caption as Fansly shows it: formatting removed, link text kept."""
    if not text:
        return text
    text = FANSLY_ESCAPED.sub(lambda m: chr(_PARK + _ESCAPABLE.index(m[1])), text)
    text = FANSLY_LINK.sub(r"\1", text)
    text = FANSLY_TAG.sub("", text)
    text = FANSLY_BOLD.sub(r"\1", text)
    text = FANSLY_ITALIC.sub(r"\1", text)
    for i, ch in enumerate(_ESCAPABLE):
        text = text.replace(chr(_PARK + i), ch)
    return text


def _is_fansly():
    import ofscraper.sites as sites

    return sites.is_fansly()


class base:
    def __init__(self):
        pass

    def text_trunicate(self, text):
        text = str(text)
        if text is None:
            return "None"
        if len(text) == 0:
            return text
        length = int(settings.get_settings().text_length)
        if length == 0:
            return text
        sep = settings.get_settings().space_replacer or " "
        if settings.get_settings().text_type == "letter":
            text = "".join(list(text)[:length])
        else:
            # text has usually been through file_cleanup already, which swaps
            # spaces for space_replacer, so words are split on that. If the
            # original text already contained that character (e.g. "_" in a
            # caption with "_" as the replacer), it also counts as a word
            # break; the original spaces can't be told apart at this point.
            word_sep = sep if sep in text else " "
            words = [x for x in text.split(word_sep) if x]
            text = word_sep.join(words[:length])
        # a cut can end on a separator; don't leave "Good_" or "Good "
        text = re.sub(f"(?:{re.escape(sep)}| )+$", "", text)
        return text

    def file_cleanup(self, text):
        text = str(text)
        text = re.sub("<[^>]*>", "", text)
        # before ":" and "/" are dropped, which would leave "[slg]" and "[s]"
        if _is_fansly():
            text = strip_fansly_markup(text)
        text = re.sub(r'[\n<>:"/\|?*:;]+', "", text)
        text = re.sub("-+", "_", text)
        text = re.sub(" +", " ", text)
        text = re.sub(" ", settings.get_settings().space_replacer, text)
        return text

    def db_cleanup(self, string):
        string = string or ""
        string = re.sub("<[^>]*>", "", string)
        if _is_fansly():
            string = strip_fansly_markup(string)
        string = " ".join(string.split())
        string = BeautifulSoup(string, html_parser).get_text()
        return string
