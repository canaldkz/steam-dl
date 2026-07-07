"""Input data model for a single game installation job."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Depot:
    depot_id: int
    key: Optional[str] = None          # hex decryption key, if known
    manifest_id: Optional[str] = None  # specific manifest gid, optional


@dataclass
class GameSpec:
    """Everything needed to install one game."""

    appid: int
    name: str
    depots: List[Depot] = field(default_factory=list)
    executable: Optional[str] = None   # relative path of the launch exe
    install_dir: Optional[str] = None  # steamapps/common/<dir>; defaults to name
    launch_options: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "GameSpec":
        depots = []
        for d in data.get("depots", []) or []:
            if isinstance(d, dict):
                depots.append(
                    Depot(
                        depot_id=int(d["depot_id"] if "depot_id" in d else d["id"]),
                        key=d.get("key"),
                        manifest_id=str(d["manifest_id"]) if d.get("manifest_id") else None,
                    )
                )
            else:  # bare depot id
                depots.append(Depot(depot_id=int(d)))
        return cls(
            appid=int(data["appid"]),
            name=str(data["name"]),
            depots=depots,
            executable=data.get("executable"),
            install_dir=data.get("install_dir"),
            launch_options=data.get("launch_options", ""),
        )

    @classmethod
    def load(cls, path: Path) -> "GameSpec":
        raw = path.read_text(encoding="utf-8")
        if path.suffix.lower() in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("PyYAML is required to read YAML specs") from exc
            data = yaml.safe_load(raw)
        else:
            data = json.loads(raw)
        return cls.from_dict(data)
