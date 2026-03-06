import os
import sys
from pathlib import Path

import cv2
import typer
from rich.progress import track

from scraper.download.image_names import ImageNames
from scraper.files.util import partition_improved_images
from scraper.img.batch_images import (
    batch_all_images,
)
from scraper.img.image_tools import (
    images_above_threshold,
    images_in_dir,
    should_split,
    split_loaded_image,
)

app = typer.Typer()


@app.command()
def batch(
    directory: str,
    out_directory: str = ".",
    threshold: int = 200,
    name: str = "",
):
    dir = Path(directory).resolve()
    images = images_in_dir(dir)
    if not images:
        print("No image files could be found in the directory", directory)
        sys.exit(1)
    batch_all_images(
        images, name=name, out_directory=out_directory, threshold=threshold
    )


@app.command()
def fix_im_colors(directory: str):
    dir = Path(directory).resolve()
    images = images_in_dir(dir)
    for image in track(images, "Recoloring images..."):
        path = str(image)
        try:
            img = cv2.imread(path)
            if img is None:
                continue
            cv2.imwrite(path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        except Exception as e:
            print(f"Could not change {path}: {e}")


@app.command()
def rescale_images(directory: str, width: int = 720):
    dir = Path(directory).resolve()
    images = images_in_dir(dir)
    # print("\n".join(images))
    for image in track(images, "Rescaling images..."):
        file_path = str(image)
        im = cv2.imread(file_path, cv2.COLOR_BGR2RGB)
        if im is None:
            continue
        y, x = im.shape[0:2]
        new_x = min(x, width)
        new_y = int(y * float(new_x) / x)
        new_image = cv2.resize(im, (new_x, new_y))
        cv2.imwrite(file_path, new_image)
        print(file_path)


@app.command()
def list_split_images(directory: str):
    res = images_above_threshold(Path(directory).resolve())
    print("\n".join(str(im) for im in res))


@app.command()
def split_images(directory: str):
    dir = Path(directory).resolve()
    res = images_above_threshold(dir)
    batch_to_images = partition_improved_images(res)
    for (name, chapter), images in batch_to_images.items():
        # load all images
        images = [(image, cv2.imread(str(image))) for image in images]
        image_names = ImageNames(name, chapter, directory=dir)
        for path, image in images:
            if image is None:
                continue
            extension = os.path.splitext(path)[1]
            if should_split(image):
                name1 = image_names.next(extension=extension)
                name2 = image_names.next(extension=extension)
                split_loaded_image(
                    image=image, out_loc_1=name1, out_loc_2=name2
                )
            else:
                cv2.imwrite(str(image_names.next(extension=extension)), image)


@app.command()
def imdet(file: str):
    image = cv2.imread(file)
    if image is None:
        print("Failed to load image!")
        return
    size = os.path.getsize(file) / (1024 * 1024)
    print(f"{file}: {size:.1f}MB, {image.shape}")
