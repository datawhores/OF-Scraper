import re

from bs4 import BeautifulSoup

def sanitize_text(string):
    if string:
        try:
            import lxml as unused_lxml_

            html_parser = "lxml"
        except ImportError:
            html_parser = "html.parser"

        string = re.sub("<[^>]*>", "", string)
        string = " ".join(string.split())
        string = BeautifulSoup(string, html_parser).get_text()
        return string
    return string
