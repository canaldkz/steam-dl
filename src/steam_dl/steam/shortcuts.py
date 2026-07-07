"""Add non-Steam game entries to ``shortcuts.vdf``.

The caller is responsible for making sure Steam is **not** running: the client
keeps ``shortcuts.vdf`` cached in memory and rewrites it on exit, silently
discarding any edit made while it is alive.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..vdf import binary_dumps, binary_loads
from .appid import shortcut_appid, shortcut_appid_signed


@dataclass
class Shortcut:
    app_name: str
    exe: str                       # stored verbatim, quotes included
    start_dir: str
    launch_options: str = ""
    icon: str = ""
    tags: List[str] = field(default_factory=list)
    is_hidden: int = 0
    allow_desktop_config: int = 1
    allow_overlay: int = 1

    def appid(self) -> int:
        return shortcut_appid(self.exe, self.app_name)

    def to_entry(self) -> Dict[str, object]:
        return {
            "appid": shortcut_appid_signed(self.exe, self.app_name),
            "AppName": self.app_name,
            "Exe": self.exe,
            "StartDir": self.start_dir,
            "icon": self.icon,
            "ShortcutPath": "",
            "LaunchOptions": self.launch_options,
            "IsHidden": self.is_hidden,
            "AllowDesktopConfig": self.allow_desktop_config,
            "AllowOverlay": self.allow_overlay,
            "OpenVR": 0,
            "Devkit": 0,
            "DevkitGameID": "",
            "DevkitOverrideAppID": 0,
            "LastPlayTime": int(time.time()),
            "FlatpakAppID": "",
            "tags": {str(i): t for i, t in enumerate(self.tags)},
        }


def _quote_exe(path: str) -> str:
    path = path.strip()
    if path.startswith('"') and path.endswith('"'):
        return path
    return f'"{path}"'


def load_shortcuts(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {"shortcuts": {}}
    data = binary_loads(path.read_bytes())
    data.setdefault("shortcuts", {})
    return data


def _find_index(entries: Dict[str, object], exe: str, app_name: str) -> Optional[str]:
    for idx, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("Exe") == exe and entry.get("AppName") == app_name:
            return idx
    return None


def add_shortcut(path: Path, shortcut: Shortcut, *, replace: bool = True) -> int:
    """Insert (or update) ``shortcut`` and write the file back.

    Returns the 32-bit app id of the shortcut. The ``Exe`` is normalized to be
    quote-wrapped before the app id is computed, matching Steam's own hashing.
    """
    shortcut.exe = _quote_exe(shortcut.exe)
    data = load_shortcuts(path)
    entries = data["shortcuts"]
    if not isinstance(entries, dict):
        entries = {}
        data["shortcuts"] = entries

    existing = _find_index(entries, shortcut.exe, shortcut.app_name)
    if existing is not None:
        if not replace:
            return shortcut.appid()
        index = existing
    else:
        used = {int(k) for k in entries.keys() if str(k).isdigit()}
        index = str(next(i for i in range(len(used) + 1) if i not in used))

    entries[index] = shortcut.to_entry()

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(binary_dumps(data))
    tmp.replace(path)
    return shortcut.appid()
