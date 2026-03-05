from scraper.download.progress_manager import (
    RangesProgressManager,
)
from pathlib import Path
from collections import defaultdict
import re

IMPROVED_PATTERN = re.compile(r"(.*)_(\d+)_\d+\.(jpeg|jpg|png|svg)")


def remove_chapter(name: str, chapter: int, pm: RangesProgressManager):
    progress = pm.load_progress()
    series_progress = progress.progress_by_name[name]
    chapter_dir = series_progress.base_dir() / "downloaded_images"
    local_files = images_in_dir(chapter_dir)
    part = partition_improved_images(local_files)
    for image in part[(name, chapter)]:
        image.unlink()
    progress.remove(name, chapter)
    pm.store_progress(progress=progress)


def images_in_dir(directory: Path) -> list[Path]:
    """Returns the paths of all images at the specified location

    Args:
        directory (Path): directory to search

    Returns:
        list[Path]: found paths
    """
    return files_in_dir(directory, [".png", ".jpeg", ".jpg"])


def files_in_dir(directory: Path, extensions: list[str] | None = None) -> list[Path]:
    """Get a list of files directly contained in a directory

    Args:
        directory: directory root to search
        extensions: extensions (with leading dot, i.e. '.txt') to include. Use 'None' to obtain all files

    Returns: list of paths of the found files

    """
    res: list[Path] = []
    path = Path(directory).resolve()
    for element in path.iterdir():
        if element.is_file() and (not extensions or element.suffix in extensions):
            res.append(element)
    return res


def partition_improved_images(
    images: list[Path],
) -> dict[tuple[str, int], list[Path]]:
    """Partition images by series name and chapter

    Args:
        images (list[Path]): image paths to consider

    Returns:
        dict[tuple[str, int], list[Path]]: dict that maps (name, chapter) to the corresponding list of file paths
    """
    batch_to_images = defaultdict(list)
    for image in images:
        base_name = image.name
        res = data_from_image_file_name(base_name)
        if not res:
            print("could not match name of image", image)
            continue
        name, chapter, *_ = res
        batch_to_images[(name, chapter)].append(image)
    return batch_to_images


def data_from_image_file_name(file_name: str) -> tuple[str, int, str] | None:
    m = IMPROVED_PATTERN.match(file_name)
    if not m:
        return None
    name, chapter, ext = m.groups()
    chapter = int(chapter)
    return name, chapter, ext
