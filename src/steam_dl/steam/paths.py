"""Filesystem layout discovery for native Steam and PortProton.

Nothing here mutates state; every function is a pure path computation or a
read-only probe so the caller can validate the environment before the pipeline
touches anything.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

HOME = Path(os.path.expanduser("~"))

# Native Linux Steam (Flatpak and classic layouts are both checked).
_NATIVE_STEAM_ROOTS = [
    HOME / ".local/share/Steam",
    HOME / ".steam/steam",
    HOME / ".var/app/com.valvesoftware.Steam/data/Steam",
]

PORTPROTON_APP_ID = "ru.linux_gaming.PortProton"
_PORTPROTON_DATA = HOME / ".var/app" / PORTPROTON_APP_ID / "data/PortProton"


def native_steam_root() -> Optional[Path]:
    """Return the first native Steam install that actually exists."""
    for root in _NATIVE_STEAM_ROOTS:
        if (root / "config").is_dir() or (root / "steamapps").is_dir():
            return root
    return None


def userdata_dirs(steam_root: Path) -> List[Path]:
    base = steam_root / "userdata"
    if not base.is_dir():
        return []
    return [p for p in base.iterdir() if p.is_dir() and p.name.isdigit() and p.name != "0"]


def detect_user_id(steam_root: Path, explicit: Optional[str] = None) -> Optional[str]:
    """Pick the Steam3 account id under ``userdata/``.

    If more than one exists we prefer the most recently modified, which is
    almost always the profile the user is currently signed into.
    """
    if explicit:
        return explicit
    dirs = userdata_dirs(steam_root)
    if not dirs:
        return None
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return dirs[0].name


def shortcuts_vdf_path(steam_root: Path, user_id: str) -> Path:
    return steam_root / "userdata" / user_id / "config" / "shortcuts.vdf"


def config_vdf_path(steam_root: Path) -> Path:
    return steam_root / "config" / "config.vdf"


@dataclass
class PortProtonLayout:
    prefix_name: str
    prefix_root: Path            # .../prefixes/<name>
    drive_c: Path
    steam_dir: Path              # drive_c/Program Files (x86)/Steam
    steamtools_dir: Path         # .../Steam/config/st
    steamapps: Path              # .../Steam/steamapps
    common: Path                 # .../steamapps/common

    def appmanifest(self, appid: int) -> Path:
        return self.steamapps / f"appmanifest_{appid}.acf"


def portproton_layout(prefix_name: str, data_root: Optional[Path] = None) -> PortProtonLayout:
    root = (data_root or _PORTPROTON_DATA) / "prefixes" / prefix_name
    drive_c = root / "drive_c"
    steam_dir = drive_c / "Program Files (x86)" / "Steam"
    steamapps = steam_dir / "steamapps"
    return PortProtonLayout(
        prefix_name=prefix_name,
        prefix_root=root,
        drive_c=drive_c,
        steam_dir=steam_dir,
        steamtools_dir=steam_dir / "config" / "st",
        steamapps=steamapps,
        common=steamapps / "common",
    )
