from typing import Annotated

import typer

from scraper.download.progress_manager import RangesProgressManager
from scraper.ebook.cbz import cbz_chapter_images, cbz_remaining
from scraper.ebook.epub import RemoveStrings, assemble

app = typer.Typer()


@app.command(help="Assemble chapters for 'name' into one or multiple epub files")
def epub(name: str, chapters: list[int] | None = None, book_size: int | None = None):
    assemble(name=name, chapters=chapters, book_size=book_size)


@app.command(help="Register a single string that should be removed in every final epub")
def epub_remove_text(text: str):
    rs = RemoveStrings.load()
    rs.text_to_remove.append(text)
    rs.store()


@app.command(
    help="Register a single string representing one or multiple lines that should be removed in every final epub. This only works if the text exactly matches line boundaries in the final epub"
)
def epub_remove_lines(
    lines: Annotated[
        str,
        typer.Argument(
            help="String representing one or multiple lines (separated '\n') that should be removed in every final epub"
        ),
    ],
):
    rs = RemoveStrings.load()
    rs.lines_to_remove.append(lines.splitlines())
    rs.store()


@app.command(help="zip files via 7zip (needs to be installed)")
def cbz_all(name: str, chapters: list[int]):
    pm = RangesProgressManager()
    for chapter in chapters:
        cbz_chapter_images(name, chapter, pm)


@app.command(help="zip files via 7zip (needs to be installed)")
def cbz_rem(name: str):
    pm = RangesProgressManager()
    cbz_remaining(name, pm)
