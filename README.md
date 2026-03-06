# Scraper
This is a tool to scrape text or images from websites.
The tool is centered arount chapter-based websites like webtoons or manga. See below for details and limitations.

## Features
- simple download of images or html source from websites
- automatic discovery of new releases (url-based)
- parallelized downloads
- conversion to epub (from text/html data)
- conversion to cbz for images (e.g. manga)
- scripts for image manipulation

**Note**: To deal with websites that load their content lazily, the tool lets the instrumented browser scroll through website content slowly in an attempt to mimic typical user behaviour.
Furthermore, it waits every now and then to avoid being caught for navigating websites too quickly or for sending too many requests.
Thus, it is recommended to use the tool to get multiple chapters while running in the background.
Then, the downloaded files can be processed further depending on their type.

## Quickstart
1. Install `scraper`: `pip install .`.
2. Look up a url for a chapter of the content you would like to scrape. Then getting started is as simple as replacing the chapter number in the url with the placeholder text `HERE` (it is planned to make this configurable at some point).
3. call `scrape dl download <url> <name>` (where `<name>` is an id without spaces of your choosing)
That's it. The download is started


## Implementation notes
The tool is structured around chapter-based websites like webtoons, manga, ...
The retrieval is usually started by a call of `scrape dl download <url> <name>` (see `scrape dl download --help` for further options).
To facilitate the automatic discovery of new releases, the url is expected to use the placeholder `HERE` for the position where the chapter number is supposed to be inserted.
This also means that websites that use urls without the chapter number are currently not supported.

## Development
This project uses [prek](https://github.com/j178/prek) to manage pre-commit hooks. Please install prek and initialize it via `prek install`.
