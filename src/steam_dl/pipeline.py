"""Linear state machine tying the five stages together.

Each stage validates its own post-condition and raises on failure, so the
orchestrator here stays thin: run the backend (stages 1-3), relocate + patch
(stage 4), then integrate with native Steam (stage 5).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .backends import make_backend
from .config import Config
from .errors import ValidationError
from .logutil import get_logger
from .models import GameSpec
from .stages.integrate import integrate
from .stages.relocate import apply_goldberg, relocate

log = get_logger()


@dataclass
class Result:
    game_dir: Path
    exe_path: Path
    shortcut_appid: Optional[int]
    patched_dlls: List[Path]


def _resolve_exe(game_dir: Path, spec: GameSpec) -> Path:
    if spec.executable:
        candidate = game_dir / spec.executable
        if candidate.exists():
            return candidate
        # Tolerate a bare filename anywhere in the tree.
        matches = list(game_dir.rglob(Path(spec.executable).name))
        if matches:
            return matches[0]
        raise ValidationError(f"executable not found: {spec.executable} under {game_dir}")

    # No exe given: pick the largest top-level .exe as a heuristic.
    exes = sorted(
        (p for p in game_dir.rglob("*.exe") if p.is_file()),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    exes = [p for p in exes if p.name.lower() not in _NON_GAME_EXES]
    if not exes:
        raise ValidationError(f"no .exe found under {game_dir}; set 'executable' in the spec")
    log.info("auto-selected executable: %s", exes[0].name)
    return exes[0]


_NON_GAME_EXES = {
    "unitycrashhandler64.exe",
    "unitycrashhandler32.exe",
    "vc_redist.x64.exe",
    "vc_redist.x86.exe",
    "dxsetup.exe",
    "vcredist_x64.exe",
    "vcredist_x86.exe",
}


def run(spec: GameSpec, cfg: Config, manifest_source: Optional[Path] = None) -> Result:
    log.info("=== steam-dl: %s (appid %s) ===", spec.name, spec.appid)
    backend = make_backend(cfg, manifest_source=manifest_source)
    backend.preflight()

    # Stages 1-3
    game_src = backend.download(spec)

    # Stage 4a -- relocate into ~/Games unless we already downloaded there.
    dest = cfg.games_dir / (spec.install_dir or spec.name)
    if game_src.resolve() == dest.resolve():
        game_dir = game_src
        log.info("stage4: already in destination, skipping relocation")
    else:
        game_dir = relocate(game_src, dest, dry_run=cfg.dry_run)

    # Stage 4b -- Goldberg DRM bypass.
    patched: List[Path] = []
    if cfg.patch_drm:
        patched = apply_goldberg(game_dir, spec.appid, cfg.goldberg_dir, dry_run=cfg.dry_run)
    else:
        log.info("stage4: DRM patch disabled")

    # Locate the launch target.
    exe_path = _resolve_exe(game_dir, spec) if not cfg.dry_run else (
        game_dir / (spec.executable or "game.exe")
    )

    # Stage 5 -- native Steam integration.
    shortcut_appid: Optional[int] = None
    if cfg.add_to_steam:
        shortcut_appid = integrate(cfg, spec.name, exe_path, spec.launch_options)
    else:
        log.info("stage5: skipping native Steam integration (--no-steam)")

    log.info("=== done: %s ===", spec.name)
    return Result(
        game_dir=game_dir,
        exe_path=exe_path,
        shortcut_appid=shortcut_appid,
        patched_dlls=patched,
    )
