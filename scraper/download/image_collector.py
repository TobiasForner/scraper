import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

import cv2
import requests
from attr import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium_stealth import stealth

from scraper.download.image_names import ImageNames
from scraper.img.image_tools import (
    SPLIT_THRESHOLD,
    split_loaded_image,
    trim_black_border,
)
from scraper.util.logging_config import get_logger


@dataclass
class ImageResult:
    name: str
    chapter: int
    image_locations: list[Path]
    found_urls: list[str]
    out_directory: Path


class ImageCollector:
    def __init__(
        self,
        out_directory: Path,
        name: str,
        batch_number: int = 1,
        skip_download: bool = False,
    ) -> None:
        self.out_directory: Path = out_directory
        self.batch_number: int = batch_number
        self.name: str = name
        self.skip_download: bool = skip_download
        options = Options()
        self.__logger = get_logger("ImageCollector")
        options.add_argument("--headless")
        # additional arguments and use of stealth found at
        # https://stackoverflow.com/questions/68289474/selenium-headless-how-to-bypass-cloudflare-detection-using-selenium # noqa: E501
        options.add_argument("start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        options.binary_location = "C:\\chromedriver\\chrome.exe"
        options.add_argument("user-agent=Chrome/110.0.3029.110")
        # used to hide console output from chrome
        # see https://stackoverflow.com/questions/53372520/python-how-to-hide-output-chrome-messages-in-selenium # noqa: E501
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        service = ChromeService(executable_path="C:\\chromedriver\\chromedriver.exe")
        self.browser = webdriver.Chrome(options=options, service=service)
        self.downloaded: list[Path] = []
        self.found_image_urls: list[str] = []
        stealth(
            driver=self.browser,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )

    def close(self):
        self.browser.close()

    def scroll_to(self, x: int, y: int):
        self.browser.execute_script(f"window.scrollTo({x}, {y});")

    def collect_images(self, url: str):
        self.__logger.debug(f"start {url}")
        self.browser.get(url)
        time.sleep(5)

        self.browser.maximize_window()
        height = self.browser.execute_script("return document.body.scrollHeight")
        max_step = int(height)
        window_size = self.browser.get_window_size()
        step = window_size["height"] // 10
        window_width = window_size["width"]
        time.sleep(2)

        width = self.browser.execute_script("return document.body.scrollWidth")

        current = 0
        while current < max_step:
            next_s = min(max_step, current + step)

            self.scroll_to(width // 2 - window_width // 2, next_s)

            if max_step - next_s <= 3 * step:
                time.sleep(5)

            time.sleep(0.2)
            height = self.browser.execute_script("return document.body.scrollHeight")
            max_step = int(height)
            current = next_s
        self.download_images()
        self.__logger.debug(f"end {url}")

    def download_images(self):
        self.__logger.debug("start locate elements")
        images = self.browser.find_elements(By.CSS_SELECTOR, "p > img")
        images2 = self.browser.find_elements(By.CSS_SELECTOR, "div > img")
        images3 = self.browser.find_elements(By.CSS_SELECTOR, "a > img")
        self.__logger.debug(
            (
                f"selected elements: {[im.get_property('src') for im in images]}; "
                f"{[im.get_property('src') for im in images2]}"
            )
        )
        if len(images2) > len(images):
            images = images2
        if len(images3) > len(images):
            images = images3

        image_names = ImageNames(self.name, self.batch_number, self.out_directory)

        im_sources: list[str] = []
        for im in images:
            self.__logger.debug(im.text)
            src = str(im.get_property("src"))
            if "?resize" in src:
                src = src.split("?resize")[0]
            if src.endswith("readerarea.svg"):
                continue
            im_sources.append(src)

        for src in im_sources:
            self.__store_image(src, image_names=image_names)
        self.__logger.debug("downloaded elements")

    def __store_image(self, url: str, image_names: ImageNames):
        extension = os.path.splitext(url)[1]
        if not extension:
            self.__logger.debug(f"Skipping {url}; extension: {extension}")
            return
        if extension not in (".jpg", ".png", ".jpeg", ".svg"):
            self.__logger.debug(f"unsupported extension {extension} of {url}")
            return

        if self.skip_download:
            self.found_image_urls.append(url)
        else:
            self.found_image_urls.append(url)
            res = requests.get(url, stream=True)

            file_name = image_names.next(extension=extension)
            self.__logger.debug(f"{url}; extension: {extension}, {file_name}")

            if res.status_code == 200:
                with open(file_name, "wb") as f:
                    self.__logger.debug(f"saving {file_name}")
                    shutil.copyfileobj(res.raw, f)
                # check whether file is too large
                image = cv2.imread(str(file_name))
                if image is None:
                    self.__logger.info(f"Could not load downloaded file {file_name}")
                    return
                height = image.shape[0]
                if height >= SPLIT_THRESHOLD:
                    file_name2 = image_names.next(extension)
                    self.__logger.debug(
                        (
                            f"Splitting image {file_name} into"
                            f" {file_name} and {file_name2}."
                        )
                    )
                    split_loaded_image(image, file_name, file_name2)
                else:
                    self.downloaded.append(file_name)

            else:
                print(f"Image Couldn't be retrieved from {url}: {res.status_code}")
                print("Attempting Screenshot")
                file_name = image_names.next(extension=".png")
                self.found_image_urls.append(url)
                self.browser.get(url)
                time.sleep(5)
                self.browser.save_screenshot(file_name)
                time.sleep(0.1)
                trim_black_border(file_name)


@contextmanager
def image_collector(
    batch_number: int,
    out_directory: Path,
    name: str,
    skip_download: bool = False,
):
    mc = ImageCollector(
        out_directory,
        name=name,
        batch_number=batch_number,
        skip_download=skip_download,
    )
    try:
        yield mc
    finally:
        try:
            mc.close()
        except Exception as e:
            print("Something went wrong when trying to close Chrome:")
            print(e)


def collect_images_single(
    name: str,
    batch_number: int,
    url: str,
    out_directory: Path,
    skip_download: bool = False,
) -> ImageResult:
    with image_collector(
        batch_number, out_directory, name=name, skip_download=skip_download
    ) as collector:
        collector.collect_images(url)
        images = collector.downloaded
        found_urls = collector.found_image_urls
        return ImageResult(
            name=name,
            chapter=batch_number,
            image_locations=images,
            found_urls=found_urls,
            out_directory=out_directory,
        )
