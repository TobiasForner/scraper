from scraper.download.progress_manager import RangesProgressManager
from scraper.files.util import files_in_dir, images_in_dir
from collections import defaultdict
import subprocess
from pathlib import Path


def cbz_chapter_images(name: str, chapter: int, pm: RangesProgressManager):
    progress = pm.load_progress()
    progress_by_name = progress.progress_by_name
    if name in progress_by_name:
        progress = progress_by_name[name]
        loc = progress.base_dir()
        images = images_in_dir(loc)
        # group into chapters
        by_chapter: dict[int, list[Path]] = defaultdict(list)
        for image in images:
            parts = image.name.split("_")
            chap = int(parts[-2])
            by_chapter[chap].append(image)
        if chapter in by_chapter:
            images = by_chapter[chapter]
            dest = loc.joinpath("archives", f"{name}_{chapter:04}.7z")
            com = ["7z", "a", str(dest), *[str(i).replace("\\\\", "/") for i in images]]
            _ = subprocess.call(com)
            __convert_to_cbz(name, chapter, pm)
        else:
            print(f"Did not find {name} chapter {chapter}. Skipped.")


def cbz_remaining(name: str, pm: RangesProgressManager):
    """Convert all chapters for 'name' to cbz files for which no cbz file is present"""
    progress = pm.load_progress()
    progress_by_name = progress.progress_by_name
    if name in progress_by_name:
        progress = progress_by_name[name]
        cbz_dir = progress.base_dir() / "cbz"

        cbz_chapters = [
            int(f.stem.split("_")[-1]) for f in files_in_dir(cbz_dir, [".cbz"])
        ]
        all_chapters = set(progress.chapters())
        to_convert = [c for c in all_chapters if c not in cbz_chapters]
        for chapter in to_convert:
            print(f"Converting chapter {chapter}")
            cbz_chapter_images(name, chapter, pm)


def __convert_to_cbz(name: str, chapter: int, pm: RangesProgressManager):
    progress = pm.load_progress()
    progress_by_name = progress.progress_by_name
    if name in progress_by_name:
        progress = progress_by_name[name]
        loc = progress.base_dir()
        archive_file = loc.joinpath("archives", f"{name}_{chapter:04}.7z")
        dest = loc.joinpath("cbz")
        com = [
            "KCC_c2e_9.0.0.exe",
            "-u",
            "-o",
            str(dest),
            "-f",
            "CBZ",
            "--customwidth 1404",
            "--customheight 1872",
            str(archive_file),
        ]
        _ = subprocess.call(com)
