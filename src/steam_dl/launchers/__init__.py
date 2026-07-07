"""Launchers -- stage 5 registration targets."""

from __future__ import annotations

from ..config import Config
from .base import Launcher, LaunchResult
from .lutris import LutrisLauncher
from .portproton import PortProtonLauncher
from .script import ScriptLauncher
from .steam import SteamLauncher

_LAUNCHERS = {
    "steam": SteamLauncher,
    "lutris": LutrisLauncher,
    "portproton": PortProtonLauncher,
    "script": ScriptLauncher,
}

LAUNCHER_NAMES = list(_LAUNCHERS)


def make_launcher(cfg: Config) -> Launcher:
    try:
        return _LAUNCHERS[cfg.launcher](cfg)
    except KeyError:
        raise ValueError(
            f"unknown launcher {cfg.launcher!r}; choose from {', '.join(_LAUNCHERS)}"
        )


__all__ = ["Launcher", "LaunchResult", "make_launcher", "LAUNCHER_NAMES"]
