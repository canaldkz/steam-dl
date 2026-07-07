"""Map a non-Steam app id to a Proton build in ``config.vdf``.

Path in the tree::

    InstallConfigStore -> Software -> Valve -> Steam -> CompatToolMapping -> <appid>

The child object is ``{ "name": <proton>, "config": "", "priority": "250" }``.
As with ``shortcuts.vdf``, Steam must be stopped before this file is edited.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from ..vdf import text_dumps, text_loads


def _walk(root: Dict, keys) -> Dict:
    """Descend ``root`` creating dicts as needed, case-insensitively."""
    node = root
    for key in keys:
        match = next((k for k in node if k.lower() == key.lower()), None)
        if match is None:
            node[key] = {}
            match = key
        child = node[match]
        if not isinstance(child, dict):
            child = {}
            node[match] = child
        node = child
    return node


def set_compat_tool(config_path: Path, appid: int, proton: str, priority: int = 250) -> None:
    text = config_path.read_text(encoding="utf-8", errors="replace") if config_path.exists() else ""
    data = text_loads(text) if text.strip() else {"InstallConfigStore": {}}

    mapping = _walk(
        data,
        ["InstallConfigStore", "Software", "Valve", "Steam", "CompatToolMapping"],
    )
    mapping[str(appid)] = {
        "name": proton,
        "config": "",
        "priority": str(priority),
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config_path.with_suffix(config_path.suffix + ".tmp")
    tmp.write_text(text_dumps(data) + "\n", encoding="utf-8")
    tmp.replace(config_path)
