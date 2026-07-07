"""Download backend interface.

A backend owns stages 1-3: it makes Steam (or an equivalent) fetch the depots
and returns the on-disk directory of the fully installed game. Stages 4-5
(relocation, DRM bypass, native integration) are backend-independent.
"""

from __future__ import annotations

import abc
from pathlib import Path

from ..config import Config
from ..models import GameSpec


class Backend(abc.ABC):
    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abc.abstractmethod
    def preflight(self) -> None:
        """Validate that this backend can run; raise on any missing piece."""

    @abc.abstractmethod
    def download(self, spec: GameSpec) -> Path:
        """Perform stages 1-3 and return the installed game directory."""
