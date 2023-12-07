#!/root/OF-Scraper/.venv/bin/python
import multiprocessing

import ofscraper.start as start
import ofscraper.utils.system as system


def main():
    if system.get_parent():
        start.main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
