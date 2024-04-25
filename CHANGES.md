# Changes

Note:

This doc was made around the beginning of the project
It is not being updated and won't be

There have been a lot more features added since then

- scrape paid content for a single model or multiple models using --username name,name2 --purchased
- allow for multiple downloads simetenously during paid content scraping
- tracking of paid content progress
- allow for force redownloading of content
- combine scraping modes [--action, --post,--paid]
- supress output with silent mode --silent
- sorts all downloads into seperate folders automatically
- fix low memory issue for paid downloads
- One time username selections for each run.
- set minimal interval for daemon mode in minutes
- filename support (limited)
- Easier to select multiple models when username arg is not passed
- safety check to prevent overwritting files. Important when forcing redownloading
- small refactoring for other parts of the code
- change tuples from scraping into objects
- fuzzy search in username selection
- simplify username selection when username args not pass
- automatic cookie extractions
- improve authentication flow
- add cache to scraper
- add metadata support
- username filter
- progress bar for scraper
- Added dynamic naming scheme for folders, and files
- Allow for metadata folder selection
- Allow for filtering by file type
-
