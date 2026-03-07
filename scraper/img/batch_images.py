import os
import re
import sys
from pathlib import Path

import cv2
from cv2.typing import MatLike
from PIL import Image

from scraper.files.util import partition_improved_images
from scraper.img.montage import Montage

IMPROVED_PATTERN = re.compile(r"(.*)_(\d+)_\d+\.(jpeg|jpg|png|svg)")


def batch_all_images(
    images: list[Path],
    name: str,
    out_directory: Path,
    threshold: int = 200,
):
    simple_names, improved_names = group_images(images)
    batch_images(simple_names, out_directory, threshold, name=name)

    batch_improved_images(improved_names, out_directory)


def batch_improved_images(images: list[Path], out_directory: Path):
    images.sort()
    batch_to_images = partition_improved_images(images=images)
    for (name, chapter), images in batch_to_images.items():
        print(f"{name}: Batch {chapter}")
        output_file = os.path.join(out_directory, f"{name}_{chapter:04}.png")
        store_images_as_batch(images, output_file)


def batch_images(
    images: list[Path],
    out_directory: Path | None,
    threshold: int = 200,
    name: str = "",
):
    if not out_directory:
        out_directory = Path.cwd()
    if not images:
        return
    images.sort(key=lambda name: str(name).zfill(10))
    base_images = [os.path.basename(im) for im in images]

    min_number = int(os.path.splitext(base_images[0])[0])
    batch_count = min_number // 200 + 1
    pos = 0

    output_path = os.path.join(out_directory, "batched_images")
    os.makedirs(output_path, exist_ok=True)
    prefix = f"{name + '_' if name else ''}b"

    while pos < len(images):
        batch = []
        while (
            pos < len(images)
            and int(os.path.splitext(base_images[pos])[0]) < batch_count * threshold
        ):
            batch.append(images[pos])
            pos += 1

        output_file = os.path.join(output_path, f"{prefix}{batch_count:04}.png")
        store_images_as_batch(batch, output_file)
        batch_count += 1


def store_images_as_batch(images: list[Path], output_file: str):
    first_image = cv2.imread(str(images[0]), cv2.COLOR_BGR2RGB)
    if first_image is None:
        print(f"Failed to obtain image for {images[0]}!")
        return
    montage = Montage(first_image)
    remaining_images = [
        cv2.imread(str(image), cv2.COLOR_BGR2RGB) for image in images[1:]
    ]
    remaining_images_success: list[MatLike] = [
        image for image in remaining_images if image is not None
    ]
    try:
        montage.multi_append(remaining_images_success)
    except ValueError as e:
        print(e)
        sys.exit(1)
    im = Image.fromarray(cv2.cvtColor(montage.montage, cv2.COLOR_RGB2BGR))
    im.save(output_file)


def group_images(images: list[Path]) -> tuple[list[Path], list[Path]]:
    simple_names: list[Path] = []
    improved_names: list[Path] = []

    simple_re = re.compile(r"\d+\.(jpg|png)")

    for image in images:
        base_name = image.name
        if IMPROVED_PATTERN.match(base_name):
            improved_names.append(image)
        elif simple_re.match(base_name):
            simple_names.append(image)
    return simple_names, improved_names
