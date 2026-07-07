"""Generate a Goldberg / GBE-Fork ``steam_settings/`` directory.

Goldberg reads its configuration from a ``steam_settings/`` folder next to the
patched ``steam_api*.dll``. These settings make the emulator behave fully
offline (no account, no Valve servers) and, optionally, enable LAN/VPN
multiplayer between other Goldberg players.

Classic ``.txt`` settings are written because they are understood by the widest
range of Goldberg builds (including current GBE Fork's legacy compatibility).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .logutil import get_logger

log = get_logger()


@dataclass
class SteamSettings:
    account_name: str = "Player"
    language: str = "english"
    listen_port: int = 47584          # Goldberg default; shared by LAN peers
    offline: bool = True              # never contact Valve
    disable_networking: bool = False  # True = pure single-player, no LAN
    steam_id: Optional[str] = None    # override the emulated SteamID64
    dlcs: Dict[int, str] = field(default_factory=dict)  # appid -> name

    def files(self, appid: int) -> Dict[str, str]:
        out: Dict[str, str] = {
            "steam_appid.txt": f"{appid}\n",
            "force_account_name.txt": f"{self.account_name}\n",
            "force_language.txt": f"{self.language}\n",
            "listen_port.txt": f"{self.listen_port}\n",
        }
        if self.steam_id:
            out["force_steamid.txt"] = f"{self.steam_id}\n"
        if self.offline:
            out["offline.txt"] = "\n"
        if self.disable_networking:
            out["disable_networking.txt"] = "\n"
        if self.dlcs:
            lines = ["1"] + [f"{aid}={name}" for aid, name in self.dlcs.items()]
            out["DLC.txt"] = "\n".join(lines) + "\n"
        return out


def write_steam_settings(
    dirs: Iterable[Path],
    appid: int,
    settings: SteamSettings,
    *,
    dry_run: bool = False,
) -> List[Path]:
    """Write ``steam_settings/`` into every directory in ``dirs``.

    Returns the list of settings folders created.
    """
    created: List[Path] = []
    payload = settings.files(appid)
    for base in dirs:
        target = Path(base) / "steam_settings"
        log.info("goldberg: writing steam_settings in %s", base)
        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)
            for name, content in payload.items():
                (target / name).write_text(content, encoding="utf-8")
        created.append(target)
    return created
