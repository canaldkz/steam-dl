"""Launcher abstraction for stage 5.

A *launcher* registers the installed game so it can be started. The default is
native Steam (Game Mode), but Steam-less options (Lutris, PortProton, or a
plain script) let the game run under Proton/Wine with no Steam client, no
account and no online presence -- the Goldberg emulator satisfies the
Steamworks API entirely offline.
"""

from __future__ import annotations

import abc
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from ..config import Config
from ..logutil import get_logger

log = get_logger()

def _launcher_dir() -> Path:
    return Path.home() / ".local/share/steam-dl/launchers"


def _desktop_dir() -> Path:
    return Path.home() / ".local/share/applications"


@dataclass
class LaunchResult:
    kind: str
    files: List[Path] = field(default_factory=list)
    note: str = ""


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return slug or "game"


def _quote(path: str) -> str:
    return '"' + str(path).replace('"', '\\"') + '"'


class Launcher(abc.ABC):
    kind = "base"

    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abc.abstractmethod
    def register(self, name: str, exe: Path, game_dir: Path) -> LaunchResult:
        ...

    # -- shared helpers for the file-based launchers --
    def _write_script(self, name: str, body: str) -> Path:
        path = _launcher_dir() / f"{slugify(name)}.sh"
        log.info("stage5: writing launch script %s", path)
        if not self.cfg.dry_run:
            _launcher_dir().mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
        return path

    def _write_desktop(self, name: str, exec_path: Path, workdir: Path) -> Path:
        path = _desktop_dir() / f"steam-dl-{slugify(name)}.desktop"
        content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={name}\n"
            f"Exec={_quote(exec_path)}\n"
            f"Path={workdir}\n"
            "Categories=Game;\n"
            "Terminal=false\n"
        )
        log.info("stage5: writing desktop entry %s", path)
        if not self.cfg.dry_run:
            _desktop_dir().mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return path
