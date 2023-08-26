#!/root/OF-Scraper/.venv/bin/python
import multiprocessing
import ofscraper.start as start
import os
def main():
    start.set_mulitproc_start_type()
    start.set_eventloop()
    start.startvalues()
    start.discord_warning()
    start.main()

if __name__ == '__main__': 
    multiprocessing.freeze_support()

    main()

