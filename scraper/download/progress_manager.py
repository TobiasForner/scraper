import io
import sys
from logging import Logger
from pathlib import Path

import platformdirs
import pyAesCrypt
import typer

from scraper.download.download_progress import AllProgress, DownloadType
from scraper.util.logging_config import get_logger

PROGRESS_FILE_ENCRYPTED = "download_progress.json.aes"
RANGES_PROGRESS_FILE_ENCRYPTED = "ranges_download_progress.json.aes"
BUFFER_SIZE = 64 * 1024


class RangesProgressManager:
    def __init__(
        self,
        progress_file_location: str | None = None,
        password: str | None = None,
    ) -> None:
        app_data_path = platformdirs.user_data_path("scraper", "TF")
        app_data_path.mkdir(parents=True, exist_ok=True)
        if progress_file_location is None:
            self.progress_file_location: Path = (
                app_data_path / RANGES_PROGRESS_FILE_ENCRYPTED
            )
        else:
            self.progress_file_location = Path(progress_file_location)

        self.urls_file_location: Path = app_data_path / "urls.json"
        if password:
            self.password: str = password
        else:
            self.password: str = typer.prompt(
                (
                    "Please enter the encryption password "
                    f"for {self.progress_file_location}"
                ),
                hide_input=True,
                confirmation_prompt=False,
            )

    def load_progress(self) -> AllProgress:
        if self.progress_file_location.exists():
            with open(self.progress_file_location, "rb") as progress_file:
                fDec = io.BytesIO()
                try:
                    pyAesCrypt.decryptStream(
                        progress_file, fDec, self.password, BUFFER_SIZE
                    )
                except ValueError as e:
                    print(f"Could not load progress file: {e}")
                    sys.exit(1)

                plain_text = fDec.getvalue().decode("ascii")

                progress = AllProgress.model_validate_json(plain_text)
                return progress
        else:
            return AllProgress(progress_by_name={})

    def store_progress(self, progress: AllProgress):
        progress_str = progress.model_dump_json()
        fIn = io.BytesIO(progress_str.encode("ascii"))
        with open(self.progress_file_location, "wb") as progress_file:
            pyAesCrypt.encryptStream(fIn, progress_file, self.password, BUFFER_SIZE)


class DynRangesProgUpdate:
    def __init__(self, progress_manager: RangesProgressManager) -> None:
        self.pm: RangesProgressManager = progress_manager
        self.logger: Logger = get_logger("DynRangesProgUpdate")

    def add_completion(
        self,
        name: str,
        dl_location: Path,
        chapter: int,
        url: str,
        dl_type: DownloadType,
    ):
        progress = self.pm.load_progress()
        res = progress.add(
            name=name,
            url=url,
            dl_location=dl_location,
            chapter=chapter,
            dl_type=dl_type,
        )
        if res:
            self.logger.debug(
                (
                    "DynRangesProgUpdate: "
                    f"Updating progress after completion of {name} {chapter}"
                )
            )
            self.pm.store_progress(progress=progress)
        else:
            self.logger.debug(
                (
                    "DynRangesProgUpdate: "
                    f"NOT updating progress after completion of {name} {chapter}"
                )
            )
