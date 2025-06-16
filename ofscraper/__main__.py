#!/root/OF-Scraper/.venv/bin/python
# -*- coding: utf-8 -*-
import multiprocessing

import ofscraper.main.open.load as load
import ofscraper.utils.system.system as system


def main():
    if system.get_parent():
        load.main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
