"""Download backends."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import Config
from .base import Backend
from .depotdownloader import DepotDownloaderBackend
from .portproton import PortProtonBackend


def make_backend(cfg: Config, manifest_source: Optional[Path] = None) -> Backend:
    if cfg.backend == "portproton":
        return PortProtonBackend(cfg, manifest_source=manifest_source)
    if cfg.backend == "depotdownloader":
        return DepotDownloaderBackend(cfg)
    raise ValueError(f"unknown backend: {cfg.backend!r}")


__all__ = ["Backend", "PortProtonBackend", "DepotDownloaderBackend", "make_backend"]
