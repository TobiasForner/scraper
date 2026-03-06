import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import typer
from ppadb.client import Client as AdbClient
from ppadb.device import Device
from rich.progress import track

from scraper.download.download_progress import DownloadType
from scraper.download.progress_manager import RangesProgressManager
from scraper.files.util import images_in_dir, partition_improved_images
from scraper.img.image_tools import find_blocked_chapters, image_split
from scraper.util.dynamic_ranges import Ranges

IMAGE_DIR = "/storage/emulated/0/Pictures"


app = typer.Typer()


@app.command(name="rem-chapter", help="Remove a chapter from your ADB device")
def adb_remove_chapter(name: str, chapter: int):
    pm = RangesProgressManager()
    remove_chapter_files_adb(name, chapter, pm)


@app.command(
    help="Disable copying to your ADB device for one series based on 'name'"
)
def no_copy(name: str):
    __set_copy(name, False)


@app.command(
    help="Enable copying to your ADB device for one series based on 'name'"
)
def do_copy(name: str):
    __set_copy(name, True)


def __set_copy(name: str, do_copy: bool):
    pm = RangesProgressManager()
    p = pm.load_progress()
    if name in p.progress_by_name:
        prog_item = p.progress_by_name[name]
        prog_item.do_copy = do_copy
        pm.store_progress(p)
    else:
        print(f"There is no progress item with the name {name}!")


@app.command(name="copy", help="Copy files from PC to your phone via ADB")
def adb_copy(
    names: list[str] = typer.Argument([]),
    all: bool = False,
    ask_for_each: bool = False,
):
    pm = RangesProgressManager()
    progress = pm.load_progress()
    if all:
        if names:
            print(
                "Error, option 'all' is used, but names were also specified:",
                names,
            )
            return

        names = [
            name
            for name, progress in progress.progress_by_name.items()
            if progress.download_type is DownloadType.images
            and progress.do_copy
        ]
        if ask_for_each:
            ask_for_each = not typer.confirm(
                "Would you like to copy all images or get asked for each name?"
            )
    if not names:
        print("No names provided:", names)
        return
    device = get_device()
    for name in names:
        name_prog = progress.progress_by_name[name]
        if not name_prog.dl_locations:
            print(f"No download location registered for {name}. Skipping")
            continue
        loc = name_prog.base_dir()
        while loc.name == name:
            loc = Path(loc, "..").resolve()
        loc = Path(loc, name)
        push_diff(
            name, source_dir=loc, device=device, confirmed=not ask_for_each
        )
        ensure_nomedia_file_for_name(name, device=device)


@app.command(
    help="Delete files belonging to chapters whose download has been blocked by the source website from your ADB device"
)
def adb_del_blocked_chapters(name: str):
    pm = RangesProgressManager()
    blocked_chapters = find_blocked_chapters(name=name, pm=pm)
    chapter_numbers = [num for _, num in blocked_chapters]
    print(f"Removing {name} {chapter_numbers} from ADB device")
    remove_multi_chapter_files_adb(name, chapters=chapter_numbers, pm=pm)


@app.command("print-diff")
def print_local_file_ranges_not_on_device(name: str, verbose: bool = False):
    def print_local_file_ranges_not_on_device_single(
        name: str, base_dir: Path, verbose: bool = False
    ):
        ranges = local_file_ranges_not_on_device(
            name, base_dir, get_device(), verbose=verbose
        )
        if not ranges:
            print(f"No new items for {name}")
        for name, rs in ranges.items():
            print(f"{name}: {str(rs)}")

    pm = RangesProgressManager()
    progress = pm.load_progress().progress_by_name
    base_dir = Path(".").resolve()
    if name == "all":
        names = progress.keys()
        for name in names:
            base_dir = progress[name].base_dir()
            print_local_file_ranges_not_on_device_single(
                name, base_dir, verbose
            )
    else:
        base_dir = progress[name].base_dir()
        print_local_file_ranges_not_on_device_single(name, base_dir, verbose)


@app.command(
    help="Ensures that all series directories on your ADB device contain a .nomedia file"
)
def ensure_nomedia():
    ensure_nomedia_file()


def files_on_device(name: str, device: Device) -> list[str]:
    res = __shell_on_device(
        device=device, cmd=f"find {IMAGE_DIR}/{name} -type f"
    )
    if res is None:
        print(
            f"Failed to find files in directory {IMAGE_DIR}/{name} on device!"
        )
        sys.exit(1)
    res_lines = res.split("\n")
    return res_lines


def remove_files_from_device(files: list[str], device: Device):
    for file in files:
        print(f"Removing {file}")
        _ = __shell_on_device(device=device, cmd=f"rm {file}")


def remove_chapter_files_adb(
    name: str, chapter: int, pm: RangesProgressManager
):
    remove_multi_chapter_files_adb(name=name, chapters=[chapter], pm=pm)


def remove_multi_chapter_files_adb(
    name: str, chapters: list[int], pm: RangesProgressManager
):
    progress = pm.load_progress().progress_by_name[name]
    local_images_dir = progress.base_dir() / "downloaded_images"
    local_files = images_in_dir(local_images_dir)
    part = partition_improved_images(local_files)
    to_remove: list[str] = []
    for chapter in chapters:
        local_chapter_files = part[(name, chapter)]
        to_remove += [
            str(p.relative_to(local_images_dir)) for p in local_chapter_files
        ]

    device = get_device()
    images = files_on_device(name, device)
    filtered_images = [
        image for image in images if image.split("/")[-1] in to_remove
    ]
    filtered_images.sort()
    remove_files_from_device(filtered_images, device=device)


def local_files_not_on_device(
    name: str, base_dir: Path, device: Device
) -> list[Path]:
    """List of file paths corresponding to images not on the device

    Args:
        name (str): name to be considered
        base_dir (Path): base dir ending in name
        device (Device): device do consider

    Returns:
        list[Path]: list of image paths
    """
    local_images_dir = base_dir / "downloaded_images"
    local_files = images_in_dir(local_images_dir)
    on_device = [
        f.replace(f"{IMAGE_DIR}/{name}/", "")
        for f in files_on_device(name, device)
    ]

    diff = [
        f
        for f in local_files
        if str(f.relative_to(local_images_dir)) not in on_device
    ]
    return diff


def ensure_nomedia_file_for_name(name: str, device: Device):
    on_device = [
        f.replace(f"{IMAGE_DIR}/{name}/", "")
        for f in files_on_device(name, device)
    ]
    if ".nomedia" not in on_device:
        print(f".nomedia file missing for {name}")
        _ = __shell_on_device(
            device=device, cmd=f"touch {IMAGE_DIR}/{name}/.nomedia"
        )
        print(f"Created .nomedia file for {name}")
        print(f"Renaming {name} and reverting name change...")
        real_name_dir = f"{IMAGE_DIR}/{name}"
        mod_name_dir = f"{IMAGE_DIR}/{name}_old"
        _ = __shell_on_device(
            device=device, cmd=f"mv {real_name_dir} {mod_name_dir}"
        )
        time.sleep(2)
        _ = __shell_on_device(
            device=device, cmd=f"mv {mod_name_dir} {real_name_dir}"
        )


def ensure_nomedia_file():
    device = get_device()
    pm = RangesProgressManager()
    progress = pm.load_progress()
    for name in progress.progress_by_name:
        ensure_nomedia_file_for_name(name, device)


def local_file_ranges_not_on_device(
    name: str, base_dir: Path, device: Device, verbose: bool
) -> dict[str, Ranges]:
    diff = local_files_not_on_device(name, base_dir, device)
    chapters: dict[str, list[int]] = defaultdict(list)
    for im in diff:
        split = image_split(im)
        if split is None:
            if verbose:
                print("Error: Could not split", im)
            continue
        name, chapter, _ = split
        chapters[name].append(chapter)
    res: dict[str, Ranges] = {}
    for name, cs in chapters.items():
        ranges = Ranges(ranges=[])

        for c in cs:
            _ = ranges.add(c)
        res[name] = ranges
    return res


def get_device() -> Device:
    def get_device_from_client(client: AdbClient) -> Device:
        devices: list[Device] = (
            client.devices()
        )  # pyright:ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not devices:
            devices = (
                client.devices()
            )  # pyright:ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not devices:
            print("No devices found!")
            sys.exit(1)
        device = devices[0]
        return device

    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        return get_device_from_client(client)
    except RuntimeError:
        print("Starting ADB server...")
        _ = subprocess.run(["adb", "start-server"], shell=True)
        client = AdbClient(host="127.0.0.1", port=5037)
        return get_device_from_client(client)


def push_diff(
    name: str, source_dir: Path, device: Device, confirmed: bool = False
):
    diff = local_files_not_on_device(name, source_dir, device=device)
    if not diff:
        print("No new items for", name, source_dir, source_dir)
        return

    src_dir = Path(source_dir, "downloaded_images")
    dst_dir = f"{IMAGE_DIR}/{name}"
    if confirmed:
        do_copy = True
    else:
        print("\t\n".join([str(image) for image in diff]))

        do_copy = typer.confirm(f"Do you want to copy the files to {dst_dir}?")

    if not do_copy:
        return

    for f in track(diff, f"Copying {name} files"):
        src = src_dir / f
        if src.is_dir():
            continue
        try:
            device.push(str(src.absolute()), f"{dst_dir}/{f.name}")
        except RuntimeError as re:
            print(
                f"Could not push {src.absolute()} to {dst_dir}/{f.name}: {re}"
            )


def names_on_device(device: Device):
    res: str | None = __shell_on_device(device, f"find {IMAGE_DIR} -type d")
    if res is None:
        print(f"Failed to find directories in {IMAGE_DIR} on device!")
        sys.exit(1)
    res_lines: list[str] = res.split("\n")
    rel_res: list[str] = [f.replace(f"{IMAGE_DIR}/", "") for f in res_lines]
    rel_res = [f for f in rel_res if "/" not in f]
    rel_res = [
        f
        for f in rel_res
        if f
        not in (
            ".thumbnails",
            "Screenshots",
            "Office Lens",
            "FairEmail",
            "Whatsapp",
            "",
        )
    ]
    print(rel_res)


def __shell_on_device(device: Device, cmd: str) -> str | None:
    res = device.shell(
        cmd=cmd
    )  # pyright:ignore[reportUnknownMemberType, reportUnknownVariableType]
    if res is None or isinstance(res, str):
        return res
    raise TypeError("Unexpected type from shell call")


if __name__ == "__main__":
    app()
