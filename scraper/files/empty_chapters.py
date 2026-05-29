from scraper.download.download_progress import DownloadType
from scraper.download.progress_manager import RangesProgressManager
from scraper.files.util import (
    files_in_dir,
    images_in_dir,
    partition_image_files,
    partition_text_files,
    remove_chapter,
)
from scraper.util.dynamic_ranges import Ranges


def list_empty_chapters(
    name: str | None = None, threshold: int = 1, verbose: bool = False
):
    pm = RangesProgressManager()
    empty_chapters = __empty_chapters(name, threshold, pm, verbose)
    if empty_chapters:
        print("Empty chapters:")
        print(
            "\t"
            + "\n\t".join(
                [
                    f"{name} {chapters_ranges}"
                    for name, chapters_ranges in empty_chapters.items()
                    if list(chapters_ranges.chapters())
                ]
            )
        )
    else:
        print("No empty chapters!")


def remove_empty_chapters(
    name: str | None = None, threshold: int = 1, verbose: bool = False
):
    pm = RangesProgressManager()
    empty_chapters = __empty_chapters(name, threshold, pm, verbose)
    for name, chapters in empty_chapters.items():
        print(f"Removing {name} {chapters}")
        for chapter in chapters.chapters():
            remove_chapter(name, chapter, pm)


def __empty_chapters(
    name: str | None, threshold: int, pm: RangesProgressManager, verbose: bool
) -> dict[str, Ranges]:
    if name is not None:
        return {name: __empty_chapters_for(name, threshold, pm, verbose)}

    res: dict[str, Ranges] = {}
    progress = pm.load_progress()
    for name in progress.progress_by_name:
        print(f"checking {name}")
        res[name] = __empty_chapters_for(name, threshold, pm, verbose)
    return res


def __empty_chapters_for(
    name: str, threshold: int, pm: RangesProgressManager, verbose: bool
) -> Ranges:
    res = Ranges(ranges=[])
    empty_text_signifiers = ['<p class="error">此信息不存在</p>']
    progress = pm.load_progress()
    if name in progress.progress_by_name:
        prog = progress.progress_by_name[name]
        if prog.download_type is DownloadType.text:
            text_files = files_in_dir(prog.base_dir(), extensions=[".txt"])
            for (name, chapter), chapter_path in partition_text_files(
                text_files
            ).items():
                text = ""
                with open(chapter_path, encoding="utf-8") as f:
                    text = f.read()
                if any([ets in text for ets in empty_text_signifiers]):
                    if verbose:
                        print(f"{name} {chapter} is empty")
                    _ = res.add(chapter)

            return res
        if prog.has_base_dir():
            images = images_in_dir(prog.base_dir() / "downloaded_images")
            image_partition = partition_image_files(images)
            for (name, chapter), chapter_paths in image_partition.items():
                if verbose:
                    print(
                        f"{name} {chapter}: {len(chapter_paths)} paths: {chapter_paths}"
                    )
                if len(chapter_paths) <= threshold:
                    _ = res.add(chapter)
            for chapter in prog.chapters():
                if (name, chapter) not in image_partition:
                    _ = res.add(chapter)
    return res
