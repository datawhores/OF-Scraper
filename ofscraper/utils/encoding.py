r"""

 _______  _______         _______  _______  _______  _______  _______  _______  _______
(  ___  )(  ____ \       (  ____ \(  ____ \(  ____ )(  ___  )(  ____ )(  ____ \(  ____ )
| (   ) || (    \/       | (    \/| (    \/| (    )|| (   ) || (    )|| (    \/| (    )|
| |   | || (__     _____ | (_____ | |      | (____)|| (___) || (____)|| (__    | (____)|
| |   | ||  __)   (_____)(_____  )| |      |     __)|  ___  ||  _____)|  __)   |     __)
| |   | || (                   ) || |      | (\ (   | (   ) || (      | (      | (\ (
| (___) || )             /\____) || (____/\| ) \ \__| )   ( || )      | (____/\| ) \ \__
(_______)|/              \_______)(_______/|/   \__/|/     \||/       (_______/|/   \__/

"""

import locale
import logging


def read_text_file(path):
    """
    A hand-editable text file such as config.json or auth.json: UTF-8, with
    or without a BOM, or else the system's local encoding (Notepad's "ANSI").
    """
    with open(path, "rb") as f:
        data = f.read()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        # not getpreferredencoding(): in UTF-8 mode (the default from
        # Python 3.15) that says UTF-8 instead of the ANSI code page
        fallback = locale.getencoding()
        logging.getLogger("shared").debug(
            f"{path} isn't UTF-8, reading it as {fallback}"
        )
        return data.decode(fallback)


def encode_utf_16(string):
    encoded_string = string.encode("utf-16", "surrogatepass")
    decoded_string = encoded_string.decode("utf-16")
    return decoded_string
