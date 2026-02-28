import logging
import sys
from pathlib import Path

from threading import Lock

import platformdirs

APPLICATION_NAME = "image_scraper"
APPLICATION_AUTHOR = "TF"


lock = Lock()


def get_logger(name: str, docker: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    with lock:
        logger.setLevel(logging.DEBUG)

        # the logger may have been initialized already
        # only add handlers if the logger has none
        if not logger.handlers:
            ch = logging.StreamHandler(sys.stdout)

            if docker:
                ch.setLevel(logging.DEBUG)
            else:
                ch.setLevel(logging.INFO)

                log_file = log_file_location(docker)
                print(f"log file loc: {log_file}")
                if log_file is not None:
                    fh = logging.FileHandler(log_file)

                    fh.setLevel(logging.DEBUG)
                    formatter = logging.Formatter(
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    )
                    fh.setFormatter(formatter)
                    logger.addHandler(fh)
            logger.addHandler(ch)

    return logger


def log_file_location(docker: bool) -> Path | None:
    if docker:
        return None
    log_dir = platformdirs.user_log_path(
        appname=APPLICATION_NAME, appauthor=APPLICATION_AUTHOR
    )
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{APPLICATION_NAME}.log"
