"""Stage 1 -- generate and inject SteamTools manifests / lua.

SteamTools loads an ``app_<AppID>.lua`` unlock script plus the binary
``.manifest`` files for each depot. The lua we can synthesize from the spec
(depot ids, decryption keys and manifest gids); the ``.manifest`` blobs come
from Steam and cannot be conjured, so they are copied from a source directory
supplied by the user when present.

The unlock script uses SteamTools' documented primitives::

    addappid(<appid>)
    addappid(<depotid>, 1, "<hex key>")
    setManifestid(<depotid>, "<manifest gid>", 0)
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import List, Optional

from ..errors import ValidationError
from ..logutil import get_logger
from ..models import GameSpec

log = get_logger()


def build_lua(spec: GameSpec) -> str:
    lines: List[str] = [f"addappid({spec.appid})"]
    for depot in spec.depots:
        if depot.key:
            lines.append(f'addappid({depot.depot_id}, 1, "{depot.key}")')
        else:
            lines.append(f"addappid({depot.depot_id})")
        if depot.manifest_id:
            lines.append(f'setManifestid({depot.depot_id}, "{depot.manifest_id}", 0)')
    return "\n".join(lines) + "\n"


def _manifest_targets(steamtools_dir: Path) -> List[Path]:
    """Where SteamTools expects ``.manifest`` files (version dependent)."""
    targets = [steamtools_dir]
    sub = steamtools_dir / "manifests"
    if sub.is_dir():
        targets.insert(0, sub)
    return targets


def inject_manifests(
    spec: GameSpec,
    steamtools_dir: Path,
    *,
    manifest_source: Optional[Path] = None,
    dry_run: bool = False,
) -> List[Path]:
    """Write the lua and copy any provided ``.manifest`` files into the prefix.

    Returns the list of files that were written, and asserts they exist.
    """
    if not steamtools_dir.is_dir():
        raise ValidationError(
            f"SteamTools config dir not found: {steamtools_dir}\n"
            "Is SteamTools installed into this PortProton prefix?"
        )

    written: List[Path] = []
    lua_path = steamtools_dir / f"app_{spec.appid}.lua"
    lua_text = build_lua(spec)
    log.info("stage1: writing %s", lua_path.name)
    if not dry_run:
        lua_path.write_text(lua_text, encoding="utf-8")
    written.append(lua_path)

    if manifest_source:
        manifests = sorted(Path(manifest_source).glob("*.manifest"))
        if not manifests:
            log.warning("stage1: no .manifest files in %s", manifest_source)
        target_dir = _manifest_targets(steamtools_dir)[0]
        for man in manifests:
            dest = target_dir / man.name
            log.info("stage1: copying manifest %s", man.name)
            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(man, dest)
                _assert_same(man, dest)
            written.append(dest)
    else:
        log.info(
            "stage1: no manifest_source given; relying on manifests already "
            "present in the prefix (or SteamTools fetching them on demand)"
        )

    if not dry_run:
        for path in written:
            if not path.exists():
                raise ValidationError(f"stage1 assertion failed: missing {path}")
    return written


def _assert_same(src: Path, dst: Path) -> None:
    if _sha256(src) != _sha256(dst):
        raise ValidationError(f"checksum mismatch after copy: {dst}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
