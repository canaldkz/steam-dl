"""Native Steam launcher -- adds a shortcut + Proton mapping for Game Mode.

Thin wrapper over :func:`steam_dl.stages.integrate.integrate` so native Steam
is just one launcher among the Steam-less options.
"""

from __future__ import annotations

from pathlib import Path

from ..stages.integrate import integrate
from .base import Launcher, LaunchResult


class SteamLauncher(Launcher):
    kind = "steam"

    def register(self, name: str, exe: Path, game_dir: Path) -> LaunchResult:
        appid = integrate(self.cfg, name, exe, launch_options="")
        note = "Added to native Steam."
        if appid is not None:
            note += f" Shortcut id {appid} mapped to {self.cfg.proton_tool}."
        return LaunchResult(kind=self.kind, note=note)
