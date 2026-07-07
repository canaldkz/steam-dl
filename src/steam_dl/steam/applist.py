"""Resolve a game name to an AppID using Steam's public app list.

The list is fetched from the store API and cached on disk for a day. Name
matching is deliberately fuzzy-but-conservative: exact (case-folded) first,
then substring, and only if a single candidate remains do we auto-resolve.
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

_APPLIST_URL = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
_CACHE = Path.home() / ".cache" / "steam-dl" / "applist.json"
_MAX_AGE = 24 * 3600


@dataclass
class AppMatch:
    appid: int
    name: str


def _load_cached() -> Optional[Dict[str, int]]:
    if not _CACHE.exists():
        return None
    if time.time() - _CACHE.stat().st_mtime > _MAX_AGE:
        return None
    try:
        return json.loads(_CACHE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _fetch() -> Dict[str, int]:
    with urllib.request.urlopen(_APPLIST_URL, timeout=30) as resp:
        payload = json.load(resp)
    apps = payload.get("applist", {}).get("apps", [])
    table: Dict[str, int] = {}
    for app in apps:
        name = app.get("name")
        appid = app.get("appid")
        if name and appid:
            # First writer wins; the store lists the base game before DLC.
            table.setdefault(name, appid)
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(table), encoding="utf-8")
    return table


def _table(refresh: bool = False) -> Dict[str, int]:
    if not refresh:
        cached = _load_cached()
        if cached:
            return cached
    return _fetch()


def search(query: str, *, limit: int = 15, refresh: bool = False) -> List[AppMatch]:
    table = _table(refresh=refresh)
    q = query.strip().casefold()
    exact = [AppMatch(appid, name) for name, appid in table.items() if name.casefold() == q]
    if exact:
        return exact[:limit]
    subs = [AppMatch(appid, name) for name, appid in table.items() if q in name.casefold()]
    subs.sort(key=lambda m: (len(m.name), m.name.casefold()))
    return subs[:limit]


def name_for_appid(appid: int, *, refresh: bool = False) -> Optional[str]:
    """Reverse lookup: AppID -> display name, best-effort from the cache."""
    for name, aid in _table(refresh=refresh).items():
        if aid == appid:
            return name
    return None


def resolve(query: str, *, refresh: bool = False) -> Optional[AppMatch]:
    """Return a single unambiguous match, or ``None`` if 0/many candidates."""
    if query.strip().isdigit():
        return AppMatch(int(query.strip()), query.strip())
    matches = search(query, refresh=refresh)
    exact = [m for m in matches if m.name.casefold() == query.strip().casefold()]
    if len(exact) == 1:
        return exact[0]
    if len(matches) == 1:
        return matches[0]
    return None
