import html
import importlib
import logging
import re

from bs4 import BeautifulSoup

import ofscraper.sites as sites
import ofscraper.utils.settings as settings

html_parser = "lxml" if importlib.util.find_spec("lxml") else "html.parser"
log = logging.getLogger("shared")
# (textlength, text_type) settings whose cut has been logged
_cut_logged = set()


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
        # 0 is no limit, and so is a negative length (naming_check reports it)
        if length <= 0:
            return text
        sep = settings.get_settings().space_replacer or " "
        text_type = settings.get_settings().text_type
        if text_type == "letter":
            cut = len(text) > length
            text = "".join(list(text)[:length])
        else:
            # text has usually been through file_cleanup already, which swaps
            # spaces for space_replacer, so words are split on that. If the
            # original text already contained that character (e.g. "_" in a
            # caption with "_" as the replacer), it also counts as a word
            # break; the original spaces can't be told apart at this point.
            word_sep = sep if sep in text else " "
            words = [x for x in text.split(word_sep) if x]
            cut = len(words) > length
            text = word_sep.join(words[:length])
        # a cut can end on a separator; don't leave "Good_" or "Good "
        text = re.sub(f"(?:{re.escape(sep)}| )+$", "", text)
        # about the setting, not the text: said once per run, not per media
        if cut and (length, text_type) not in _cut_logged:
            _cut_logged.add((length, text_type))
            unit = "letters" if text_type == "letter" else "words"
            log.debug(
                f"{{text}} cut to {length} {unit} (text_type_default: {text_type})"
            )
        return text

    def file_cleanup(self, text):
        text = str(text)
        # OnlyFans captions are HTML; Fansly captions are plain text, so a
        # "<3 you >" or an "&amp;" there is what was written
        if not sites.is_fansly():
            # a <br> or the end of a paragraph separates words too
            text = re.sub(
                r"<br\s*/?>|</?(?:p|div|li|h[1-6])\b[^>]*>",
                " ",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub("<[^>]*>", "", text)
            # OnlyFans sends text HTML-escaped ("Tom &amp; Jerry"), as it
            # does label names (labels.decode_label_name). Decoded after the
            # tags are gone, so a decoded "<" isn't read as one. Only an
            # entity ending in ";" is decoded: a cleaned name has none left,
            # so cleaning it again decodes nothing twice. A decoded "\" or
            # "/" would be a folder in the name ("&#92;..&#92;" climbs out of
            # the save folder on Windows), so it's removed, as is a decoded
            # control character other than a line break or tab.
            text = re.sub(
                r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);",
                lambda m: re.sub(
                    r"[\\/\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
                    "",
                    html.unescape(m[0]),
                ),
                text,
            )
        # a line break or a tab, written or decoded ("&#10;"), separates
        # words: removing it would join the words on either side
        text = re.sub(r"[\r\n\t]+", " ", text)
        text = text.replace("\xa0", " ")
        # Fansly text is plain already (normalize._item_dict); removing the
        # codes again would drop an escaped "\[s:lg\]", shown as "[s:lg]"
        # a backslash is a folder separator on Windows, and control characters
        # (tab, carriage return) can't be in a Windows file name
        import ofscraper.utils.paths.names as names

        text = names.strip_caption_chars(text)
        text = re.sub("-+", "_", text)
        text = re.sub(" +", " ", text).strip(" ")
        # literal text: a backslash isn't a re.sub escape here
        text = text.replace(" ", settings.get_settings().space_replacer)
        return text

    def db_cleanup(self, string):
        string = string or ""
        string = re.sub("<[^>]*>", "", string)
        # Fansly text is plain already (normalize._item_dict): removing the
        # codes again would turn an escaped "\*sale\*", shown as "*sale*",
        # into "sale"
        string = " ".join(string.split())
        string = BeautifulSoup(string, html_parser).get_text()
        return string
