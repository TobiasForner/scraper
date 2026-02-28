from pathlib import Path


class ImageNames:
    def __init__(self, name: str, chapter: int, directory: Path) -> None:
        self.pos: int = 1
        self.name: str = name
        self.chapter: int = chapter
        self.directory: Path = directory

    def current(self, extension: str) -> Path:
        base_name = f"{self.name}_{self.chapter:04}_{self.pos:05}{extension}"
        return Path(self.directory, base_name)

    def next(self, extension: str) -> Path:
        res = self.current(extension=extension)
        self.pos += 1
        return res
