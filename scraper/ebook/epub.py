import itertools
import math
from pathlib import Path

import bs4
import platformdirs
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString, PageElement
from ebooklib import epub
from pydantic import BaseModel

from scraper.download.download_progress import RangesProgress
from scraper.download.progress_manager import RangesProgressManager


def assemble(
    name: str, chapters: list[int] | None = None, book_size: int | None = None
):
    progress_manager = RangesProgressManager()
    progress = progress_manager.load_progress()
    progress = progress.progress_by_name[name]
    if chapters is None:
        chapters = list(progress.chapters())
        chapters.sort()
    fill_size = len(str(chapters[-1]))
    rs = RemoveStrings.load()
    if book_size:
        for i in range(math.ceil(len(chapters) / book_size)):
            start_chapter = chapters[i * book_size]
            end_chapter = chapters[
                min(len(chapters) - 1, (i + 1) * book_size - 1)
            ]
            chaps = chapters[i * book_size : (i + 1) * book_size]
            build_epub(
                progress,
                name,
                chaps,
                remove_strings=rs,
                book_name=f"{name}_{str(start_chapter).zfill(fill_size)}-{str(end_chapter).zfill(fill_size)}",
            )
    else:
        build_epub(progress, name, chapters, remove_strings=rs)


class RemoveStrings(BaseModel):
    text_to_remove: list[str]
    lines_to_remove: list[list[str]]

    @staticmethod
    def load():
        file_location = RemoveStrings.json_file_location()
        if not file_location.exists():
            return RemoveStrings(text_to_remove=[], lines_to_remove=[])
        with open(file_location, encoding="utf-8") as in_file:
            text = in_file.read()
            return RemoveStrings.model_validate_json(text)

    def store(self):
        with open(
            RemoveStrings.json_file_location(), "w", encoding="utf-8"
        ) as out_file:
            _ = out_file.write(self.model_dump_json())

    @staticmethod
    def json_file_location() -> Path:
        return (
            Path(platformdirs.user_data_dir("scraper", "TF"))
            / "epub_remove_strings.json"
        )


def get_html_text(
    progress: RangesProgress,
    name: str,
    chapter: int,
    remove_strings: RemoveStrings,
) -> str | None:
    chapter_path = progress.dl_locations[0] / f"{name}_{chapter}.txt"
    with open(chapter_path, encoding="utf-8") as f:
        text = f.read()
        soup = BeautifulSoup(text, features="lxml")
    content = soup.find("div", id="chapter-content")

    if content is None:
        content = soup.find("div", id="post-body")
    if content is None:
        content = soup.find("article", id="chapter-content")
    if content is None:
        content = soup.find("div", class_="episode-content")
    if content is None:
        return None
    text = collapse_whitespace(
        content, chapter=chapter, remove_strings=remove_strings
    )
    return text


def collapse_whitespace(
    content: bs4.element.Tag, chapter: int, remove_strings: RemoveStrings
) -> str:
    sentence_end_patterns = [
        ".",
        '."',
        "?",
        "!",
        '?"',
        '!"',
        "'.",
        "'?",
        "'!",
        "”",
        "＊＊＊",
        "’",
        "…",
        "]",
    ]
    elems = content.children

    def extract_text(elem: PageElement) -> list[str]:
        t: str = elem.text
        if len(t) > 5000 and isinstance(elem, Tag):
            return leaf_texts(elem)
        return [t]

    text_segments = list(itertools.chain(*(extract_text(e) for e in elems)))

    # remove phrases
    for pr in remove_strings.text_to_remove:
        text_segments = [t.replace(pr, "") for t in text_segments]

    text_segments = [t.replace(f"Chapter {chapter}", "") for t in text_segments]
    text_segments = [t.strip() for t in text_segments if t.strip()]

    # combine lines that need it
    last_finished = True
    combined: list[str] = []
    for i, t in enumerate(text_segments):
        if not last_finished and not any(
            t.startswith(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ):
            combined[-1] += f" {t}"
        else:
            combined.append(t)
        last_finished = (
            any(t.endswith(s) for s in sentence_end_patterns) or i == 0
        )

    # assemble text
    text = f"<h1>Chapter {chapter}</h1>"
    for t in combined:
        text += f"<p>{t}</p>"

    # enforce space between sentences
    for se in sentence_end_patterns:
        for next_char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            text = text.replace(f"{se}{next_char}", f"{se} {next_char}")

    final_strings_to_remove = [
        "".join([f"<p>{line}</p>" for line in lines])
        for lines in remove_strings.lines_to_remove
    ]
    for fin_s_to_rem in final_strings_to_remove:
        text = text.replace(fin_s_to_rem, "")
    return text


def leaf_texts(root: bs4.element.Tag) -> list[str]:
    """
    Returns a list of all leaf node texts.
    This is an approximation that should capture all text on the online novel sites I have found so far
    """
    texts = [
        node.strip()
        for node in root.descendants
        if isinstance(node, NavigableString) and node.strip()
    ]
    return texts


def build_epub(
    progress: RangesProgress,
    name: str,
    chapters: list[int],
    remove_strings: RemoveStrings,
    book_name: str | None = None,
):
    book = epub.EpubBook()
    if book_name is None:
        book_name = name
    print(f"Building {book_name}")
    book.set_title(book_name)
    book.set_language("en")
    toc = []
    spine: list[str | epub.EpubHtml] = ["nav"]
    for chapter in chapters:
        chapter_title = f"chapter {chapter}"
        chapter_file = f"chapter{chapter}.xhtml"
        c = epub.EpubHtml(
            title=chapter_title, file_name=chapter_file, lang="en"
        )
        content = get_html_text(
            progress=progress,
            name=name,
            chapter=chapter,
            remove_strings=remove_strings,
        )
        if content is None:
            print(f"failed to find content for {name} {chapter}")
            continue
        elif content == "":
            print("chapter", chapter, "empty")
        c.content = content
        toc.append(epub.Link(chapter_file, chapter_title, f"reaper_{chapter}"))
        spine.append(c)
        book.add_item(c)

    nav_css = epub.EpubItem(
        uid="style_nav",
        file_name="style/nav.css",
        media_type="text/css",
        content="BODY {color: black; background-color: white;}",
    )
    book.spine = spine
    book.toc = toc
    book.add_item(nav_css)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    epub.write_epub(f"{book_name}.epub", book)
