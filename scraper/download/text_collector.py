from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass
class TextResult:
    name: str
    chapter: int
    out_directory: Path


def scrape_text(name: str, chapter: int, url: str, dl_location: Path):
    res = requests.get(url)
    dl_location.mkdir(parents=True, exist_ok=True)
    with open(Path(dl_location, f"{name}_{chapter}.txt"), "w", encoding="utf-8") as f:
        _ = f.write(res.text)
    return TextResult(name, chapter, out_directory=dl_location)
