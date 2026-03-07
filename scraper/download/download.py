import itertools
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Protocol

import platformdirs
import requests
import typer
from rich.progress import Progress

from scraper.download.download_progress import DownloadType, RangesProgress
from scraper.download.image_collector import ImageResult, collect_images_single
from scraper.download.progress_manager import (
    DynRangesProgUpdate,
    RangesProgressManager,
)
from scraper.download.text_collector import TextResult, scrape_text
from scraper.img.batch_images import batch_improved_images
from scraper.util.dynamic_ranges import Ranges
from scraper.util.logging_config import get_logger

app = typer.Typer()


@dataclass
class ChapterTarget:
    name: str
    url: str
    base_url: str
    chapter: int
    target_dir: Path
    download_type: DownloadType


@dataclass
class DownloadTarget:
    name: str
    url: str
    start: int
    end: int
    target_dir: Path
    download_type: DownloadType = DownloadType.images

    def count(self) -> int:
        return self.end - self.start + 1

    def short_description(self) -> str:
        range_str = f"{self.start}-{self.end}"
        if self.start == self.end:
            range_str = str(self.start)
        return f"{self.name} {range_str} ({self.download_type})"

    def __download_dir(self) -> Path:
        if self.download_type is DownloadType.text:
            return self.target_dir
        else:
            return self.target_dir / "downloaded_images"

    def to_chapter_targets(self) -> list[ChapterTarget]:
        return [
            ChapterTarget(
                self.name,
                self.url.replace("Here", str(chapter)),
                self.url,
                chapter,
                self.__download_dir(),
                self.download_type,
            )
            for chapter in range(self.start, self.end + 1)
        ]


@app.command(
    help=(
        "Downloads images from a range of URLs and"
        " arranges them in a single png file for each URL."
    )
)
def download(
    url: str,
    name: str,
    password: Annotated[
        str,
        typer.Option(
            prompt=True,
            confirmation_prompt=False,
            hide_input=True,
        ),
    ],
    start: int = 1,
    end: int = 1,
    out_directory_prefix: Annotated[
        Path,
        typer.Argument(
            help=(
                "Prefix used to place the files in."
                "Images are placed as <out_directory_prefix>/<name>/downloaded"
                " images (single images) and out_directory_prefix/name/name for"
                " the batched images."
            )
        ),
    ] = platformdirs.user_data_path("scraper", "TF"),
    batches: bool = False,
    dltype: DownloadType = DownloadType.images,
):
    """Downloads images from a range of URLs and arranges them in a single png file for
    each URL.

    Args:
        url (str): URL template from which the URLs may be generated. You may use the
            string 'HERE' to specify a single point in the URL that is replaced by each
            of the numbers in [start, end]. If 'HERE' is not used in the URL the URL is
            used once as provided
        name (str): used to identify the images downloaded by each call
        start (int, optional): Start of the range used to replace HERE in the URL.
            Defaults to 1.
        end (int, optional): End (inclusive) of the range used to replace HERE in the
            URL. Defaults to 1.
        out_directory_prefix (str, optional): Prefix used to place the files in. Images
            are placed as out_directory_prefix/name/downloaded images (single images)
            and out_directory_prefix/name/name for the batched images..
        batches (bool, optional): specify whether the images belonging to each chapter
            should also be combined into a single file. Defaults to False.
    """
    if start < end and "HERE" not in url:
        print(f"ERROR: Range is {start}-{end}, but the url does not contain 'HERE'!")
        return

    target = DownloadTarget(
        name=name,
        url=url,
        start=start,
        end=end,
        target_dir=Path(out_directory_prefix, name),
        download_type=dltype,
    )
    progress_manager = RangesProgressManager(password=password)
    # also to check that the pw is correct
    progress = progress_manager.load_progress()
    if name in progress.progress_by_name:
        confirm = typer.confirm(
            (
                f"There is a progress item with the name {name}."
                " The information could be overwritten."
                " If this is the same item consider using the 'next' command instead."
                " Should I continue?"
            )
        )
        if not confirm:
            sys.exit(0)
    targets = target.to_chapter_targets()
    download_targets(
        targets=targets, progress_manager=progress_manager, batches=batches
    )


@app.command(help="Show available updates")
def show_updates(name: str | None = None):
    progress_manager = RangesProgressManager()
    progress = progress_manager.load_progress()
    if not progress:
        print("No progress found.")
        sys.exit(1)
    if name:
        if name in progress.progress_by_name:
            prog = progress.progress_by_name[name]
            __check_for_updates(name, prog)

        else:
            print("No item with this name.")
    else:
        for it_name, data in progress.progress_by_name.items():
            if data.stopped:
                print(f"Skipping {it_name}: stopped")
                continue
            __check_for_updates(it_name, data)


@app.command("update", help="Download updates")
def dl_updates(name: str | None = None, batches: bool = False, limit: int = 6):
    progress_manager = RangesProgressManager()
    progress = progress_manager.load_progress()
    logger = get_logger("dl_updates")

    if not progress:
        logger.info("No progress found.")
        sys.exit(1)
    targets: list[ChapterTarget] = []
    if name:
        if name in progress.progress_by_name:
            prog = progress.progress_by_name[name]
            chapter_targets = __get_new_chapter_updates_for_prog(
                prog, max_new_count=limit
            )
            if chapter_targets:
                targets += chapter_targets

        else:
            logger.info(f"No item with the name {name}.")
    else:
        with Progress(transient=True) as progress_bar:
            task = progress_bar.add_task("")
            for it_name, data in progress.progress_by_name.items():
                if data.stopped:
                    logger.debug(f"Skipping {it_name}")
                else:
                    progress_bar.update(task, description=f"Checking {it_name}")
                    chapter_targets = __get_new_chapter_updates_for_prog(
                        data, max_new_count=limit
                    )

                    if chapter_targets:
                        chapter_ranges = Ranges(ranges=[])
                        for ct in chapter_targets:
                            _ = chapter_ranges.add(ct.chapter)

                        progress_bar.print(f"found target {it_name} {chapter_ranges}")
                        logger.debug(f"found target {it_name} {chapter_ranges}")
                        targets += chapter_targets
                progress_bar.advance(task)

    if targets:
        logger.info("beginning downloads")
        download_targets(targets, progress_manager, batches=batches)
    else:
        logger.info("No updates found!")


def __get_updates(name: str, prog: RangesProgress, max_new_count: int = 100000000):
    logger = get_logger("__get_updates")

    if prog.dl_locations:
        target_dir = prog.base_dir()
    else:
        target_dir = platformdirs.user_data_path("scraper", "TF", name)

    url = prog.urls[-1]
    if "HERE" not in url:
        logger.error(f"No template url for '{name}' ({url})!")
        return
    count = __last_new_chapter(prog, max_new_count=max_new_count)
    if count > prog.end:
        return DownloadTarget(
            name,
            url,
            prog.end + 1,
            count,
            target_dir,
            download_type=prog.download_type,
        )
    else:
        return None


@app.command(help="Download the up to 'n' next chapters for 'name'")
def next(name: str, n: int, num_threads: int = 6):
    progress_manager = RangesProgressManager()
    progress = progress_manager.load_progress()
    if name not in progress.progress_by_name:
        print(f"No progress for name {name}!")
        return
    prog = progress.progress_by_name[name]

    target = __get_updates(name, prog, max_new_count=n)
    if target is None:
        print("no updates found")
        return
    targets = __get_new_chapter_updates_for_prog(prog, max_new_count=n)
    download_targets(
        targets, progress_manager=progress_manager, num_threads=num_threads
    )


def __last_new_chapter(prog: RangesProgress, max_new_count: int = 10000000) -> int:
    base_url = prog.urls[-1]
    count = prog.end

    next_url = base_url.replace("HERE", str(count + 1))
    while __url_is_valid(next_url) and count - prog.end < max_new_count:
        count += 1
        next_url = base_url.replace("HERE", str(count + 1))
    return count


def __get_new_chapter_updates_for_prog(
    prog: RangesProgress, max_new_count: int = 10000000
) -> list[ChapterTarget]:
    res: list[ChapterTarget] = []
    template_urls = [url for url in prog.urls if "HERE" in url]
    if not template_urls:
        print(f"No template url for {prog.name} available!")
        return []
    base_url = template_urls[-1]
    chapter = prog.end
    target_dir = prog.base_dir()
    if prog.download_type is DownloadType.images:
        target_dir = target_dir / "downloaded_images"

    next_url = base_url.replace("HERE", str(chapter + 1))
    while __url_is_valid(next_url) and chapter < prog.end + max_new_count:
        chapter += 1
        res.append(
            ChapterTarget(
                prog.name,
                url=next_url,
                base_url=base_url,
                chapter=chapter,
                target_dir=target_dir,
                download_type=prog.download_type,
            )
        )
        next_url = base_url.replace("HERE", str(chapter + 1))
    return res


def __url_is_valid(url: str) -> bool:
    logger = get_logger("__last_new_chapter")
    logger.debug(f"Checking {url}")
    invalid_phrases = (
        "This chapter is premium!",
        "Premium Chapter",
        (
            "Sorry for the inconvenience."
            " We&rsquo;re performing some maintenance at the moment."
            " If you need to you can always follow us on "
        ),
        "is required to read this chapter",
    )
    if "blank" in url:
        # blank does not seem to work atm
        return False
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200 or resp.url != url:
            return False
        text = resp.text
        if text.startswith('<!DOCTYPE html><html id="__next_error__">') or any(
            ip in text for ip in invalid_phrases
        ):
            return False
    except requests.exceptions.Timeout:
        print("Timeout")
        return False

    return True


def download_targets(
    targets: list[ChapterTarget],
    progress_manager: RangesProgressManager,
    batches: bool = False,
    num_threads: int = 6,
):
    """Download the files for the specified targets.
    Also updates the progress file and urls.json file.
    Images belonging to the same chapter are merged if batches=True.

    Args:
        targets (list[DownloadTarget]): list of targets
        progress_manager (RangesProgressManager): progress manager
        batches (bool, optional): _description_. Defaults to False.
    """

    downloaded_images: list[ImageResult] = []
    dr_prog_upd = DynRangesProgUpdate(progress_manager=progress_manager)
    successful_downloads: dict[str, Ranges] = defaultdict(Ranges.new)
    if len(targets) == 1:
        target = targets[0]
        target.target_dir.mkdir(parents=True, exist_ok=True)

        print(f"Collecting images for {target.name} {target.chapter}")
        if target.download_type is DownloadType.images:
            image_result = collect_images_single(
                target.name, target.chapter, target.url, target.target_dir
            )
            if len(image_result.image_locations) > 1:
                downloaded_images = [image_result]
                _ = successful_downloads[target.name].add(target.chapter)

                dr_prog_upd.add_completion(
                    name=target.name,
                    chapter=target.chapter,
                    url=target.base_url,
                    dl_location=target.target_dir,
                    dl_type=target.download_type,
                )
            else:
                print(
                    (
                        f"Only got {len(image_result.image_locations)} images for"
                        f" {target.name} {target.chapter}. Not logging as downloaded."
                    )
                )
        elif target.download_type is DownloadType.text:
            _ = scrape_text(
                name=target.name,
                chapter=target.chapter,
                url=target.url,
                dl_location=target.target_dir,
            )
            downloaded_images = []
            dr_prog_upd.add_completion(
                name=target.name,
                chapter=target.chapter,
                url=target.base_url,
                dl_location=target.target_dir,
                dl_type=target.download_type,
            )
            _ = successful_downloads[target.name].add(target.chapter)

    else:
        fut_results: list[Future[ImageResult | TextResult]] = []

        class DataScraper(Protocol):
            def __call__(  # noqa: E704
                self,
                name: str,
                chapter: int,
                url: str,
                dl_location: Path,
                skip_download: bool,
                /,
            ) -> ImageResult | TextResult: ...

        with ThreadPoolExecutor(num_threads) as executor:
            for target in targets:
                out_directory = target.target_dir
                out_directory.mkdir(exist_ok=True)

                scraping_function: DataScraper = collect_images_single
                if target.download_type is DownloadType.text:
                    scraping_function = scrape_text
                future_res: Future[ImageResult | TextResult] = executor.submit(
                    scraping_function,
                    target.name,
                    target.chapter,
                    target.url,
                    target.target_dir,
                    False,
                )
                fut_results.append(future_res)

            with Progress(transient=True) as progress:
                # updates text in progress bar
                def running_info() -> str:
                    running_parts: list[str] = []
                    for index, fut in enumerate(fut_results):
                        if fut.running():
                            running_parts.append(
                                f"{targets[index].name} {targets[index].chapter}"
                            )
                    return " " + ", ".join(running_parts)

                def finished_info(finished_count: int):
                    return f"finished {finished_count}/{len(fut_results)}"

                finished_count = 0
                task = progress.add_task(
                    f"Currently downloading... ({finished_info(finished_count)})",
                    total=len(fut_results),
                )

                def update_text(last_finished: str):
                    progress.update(
                        task,
                        description=(
                            f"Downloading{running_info()}..."
                            f" ({finished_info(finished_count)}){last_finished}"
                        ),
                    )

                time.sleep(3)
                update_text("")

                for fut in as_completed(fut_results):
                    progress.advance(task)
                    finished_count += 1
                    res = fut.result()
                    valid_completion = True
                    match res:
                        case ImageResult(name, chapter, image_locations, _):
                            dl_type: DownloadType = DownloadType.images
                            downloaded_images.append(res)
                            if len(image_locations) <= 1:
                                valid_completion = False
                                print(
                                    (
                                        f"Only found the following images: "
                                        f"{image_locations} for {name} {chapter},"
                                        " not logging as downloaded."
                                    )
                                )
                        case TextResult(name, chapter):
                            dl_type = DownloadType.text
                    if valid_completion:
                        _ = successful_downloads[name].add(chapter)
                        # figure out base_url
                        t = [
                            t
                            for t in targets
                            if t.name == name and t.chapter == chapter
                        ]
                        dr_prog_upd.add_completion(
                            name=name,
                            dl_location=res.out_directory,
                            chapter=chapter,
                            url=t[0].base_url,
                            dl_type=dl_type,
                        )
                    last_finished = f"; Last finished: {name} {chapter}"
                    update_text(last_finished=last_finished)
                    time.sleep(5)
                    update_text(last_finished=last_finished)

    if batches:
        current_dir = os.getcwd()
        image_paths: dict[str, list[Path]] = defaultdict(list)
        for im_res in downloaded_images:
            image_paths[im_res.name] += im_res.image_locations
        for name, paths in image_paths.items():
            out_directory = Path(current_dir, name, name)
            os.makedirs(out_directory, exist_ok=True)
            batch_improved_images(paths, out_directory)

    for name, ranges in successful_downloads.items():
        print(f"Downloaded {name} {ranges}")


@app.command(help="Fill gaps in downloaded chapters")
def fill_gaps(
    name: str | None = None,
    fill_start: bool = False,
    batches: bool = False,
    num_threads: int = 6,
):
    pm = RangesProgressManager()
    progress = pm.load_progress()

    def targets_for_name(name: str) -> list[DownloadTarget]:
        """
        Compute 'DownloadTarget's that represent the gaps
        in the downloaded chapters for 'name'
        """
        prog = progress.progress_by_name[name]
        res: list[DownloadTarget] = []
        target_dir = prog.base_dir()
        print(prog.ranges)
        if fill_start and 1 < prog.ranges.ranges[0].start:
            res.append(
                DownloadTarget(
                    name,
                    prog.urls[-1],
                    start=1,
                    end=prog.ranges.ranges[0].start - 1,
                    target_dir=target_dir,
                    download_type=prog.download_type,
                )
            )
        for r0, r1 in itertools.pairwise(prog.ranges.ranges):
            if r0.end + 1 < r1.start:
                res.append(
                    DownloadTarget(
                        name,
                        prog.urls[-1],
                        start=r0.end + 1,
                        end=r1.start - 1,
                        target_dir=target_dir,
                        download_type=prog.download_type,
                    )
                )
        return res

    targets: list[ChapterTarget] = []

    def extend_targets(name: str):
        nonlocal targets
        targets += [
            chapter_target
            for t in targets_for_name(name)
            for chapter_target in t.to_chapter_targets()
        ]

    if name:
        extend_targets(name)
    else:
        for name in progress.progress_by_name:
            extend_targets(name)
    download_targets(
        targets=targets,
        progress_manager=pm,
        batches=batches,
        num_threads=num_threads,
    )


def __check_for_updates(name: str, prog: RangesProgress):
    upd = __get_updates(name, prog)
    if upd is None:
        print(f"{name}: No new chapters available from {prog.urls[-1]}")
    else:
        print(
            (
                f"{name}: available until {upd.end} "
                f"(downloaded until {prog.end}) from {upd.url}"
            )
        )


@app.command(help="Print a summary table of all downloaded chapters")
def summary() -> None:
    pm = RangesProgressManager()
    progress = pm.load_progress()
    # name, ranges, stopped, copy
    summary_info: list[tuple[str, str, str, str]] = []
    summary_lengths: tuple[int, int, int, int] = (4, 6, 7, 5)
    for name, p in progress.progress_by_name.items():
        ranges_string = str(p.ranges)
        stopped = str(p.stopped)
        copy = str(p.do_copy)
        max_name_len = max(summary_lengths[0], len(name))
        max_ranges_len = max(summary_lengths[1], len(ranges_string))
        summary_lengths = (max_name_len, max_ranges_len, 7, 5)
        summary_info.append((name, ranges_string, stopped, copy))

    print(summary_lengths)
    line_width = sum(summary_lengths) + 4 * 2 + 5
    inner_hor_line = (
        f"├─{'─' * summary_lengths[0]}"
        f"─┼─{'─' * summary_lengths[1]}"
        f"─┼─{'─' * summary_lengths[2]}"
        f"─┼─{'─' * summary_lengths[3]}─┤"
    )

    lines = [
        f"┌{'─' * (line_width - 2)}┐",
        (
            f"│ {'name'.ljust(summary_lengths[0])} "
            f"│ {'ranges'.ljust(summary_lengths[1])}"
            " │ stopped │ copy  │"
        ),
    ]
    summary_info.sort(key=lambda i: i[0])
    for name, ranges, stopped, copy in summary_info:
        lines.append(inner_hor_line)
        lines.append(
            (
                f"│ {name.ljust(summary_lengths[0])} "
                f"│ {ranges.ljust(summary_lengths[1])} "
                f"│ {stopped.ljust(summary_lengths[2])} "
                f"│ {copy.ljust(summary_lengths[3])} │"
            )
        )
    lines.append(
        (
            f"└─{'─' * summary_lengths[0]}"
            f"─┴─{'─' * summary_lengths[1]}"
            f"─┴─{'─' * summary_lengths[2]}"
            f"─┴─{'─' * summary_lengths[3]}─┘"
        )
    )
    print("\n".join(lines))


@app.command(help="Show downloaded items overview")
def show_dl(name: str | None = None, prog_loc: str | None = None):
    progress_manager = RangesProgressManager(prog_loc)
    progress = progress_manager.load_progress()
    if not progress:
        print("No progress found.")
        sys.exit(1)
    if name:
        if name in progress.progress_by_name:
            prog = progress.progress_by_name[name]
            print(f"{name}: {str(prog.ranges)} from {prog.urls}")
        else:
            print("No item with this name.")
    else:
        for name, prog in progress.progress_by_name.items():
            print(f"{name}: {str(prog.ranges)} from {prog.urls}")


@app.command(
    help=(
        "Stop new chapters for 'name' from being "
        "included in default download lists (e.g. in 'update' calls)"
    )
)
def stop(name: str):
    pm = RangesProgressManager()
    p = pm.load_progress()
    for item in p.progress_by_name.values():
        if item.name == name:
            if not item.stopped:
                item.stopped = True
                pm.store_progress(p)
            return


@app.command(
    help=(
        "Allow new chapters for 'name' to be included"
        " in default download lists (e.g. in 'update' calls)"
    )
)
def unstop(name: str):
    pm = RangesProgressManager()
    p = pm.load_progress()
    for item in p.progress_by_name.values():
        if item.name == name:
            if item.stopped:
                item.stopped = False
                pm.store_progress(p)
            return
