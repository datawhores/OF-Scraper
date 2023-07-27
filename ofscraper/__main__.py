#!/root/OF-Scraper/.venv/bin/python
import multiprocessing
import sys
import ofscraper.start as start
def main():
    sys.exit(start.main())

# protect the entry point
if __name__ == '__main__':
	# enable support for multiprocessing
    multiprocessing.freeze_support()
    main()
