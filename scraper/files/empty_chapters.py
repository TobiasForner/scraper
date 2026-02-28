from scraper.files.util import (
    images_in_dir,
    partition_improved_images,
)
from scraper.files.util import remove_chapter
from scraper.download.progress_manager import RangesProgressManager


def list_empty_chapters(
    name: str | None = None, threshold: int = 1, verbose: bool = False
):
    pm = RangesProgressManager()
    empty_chapters = __empty_chapters(name, threshold, pm, verbose)
    if empty_chapters:
        print("Empty chapters:")
        print(
            "\t"
            + "\n\t".join([f"{name} {chapter}" for name, chapter in empty_chapters])
        )
    else:
        print("No empty chapters!")


def remove_empty_chapters(
    name: str | None = None, threshold: int = 1, verbose: bool = False
):
    pm = RangesProgressManager()
    empty_chapters = __empty_chapters(name, threshold, pm, verbose)
    for name, chapter_string in empty_chapters:
        print(f"Removing {name} {chapter_string}")
        remove_chapter(name, int(chapter_string), pm)


def __empty_chapters(
    name: str | None, threshold: int, pm: RangesProgressManager, verbose: bool
) -> list[tuple[str, str]]:
    res = []

    if name is not None:
        return [
            (name, chapter)
            for chapter in __empty_chapters_for(name, threshold, pm, verbose)
        ]

    res = []
    progress = pm.load_progress()
    for name in progress.progress_by_name:
        res += [
            (name, chapter)
            for chapter in __empty_chapters_for(name, threshold, pm, verbose)
        ]
    return res


def __empty_chapters_for(
    name: str, threshold: int, pm: RangesProgressManager, verbose: bool
) -> list[str]:
    res = []
    progress = pm.load_progress()
    if name in progress.progress_by_name:
        prog = progress.progress_by_name[name]
        if prog.download_type == "text":
            return res
        if prog.has_base_dir():
            images = images_in_dir(prog.base_dir() / "downloaded_images")
            image_partition = partition_improved_images(images)
            for (name, chapter), chapter_paths in image_partition.items():
                if verbose:
                    print(
                        f"{name} {chapter}: {len(chapter_paths)} paths: {chapter_paths}"
                    )
                if len(chapter_paths) <= threshold:
                    res.append(chapter)
            for chapter in prog.chapters():
                chapter_string = f"{chapter:04d}"
                if (name, chapter_string) not in image_partition:
                    res.append(chapter_string)

    return res
