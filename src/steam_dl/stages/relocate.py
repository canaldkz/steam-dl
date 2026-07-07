"""Stage 4 -- move the game out of the prefix and apply the Goldberg bypass.

After the download, the game sits inside the PortProton prefix's
``steamapps/common``. We relocate it to ``~/Games`` (native filesystem), then
walk it depth-first replacing every ``steam_api(64).dll`` with the Goldberg
emulator build and dropping a ``steam_appid.txt`` alongside each one.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import List, Optional

from ..errors import ValidationError
from ..logutil import get_logger

log = get_logger()

_STEAM_API_DLLS = ("steam_api64.dll", "steam_api.dll")


def relocate(src: Path, dest: Path, *, dry_run: bool = False) -> Path:
    """Move ``src`` -> ``dest``. Falls back to copy+delete across filesystems."""
    if dry_run:
        log.info("stage4: (dry-run) would relocate %s -> %s", src, dest)
        return dest
    if not src.is_dir():
        raise ValidationError(f"stage4: source game dir missing: {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        log.warning("stage4: destination exists, removing: %s", dest)
        shutil.rmtree(dest)

    log.info("stage4: relocating %s -> %s", src, dest)
    try:
        os.rename(src, dest)
    except OSError:
        # Different filesystems: copy then remove the original.
        shutil.copytree(src, dest)
        shutil.rmtree(src)
    if not dest.is_dir():
        raise ValidationError(f"stage4 assertion failed: {dest} not created")
    return dest


def find_steam_api_dlls(root: Path) -> List[Path]:
    found: List[Path] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.lower() in _STEAM_API_DLLS:
                found.append(Path(dirpath) / name)
    return found


def apply_goldberg(
    game_dir: Path,
    appid: int,
    goldberg_dir: Optional[Path],
    *,
    dry_run: bool = False,
) -> List[Path]:
    """Overwrite steam_api DLLs with Goldberg and write ``steam_appid.txt``.

    Every directory that contained an original DLL gets a ``steam_appid.txt``
    even when no Goldberg template is configured, since some games need only
    that file. Returns the list of patched DLL paths.
    """
    dlls = find_steam_api_dlls(game_dir)
    if not dlls:
        log.warning("stage4: no steam_api DLLs found under %s", game_dir)

    if goldberg_dir is not None and not Path(goldberg_dir).is_dir():
        raise ValidationError(f"stage4: goldberg template dir missing: {goldberg_dir}")

    patched: List[Path] = []
    seen_dirs = set()
    for dll in dlls:
        appid_txt = dll.parent / "steam_appid.txt"
        if dll.parent not in seen_dirs:
            log.info("stage4: writing %s", appid_txt)
            if not dry_run:
                appid_txt.write_text(f"{appid}\n", encoding="utf-8")
            seen_dirs.add(dll.parent)

        if goldberg_dir is None:
            continue
        template = Path(goldberg_dir) / dll.name
        if not template.exists():
            log.warning("stage4: no Goldberg build for %s, skipping overwrite", dll.name)
            continue
        log.info("stage4: patching %s", dll)
        if not dry_run:
            backup = dll.with_suffix(dll.suffix + ".orig")
            if not backup.exists():
                shutil.copy2(dll, backup)
            shutil.copy2(template, dll)
        patched.append(dll)
    return patched
