"""Steam-less launcher: register the game in Lutris.

Lutris (preinstalled on Bazzite) keeps a per-game YAML config in
``config/lutris/games/`` and a row in its ``pga.db`` SQLite database. Both are
written here. The database insert is defensive -- it introspects the ``games``
table and only fills columns that exist -- and is skipped (with the YAML still
emitted for manual import) if no database is present.

The runner is set to ``wine``; switch it to Proton-GE inside Lutris if a title
needs Proton specifically.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import List, Optional, Tuple

from .base import Launcher, LaunchResult, slugify

def _candidates() -> list:
    """(config_dir, pga.db) pairs: native then Flatpak."""
    home = Path.home()
    return [
        (home / ".config/lutris", home / ".local/share/lutris/pga.db"),
        (
            home / ".var/app/net.lutris.Lutris/config/lutris",
            home / ".var/app/net.lutris.Lutris/data/lutris/pga.db",
        ),
    ]


def _find_lutris() -> Tuple[Optional[Path], Optional[Path]]:
    for config_dir, db in _candidates():
        if config_dir.is_dir() or db.exists():
            return config_dir, db
    return None, None


def _yaml_config(exe: Path, prefix: Path) -> str:
    return (
        "game:\n"
        f"  exe: {exe}\n"
        f"  prefix: {prefix}\n"
        "  args: ''\n"
        "system: {}\n"
        "wine: {}\n"
    )


class LutrisLauncher(Launcher):
    kind = "lutris"

    def register(self, name: str, exe: Path, game_dir: Path) -> LaunchResult:
        config_dir, db = _find_lutris()
        if config_dir is None:
            config_dir = _candidates()[0][0]  # write to native path for later import

        slug = slugify(name)
        configpath = f"{slug}-{int(time.time())}"
        games_cfg_dir = config_dir / "games"
        cfg_file = games_cfg_dir / f"{configpath}.yml"
        prefix = game_dir / "prefix"

        files: List[Path] = []
        self._log("stage5: writing Lutris config %s", cfg_file)
        if not self.cfg.dry_run:
            games_cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg_file.write_text(_yaml_config(exe, prefix), encoding="utf-8")
        files.append(cfg_file)

        inserted = False
        if db and db.exists() and not self.cfg.dry_run:
            inserted = self._insert_row(db, name, slug, configpath, game_dir)

        note = (
            "Registered in Lutris."
            if inserted
            else "Lutris DB not found; import the .yml in Lutris (+ > Import)."
        )
        return LaunchResult(kind=self.kind, files=files, note=note)

    def _insert_row(self, db: Path, name, slug, configpath, game_dir) -> bool:
        try:
            con = sqlite3.connect(str(db))
            cur = con.cursor()
            cols = {row[1] for row in cur.execute("PRAGMA table_info(games)")}
            wanted = {
                "name": name,
                "slug": slug,
                "runner": "wine",
                "directory": str(game_dir),
                "installed": 1,
                "configpath": configpath,
                "platform": "Windows",
                "hidden": 0,
                "installed_at": int(time.time()),
            }
            use = {k: v for k, v in wanted.items() if k in cols}
            # Avoid duplicate rows on re-run.
            cur.execute("DELETE FROM games WHERE slug = ?", (slug,))
            placeholders = ", ".join("?" for _ in use)
            cur.execute(
                f"INSERT INTO games ({', '.join(use)}) VALUES ({placeholders})",
                list(use.values()),
            )
            con.commit()
            con.close()
            return True
        except sqlite3.Error as exc:
            self._log("stage5: Lutris DB write failed (%s); YAML still written", exc)
            return False

    def _log(self, msg, *args):
        from ..logutil import get_logger

        get_logger().info(msg, *args)
