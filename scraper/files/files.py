import json
import os
import shutil
from pathlib import Path

import typer
from rich.progress import track

from scraper.adb.adb import remove_chapter_files_adb
from scraper.download.progress_manager import RangesProgressManager
from scraper.files import empty_chapters
from scraper.files.util import images_in_dir, remove_chapter
from scraper.img.batch_images import group_images
from scraper.img.image_tools import find_blocked_chapters

app = typer.Typer()


@app.command(help="Copy local files to another root directory")
def copy_files(target_directory: str, verbose: bool = False):
    progress_manager = RangesProgressManager()
    progress = progress_manager.load_progress()

    copy_progress_loc = Path(target_directory, "copy_progress.json")

    copy_progress = {}
    if copy_progress_loc.exists():
        with open(copy_progress_loc) as copy_prog_file:
            copy_progress = json.load(copy_prog_file)
    copied_to = copy_progress.get("copied_to", [])

    for prog in progress.progress_by_name.values():
        downloaded_images: list[Path] = []
        for loc in prog.dl_locations:
            p = loc / "downloaded_images"
            downloaded_images += images_in_dir(p)
        target_for_name = Path(
            target_directory, prog.name, "downloaded_images"
        ).resolve()
        target_for_name.mkdir(parents=True, exist_ok=True)
        _, improved_images = group_images(
            [p.resolve() for p in downloaded_images]
        )
        for p in improved_images:
            p = Path(p)
            target_image = Path(target_for_name, p.name)
            if not target_image.exists() and target_image not in copied_to:
                if verbose:
                    print("Copying", p, "to", target_image)
                shutil.copyfile(p, target_image)
                copied_to.append(str(target_image))

    copy_progress["copied_to"] = copied_to
    with open(copy_progress_loc, "w") as copy_prog_file:
        json.dump(copy_progress, copy_prog_file)


@app.command(help="Move local files to another directory")
def move_files(source_dir: Path, target_dir: Path):
    source_dir = source_dir.resolve()
    pm = RangesProgressManager()
    progress = pm.load_progress()
    for p in track(progress.progress_by_name.values(), "Copying files..."):
        to_remove: list[Path] = []
        for loc in p.dl_locations:
            if not loc.exists():
                to_remove.append(loc)
                continue
            if loc.is_relative_to(source_dir):
                rel = loc.relative_to(source_dir)
                new_loc = Path(target_dir, rel).resolve()
                shutil.copytree(loc, new_loc, dirs_exist_ok=True)
                if new_loc not in p.dl_locations:
                    p.dl_locations.append(new_loc)
        p.dl_locations = [loc for loc in p.dl_locations if loc not in to_remove]
    pm.store_progress(progress)


@app.command(
    help="Helper command to ensure that stored download directories follow the current convention"
)
def normalize_dl_dirs():
    pm = RangesProgressManager()
    progress = pm.load_progress()
    for p in progress.progress_by_name.values():
        while p.dl_locations and p.dl_locations[-1].name == "downloaded_images":
            print(f"{p.dl_locations[-1]} -> {p.dl_locations[-1].parent}")
            p.dl_locations[-1] = p.dl_locations[-1].parent
        new_dl_locations = [
            dl for dl in p.dl_locations if dl.is_absolute() and dl.exists()
        ]
        p.dl_locations = new_dl_locations

    pm.store_progress(progress)


@app.command(
    help="Shows a list of chapters of a series (specified by 'name') where the download has been blocked."
)
def list_blocked_chapters(name: str):
    pm = RangesProgressManager()
    blocked_chapters = find_blocked_chapters(name=name, pm=pm)
    print("\n".join(str(p) for p in blocked_chapters))


@app.command(
    help="Deletes all local chapters of a series (specified by 'name') whose the download has been blocked. Successfully downloaded chapters are not affected"
)
def del_blocked_chapters(name: str):
    pm = RangesProgressManager()
    blocked_chapters = find_blocked_chapters(name=name, pm=pm)
    for name, chapter in blocked_chapters:
        print(f"Removing {name} {chapter} from storage")
        remove_chapter(name, chapter, pm=pm)


@app.command(
    help="Delete a specified chapter of a series (specified by 'name')"
)
def remove_local_chapter(name: str, chapter: int):
    print(f"{chapter:04d}")
    pm = RangesProgressManager()
    remove_chapter(name, chapter, pm)


@app.command(
    help="Delete all local and adb chapters of a series (specified by 'name') whose the download has been blocked. Successfully downloaded chapters are not affected"
)
@app.command()
def full_del_blocked_chapters(name: str):
    pm = RangesProgressManager()
    blocked_chapters = find_blocked_chapters(name=name, pm=pm)
    for name, chapter in blocked_chapters:
        print(f"Removing {name} {chapter}")
        remove_chapter_files_adb(name, chapter, pm)
        remove_chapter(name, chapter, pm=pm)


app.command(
    help="List all empty chapters of a series (emptiness is determined if less than 'threshold') files have been downloaded",
)(empty_chapters.list_empty_chapters)
app.command(
    help="Delete all empty chapters of a series (emptiness is determined if less than 'threshold') files have been downloaded",
)(empty_chapters.remove_empty_chapters)
