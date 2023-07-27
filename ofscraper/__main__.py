#!/root/OF-Scraper/.venv/bin/python
import multiprocessing
import sys
import ofscraper.start as start

multiprocessing.freeze_support()
sys.exit(start.main())

