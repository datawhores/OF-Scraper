# Changes

**Note:** This document was written near the beginning of the project. It is not updated and will not be; many more features have been added since.

- Scrape paid content for a single model or multiple models using `--username name,name2 --purchased`
- Allow multiple simultaneous downloads during paid content scraping
- Track paid content progress
- Allow force re-downloading of content
- Combine scraping modes (`--action`, `--post`, `--paid`)
- Suppress output with silent mode (`--silent`)
- Sort all downloads into separate folders automatically
- Fix low-memory issue for paid downloads
- One-time username selections for each run
- Set minimum interval for daemon mode in minutes
- Filename support (limited)
- Easier selection of multiple models when the username argument is not passed
- Safety check to prevent overwriting files (important when forcing re-downloads)
- Small refactoring for other parts of the code
- Change tuples from scraping into objects
- Fuzzy search in username selection
- Simplify username selection when username arguments are not passed
- Automatic cookie extractions
- Improve authentication flow
- Add cache to scraper
- Add metadata support
- Username filter
- Progress bar for scraper
- Add dynamic naming scheme for folders and files
- Allow metadata folder selection
- Allow filtering by file type
