"""Small logging helpers shared across stages."""

from __future__ import annotations

import logging
import sys

_LOGGER_NAME = "steam_dl"


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def setup_logging(verbose: bool = False) -> logging.Logger:
    logger = get_logger()
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger
