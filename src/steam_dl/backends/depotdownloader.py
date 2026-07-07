"""DepotDownloader backend -- a Wine-free alternative.

DepotDownloader is a cross-platform .NET tool that pulls depots straight from
the Steam CDN given an appid/depot/manifest and (for locked depots) a
decryption key. When keys are known this removes the entire PortProton, Wine
and SteamTools stack: no prefix, no ``.acf`` polling, no ``wineserver -k``.

It downloads directly into ``games_dir/<name>`` so stage 4's relocation becomes
a no-op, and stages 4b (Goldberg) and 5 (native integration) run unchanged.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..errors import EnvironmentError_, ValidationError
from ..logutil import get_logger
from ..models import GameSpec
from .base import Backend

log = get_logger()


class DepotDownloaderBackend(Backend):
    def preflight(self) -> None:
        if shutil.which(self.cfg.depotdownloader_bin) is None:
            raise EnvironmentError_(
                f"'{self.cfg.depotdownloader_bin}' not found on PATH.\n"
                "Install from https://github.com/SteamRE/DepotDownloader"
            )

    def download(self, spec: GameSpec) -> Path:
        dest = self.cfg.games_dir / (spec.install_dir or spec.name)
        if not spec.depots:
            raise ValidationError(
                "DepotDownloader backend needs at least one depot in the spec"
            )
        dest.mkdir(parents=True, exist_ok=True)

        for depot in spec.depots:
            cmd = [
                self.cfg.depotdownloader_bin,
                "-app",
                str(spec.appid),
                "-depot",
                str(depot.depot_id),
                "-dir",
                str(dest),
            ]
            if depot.manifest_id:
                cmd += ["-manifest", depot.manifest_id]
            if depot.key:
                cmd += ["-depotkey", depot.key]
            log.info("stage1-3: DepotDownloader app %s depot %s", spec.appid, depot.depot_id)
            if self.cfg.dry_run:
                log.info("(dry-run) %s", " ".join(cmd))
                continue
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                raise ValidationError(
                    f"DepotDownloader failed for depot {depot.depot_id} "
                    f"(exit {result.returncode})"
                )

        if not self.cfg.dry_run and not any(dest.iterdir()):
            raise ValidationError(f"DepotDownloader produced no files in {dest}")
        return dest
