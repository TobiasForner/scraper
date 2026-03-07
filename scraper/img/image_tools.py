from pathlib import Path

import cv2
import numpy as np
import platformdirs
from cv2.typing import MatLike

from scraper.download.progress_manager import RangesProgressManager
from scraper.files.util import (
    data_from_image_file_name,
    images_in_dir,
    partition_improved_images,
)

SPLIT_THRESHOLD = 15000


def image_split(image: str | Path) -> tuple[str, int, str] | None:
    if isinstance(image, Path):
        image_s = image.name
    else:
        image_s = image
    return data_from_image_file_name(image_s)


def images_above_threshold(directory: Path) -> list[Path]:
    ims = images_in_dir(directory)
    res: list[Path] = []
    for im in ims:
        im = im.resolve()
        lim = cv2.imread(str(im))
        if lim is None:
            continue
        if should_split(lim):
            res.append(im)
    return res


def should_split(image: np.ndarray) -> bool:
    height = image.shape[0]
    return height >= SPLIT_THRESHOLD


def split_image(image_location: str, out_loc_1: str, out_loc_2: str):
    image = cv2.imread(image_location)
    if image is None:
        return
    h, _, _ = image.shape
    new_height = h // 2

    first = image[:new_height, :]
    second = image[new_height:, :]
    _ = cv2.imwrite(out_loc_1, first)
    _ = cv2.imwrite(out_loc_2, second)


def split_loaded_image(image: np.ndarray, out_loc_1: Path, out_loc_2: Path):
    h = image.shape[0]
    new_height = h // 2

    first = image[:new_height, :]
    second = image[new_height:, :]
    cv2.imwrite(str(out_loc_1), first)
    cv2.imwrite(str(out_loc_2), second)


def names_in(dir: Path) -> list[str]:
    progress_manager = RangesProgressManager()
    progress = progress_manager.load_progress()
    res: list[str] = []
    for name, p in progress.progress_by_name.items():
        if any([Path(loc).is_relative_to(dir) for loc in p.dl_locations]):
            res.append(name)
    return res


def trim_black_border(image_path: Path):
    image = cv2.imread(str(image_path))
    if image is None:
        return
    height, _, _ = image.shape
    pos = 0

    def is_black_line(line: int, image: MatLike) -> bool:
        arr = image[line] == 14
        res = arr.all(1).all()
        return res

    # trim top
    while pos < height and is_black_line(pos, image):
        pos += 1
    image = image[pos:]

    # trim bottom
    height, _, _ = image.shape
    pos = height - 1
    while pos > 0 and is_black_line(pos, image):
        pos -= 1
    image = image[:pos]

    height, width, _ = image.shape

    def is_black_col(col: int, image: MatLike) -> bool:
        arr = image[:, col] == 14
        res: bool = arr.all(1).all()

        return res

    # trim left
    pos = 0
    while pos < width and is_black_col(pos, image):
        pos += 1
    image = image[:, pos:]

    # trim right
    height, width, _ = image.shape
    pos = width - 1
    while pos > 0 and is_black_col(pos, image):
        pos -= 1
    image = image[:, :pos]
    _ = cv2.imwrite(str(image_path), image)


def is_blocked(image_path: Path) -> bool:
    blocked_image_root = platformdirs.user_data_path("scraper", "TF") / "blocked_images"
    blocked_image_root.mkdir(exist_ok=True)
    blocked_images = images_in_dir(blocked_image_root)
    if not blocked_images:
        return False
    test_image = cv2.imread(str(image_path))
    if not test_image:
        return False
    test_image_cut = test_image[:500]
    for blocked_image_path in blocked_images:
        blocked_image_cut = cv2.imread(str(blocked_image_path))
        if blocked_image_cut is None:
            continue
        if (
            blocked_image_cut.shape == test_image_cut.shape
            and (blocked_image_cut == test_image_cut).all()
        ):
            return True
    return False


def find_blocked_chapters(
    name: str, pm: RangesProgressManager
) -> list[tuple[str, int]]:
    res = []
    progress = pm.load_progress()
    if name in progress.progress_by_name:
        prog = progress.progress_by_name[name]
        images = images_in_dir(prog.base_dir() / "downloaded_images")
        image_partition = partition_improved_images(images)
        for (name, chapter), chapter_paths in image_partition.items():
            chapter_paths.sort()
            if any(is_blocked(chapter_path) for chapter_path in chapter_paths):
                res.append((name, chapter))
    return res
