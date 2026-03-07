from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from scraper.util.dynamic_ranges import Ranges


class DownloadType(str, Enum):
    images = "images"
    text = "text"


class RangesProgress(BaseModel):
    name: str
    urls: list[str]
    dl_locations: list[Path]
    ranges: Ranges
    stopped: bool = Field(default=False)
    do_copy: bool = Field(default=True)
    download_type: DownloadType = Field(default=DownloadType.images)

    def add(self, url: str, dl_location: Path, chapter: int) -> bool:
        """Adds a downloaded chapter, merges ranges afterwards

        Args:
            url (str): url used for the chapter download
            dl_location (Path): base location for the downloaded files.
            Ends with name, not with downloaded_images
            chapter (int): chapter number

        Returns:
            bool: True if the chapter was added, False if it was aleady present
        """
        if url not in self.urls:
            self.urls.append(url)
        if dl_location not in self.dl_locations:
            self.dl_locations.append(dl_location)
        else:
            # move dl_location to the back
            pos = self.dl_locations.index(dl_location)
            self.dl_locations = (
                self.dl_locations[:pos] + self.dl_locations[pos + 1 :] + [dl_location]
            )
        return self.ranges.add(chapter)

    def remove(self, chapter: int):
        _ = self.ranges.remove(chapter)

    def has_base_dir(self) -> bool:
        return bool(self.dl_locations)

    def base_dir(self) -> Path:
        """Last local download location, ending in the series name

        Returns:
            Path: path to the lats download location
        """
        res = self.dl_locations[-1]
        while res.name == "downloaded_images":
            res = res.parent
        return res

    @property
    def end(self):
        return self.ranges.end

    def chapters(self):
        for chapter in self.ranges.chapters():
            yield chapter

    @staticmethod
    def new(name: str, dl_type: DownloadType):
        return RangesProgress(
            name=name,
            urls=[],
            dl_locations=[],
            ranges=Ranges(ranges=[]),
            download_type=dl_type,
        )


class AllProgress(BaseModel):
    progress_by_name: dict[str, RangesProgress]

    def add(
        self,
        name: str,
        url: str,
        dl_location: Path,
        chapter: int,
        dl_type: DownloadType,
    ):
        if name in self.progress_by_name:
            prog = self.progress_by_name[name]

            if prog.download_type is not dl_type:
                print(
                    (
                        f"ERROR: new download type {dl_type} does not match"
                        f" the existing one {prog.download_type}"
                    )
                )
                return
            return prog.add(url, dl_location, chapter)
        else:
            p = RangesProgress.new(name, dl_type)
            _ = p.add(url, dl_location, chapter)
            self.progress_by_name[name] = p
            return True

    def remove(self, name: str, chapter: int):
        self.progress_by_name[name].remove(chapter)
