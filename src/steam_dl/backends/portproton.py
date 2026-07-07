"""PortProton + SteamTools backend (the workflow from the task description).

Stage 1  inject the lua/manifests into the prefix's SteamTools config.
Stage 2  launch the Windows Steam client inside PortProton with an install URL.
Stage 3  poll ``appmanifest_<AppID>.acf`` until StateFlags says installed, then
         shut the prefix down cleanly via ``wineserver -k``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from ..errors import EnvironmentError_, ValidationError
from ..logutil import get_logger
from ..models import GameSpec
from ..stages.manifests import inject_manifests
from ..stages.watcher import wait_for_manifest, wait_until_installed
from ..steam import paths
from ..steam.acf import read_app_state
from .base import Backend

log = get_logger()


class PortProtonBackend(Backend):
    def __init__(self, cfg, manifest_source: Optional[Path] = None):
        super().__init__(cfg)
        self.manifest_source = manifest_source
        self.layout = paths.portproton_layout(cfg.prefix_name)

    # -- stage 0 -----------------------------------------------------------
    def preflight(self) -> None:
        if shutil.which(self.cfg.flatpak_bin) is None:
            raise EnvironmentError_(f"'{self.cfg.flatpak_bin}' not found on PATH")
        if not self.layout.prefix_root.is_dir():
            raise EnvironmentError_(
                f"PortProton prefix not found: {self.layout.prefix_root}\n"
                f"Create/select prefix '{self.cfg.prefix_name}' first."
            )
        if not self.layout.steamtools_dir.is_dir():
            raise EnvironmentError_(
                f"SteamTools config dir missing: {self.layout.steamtools_dir}"
            )

    # -- stages 1-3 --------------------------------------------------------
    def download(self, spec: GameSpec) -> Path:
        acf_path = self.layout.appmanifest(spec.appid)

        # Stage 1
        inject_manifests(
            spec,
            self.layout.steamtools_dir,
            manifest_source=self.manifest_source,
            dry_run=self.cfg.dry_run,
        )

        # Stage 2
        self._launch_install(spec.appid)

        # Stage 3
        if self.cfg.dry_run:
            log.info("stage3: (dry-run) skipping download watch")
            return self._installed_dir(spec)

        wait_for_manifest(acf_path, self.cfg.acf_appear_timeout, self.cfg.poll_interval)
        state = wait_until_installed(
            acf_path, self.cfg.download_timeout, self.cfg.poll_interval
        )
        self._shutdown_prefix()

        game_dir = self.layout.common / (spec.install_dir or state.installdir or spec.name)
        if not game_dir.is_dir():
            raise ValidationError(
                f"stage3: installed dir not found after download: {game_dir}"
            )
        return game_dir

    # -- helpers -----------------------------------------------------------
    def _launch_install(self, appid: int) -> None:
        cmd = [
            self.cfg.flatpak_bin,
            "run",
            self.cfg.portproton_app,
            "-p",
            self.cfg.prefix_name,
            r"C:\Program Files (x86)\Steam\steam.exe",
            f"steam://install/{appid}",
        ]
        log.info("stage2: launching Windows Steam for install of appid %s", appid)
        if self.cfg.dry_run:
            log.info("stage2: (dry-run) %s", " ".join(cmd))
            return
        from ..proc import stream_process

        stream_process(cmd, on_line=lambda ln: log.debug("portproton: %s", ln))

    def _shutdown_prefix(self) -> None:
        cmd = [
            self.cfg.flatpak_bin,
            "run",
            f"--command=wineserver",
            self.cfg.portproton_app,
            "-k",
        ]
        log.info("stage3: shutting down prefix (wineserver -k)")
        if self.cfg.dry_run:
            return
        try:
            subprocess.run(cmd, timeout=60, check=False)
        except subprocess.TimeoutExpired:
            log.warning("stage3: wineserver -k timed out")

    def _installed_dir(self, spec: GameSpec) -> Path:
        state = read_app_state(self.layout.appmanifest(spec.appid))
        name = spec.install_dir or (state.installdir if state else "") or spec.name
        return self.layout.common / name
