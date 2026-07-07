"""Runtime configuration -- paths, backend choice, timeouts, toggles.

Every value has a sane default for a Bazzite handheld so a bare
``steam-dl install <appid>`` works out of the box, but each can be overridden
on the command line or in a small JSON/YAML config file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional

HOME = Path(os.path.expanduser("~"))


@dataclass
class Config:
    # --- backend selection -------------------------------------------------
    backend: str = "portproton"          # "portproton" | "depotdownloader"
    prefix_name: str = "STEAM"           # PortProton prefix name

    # --- external commands -------------------------------------------------
    flatpak_bin: str = "flatpak"
    portproton_app: str = "ru.linux_gaming.PortProton"
    depotdownloader_bin: str = "DepotDownloader"
    steam_bin: str = "steam"

    # --- DRM bypass --------------------------------------------------------
    goldberg_dir: Optional[Path] = None  # template dir with steam_api*.dll
    patch_drm: bool = True

    # --- destination -------------------------------------------------------
    games_dir: Path = field(default_factory=lambda: HOME / "Games")

    # --- native steam integration -----------------------------------------
    proton_tool: str = "GE-Proton"
    add_to_steam: bool = True
    restart_steam: bool = False          # off by default: it is disruptive

    # --- watcher tuning ----------------------------------------------------
    acf_appear_timeout: int = 120        # s to wait for appmanifest to exist
    download_timeout: int = 6 * 3600     # s hard cap on the whole download
    poll_interval: float = 6.0           # s between .acf reads

    user_id: Optional[str] = None        # userdata/<id>; auto-detected if None
    dry_run: bool = False

    def merged(self, **overrides) -> "Config":
        clean = {k: v for k, v in overrides.items() if v is not None}
        return replace(self, **clean)


def load_config(path: Optional[Path]) -> Config:
    cfg = Config()
    if path is None:
        return cfg
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(raw) or {}
    else:
        import json

        data = json.loads(raw)
    # Coerce known path fields.
    for key in ("goldberg_dir", "games_dir"):
        if key in data and data[key] is not None:
            data[key] = Path(os.path.expanduser(str(data[key])))
    known = {f for f in Config().__dataclass_fields__}  # type: ignore[attr-defined]
    return replace(cfg, **{k: v for k, v in data.items() if k in known})
