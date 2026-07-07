"""Ingest a ready-made SteamTools bundle (folder or ``.zip``).

A *bundle* is whatever you already have on disk for a game: an
``app_<AppID>.lua`` unlock script plus its ``.manifest`` files. This module
reads that bundle and turns it into a :class:`GameSpec`, so instead of writing
a YAML spec by hand you can point the installer at the files directly::

    steam-dl install --bundle mygame.zip

Nothing here downloads anything -- it only unpacks and parses files that are
already present. The lua is parsed with SteamTools' own primitives:

    addappid(<id>)                     -> app or key-less depot
    addappid(<id>, 1, "<hex key>")     -> depot with a decryption key
    setManifestid(<depot>, "<gid>", 0) -> pins a manifest generation
"""

from __future__ import annotations

import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .errors import ValidationError
from .logutil import get_logger
from .models import Depot, GameSpec

log = get_logger()

_COMMENT = re.compile(r"--.*?$", re.MULTILINE)
_ADDAPPID = re.compile(
    r"""addappid\(\s*(\d+)\s*(?:,\s*\d+\s*,\s*["']([0-9a-fA-F]*)["']\s*)?\)""",
    re.IGNORECASE,
)
_SETMANIFEST = re.compile(
    r"""setManifestid\(\s*(\d+)\s*,\s*["'](\d+)["']""",
    re.IGNORECASE,
)
_MANIFEST_FILE = re.compile(r"^(\d+)_(\d+)\.manifest$", re.IGNORECASE)


def parse_lua(text: str) -> Tuple[List[int], Dict[int, str], Dict[int, str]]:
    """Return ``(ids_in_order, keys_by_depot, manifests_by_depot)``.

    ``ids_in_order`` keeps the order in which ``addappid`` appeared, which lets
    the caller fall back to "the first bare id is the app" when the filename
    does not carry the AppID.
    """
    clean = _COMMENT.sub("", text)
    ids: List[int] = []
    keys: Dict[int, str] = {}
    for m in _ADDAPPID.finditer(clean):
        depot = int(m.group(1))
        if depot not in ids:
            ids.append(depot)
        if m.group(2):
            keys[depot] = m.group(2)
    manifests: Dict[int, str] = {}
    for m in _SETMANIFEST.finditer(clean):
        manifests[int(m.group(1))] = m.group(2)
    return ids, keys, manifests


def _appid_from_name(path: Path) -> Optional[int]:
    m = re.match(r"app_(\d+)\.lua$", path.name, re.IGNORECASE)
    return int(m.group(1)) if m else None


def spec_from_lua(
    lua_path: Path,
    *,
    name: Optional[str] = None,
    manifest_dir: Optional[Path] = None,
) -> GameSpec:
    """Build a :class:`GameSpec` from a single lua file.

    The AppID is taken from the ``app_<AppID>.lua`` filename when possible,
    otherwise from the first key-less ``addappid`` call. Manifest ids come from
    ``setManifestid`` and, when absent, from ``<depot>_<gid>.manifest`` files
    found next to the lua.
    """
    text = lua_path.read_text(encoding="utf-8", errors="replace")
    ids, keys, manifests = parse_lua(text)
    if not ids:
        raise ValidationError(f"no addappid(...) calls found in {lua_path}")

    appid = _appid_from_name(lua_path)
    if appid is None:
        # First id that has no key is most likely the app itself.
        appid = next((i for i in ids if i not in keys), ids[0])

    # Fill missing manifest ids from manifest filenames in the bundle.
    scan_dir = manifest_dir or lua_path.parent
    for man in scan_dir.rglob("*.manifest"):
        fm = _MANIFEST_FILE.match(man.name)
        if fm:
            depot = int(fm.group(1))
            manifests.setdefault(depot, fm.group(2))

    depots = [
        Depot(depot_id=i, key=keys.get(i), manifest_id=manifests.get(i))
        for i in ids
        if i != appid
    ]

    return GameSpec(
        appid=appid,
        name=name or _default_name(appid),
        depots=depots,
    )


def _default_name(appid: int) -> str:
    try:
        from .steam import applist

        got = applist.name_for_appid(appid)
        if got:
            return got
    except Exception:  # offline / no cache -- fall through
        pass
    return f"App {appid}"


@dataclass
class Ingested:
    spec: GameSpec
    manifest_dir: Path
    _tmp: Optional[tempfile.TemporaryDirectory] = None

    def cleanup(self) -> None:
        if self._tmp is not None:
            self._tmp.cleanup()


def _find_lua(root: Path) -> Path:
    named = sorted(root.rglob("app_*.lua"))
    if named:
        return named[0]
    any_lua = sorted(root.rglob("*.lua"))
    if any_lua:
        return any_lua[0]
    raise ValidationError(f"no .lua file found in bundle: {root}")


def ingest(path: Path, *, name: Optional[str] = None) -> Ingested:
    """Load a bundle from a directory or ``.zip`` and return spec + manifests."""
    path = Path(path)
    if not path.exists():
        raise ValidationError(f"bundle not found: {path}")

    tmp: Optional[tempfile.TemporaryDirectory] = None
    if path.is_file() and path.suffix.lower() == ".zip":
        tmp = tempfile.TemporaryDirectory(prefix="steam-dl-bundle-")
        root = Path(tmp.name)
        log.info("bundle: extracting %s", path.name)
        with zipfile.ZipFile(path) as zf:
            zf.extractall(root)
    elif path.is_dir():
        root = path
    else:
        raise ValidationError(f"bundle must be a directory or .zip: {path}")

    lua = _find_lua(root)
    manifest_dir = lua.parent
    log.info("bundle: using lua %s", lua.name)
    spec = spec_from_lua(lua, name=name, manifest_dir=manifest_dir)
    log.info(
        "bundle: appid=%s depots=%d (keys=%d)",
        spec.appid,
        len(spec.depots),
        sum(1 for d in spec.depots if d.key),
    )
    return Ingested(spec=spec, manifest_dir=manifest_dir, _tmp=tmp)
