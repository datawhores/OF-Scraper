r"""
        _____                                               
  _____/ ____\______ ________________    ____   ___________ 
 /  _ \   __\/  ___// ___\_  __ \__  \  /  _ \_/ __ \_  __ \
(  <_> )  |  \___ \\  \___|  | \// __ \(  <_> )  ___/|  | \/
 \____/|__| /____  >\___  >__|  (____  /\____/ \___  >__|   
                 \/     \/           \/            \/       
"""

__title__ = "ofscraper"
__author__ = "datawhores"
__author_email__ = "datawhores@riseup.net"
__description__ = (
    "A command-line program to quickly download,like or unlike posts, and more"
)
__url__ = "https://github.com/datawhores/OF-Scraper"
__license__ = "GNU General Public License v3 or later (GPLv3+)"
__copyright__ = "Copyright 2023"


try:
    from dunamai import Version

    __hardcoded__ = None
    __version__ = __hardcoded__ or Version.from_git(
        pattern="(?P<base>\d+\.\d+(\.((\d+\.\w+)|\w+)|))"
    ).serialize(format="{base}+{branch}.{commit}", metadata=False)
    if __version__ == "0.0.0":
        print(__version__)
        # raise Exception("pipx error")
except:
    import importlib

    __version__ = importlib.metadata.version("ofscraper")
