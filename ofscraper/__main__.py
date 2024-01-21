#!/root/OF-Scraper/.venv/bin/python
import multiprocessing

import ofscraper.runner.load as load
import ofscraper.utils.system.system as system


def main():
    if system.get_parent():
        load.main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
