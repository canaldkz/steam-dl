"""Stage 5 -- register the game with native Steam for Game Mode.

Order is critical and differs from the naive guide: Steam caches
``shortcuts.vdf`` / ``config.vdf`` in memory and rewrites them on exit, so we
must **stop Steam first**, then edit both files, then start it again. Editing
while Steam is alive silently loses the change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import Config
from ..errors import EnvironmentError_, ValidationError
from ..logutil import get_logger
from ..proc import pgrep, stream_process, terminate, wait_for_exit
from ..steam import paths
from ..steam.compat import set_compat_tool
from ..steam.shortcuts import Shortcut, add_shortcut

log = get_logger()


def integrate(cfg: Config, app_name: str, exe_path: Path, launch_options: str = "") -> int:
    """Add the shortcut + compat mapping. Returns the shortcut app id."""
    steam_root = paths.native_steam_root()
    if steam_root is None:
        raise EnvironmentError_("native Steam install not found")
    user_id = paths.detect_user_id(steam_root, cfg.user_id)
    if user_id is None:
        raise EnvironmentError_(
            "could not determine Steam userdata id; sign in once or pass user_id"
        )

    shortcuts_path = paths.shortcuts_vdf_path(steam_root, user_id)
    config_path = paths.config_vdf_path(steam_root)

    steam_pids = pgrep("steam") + pgrep("steamwebhelper")
    was_running = bool(steam_pids)
    if was_running:
        log.info("stage5: stopping native Steam before editing vdf files")
        if not cfg.dry_run:
            terminate(steam_pids, timeout=30)

    shortcut = Shortcut(
        app_name=app_name,
        exe=str(exe_path),
        start_dir=str(exe_path.parent),
        launch_options=launch_options,
    )
    log.info("stage5: adding shortcut -> %s", shortcuts_path)
    if cfg.dry_run:
        appid = shortcut.appid()
    else:
        appid = add_shortcut(shortcuts_path, shortcut)

    log.info("stage5: mapping appid %s -> %s in config.vdf", appid, cfg.proton_tool)
    if not cfg.dry_run:
        set_compat_tool(config_path, appid, cfg.proton_tool)
        _assert_written(shortcuts_path, config_path)

    if was_running or cfg.restart_steam:
        _restart_steam(cfg)
    return appid


def _assert_written(shortcuts_path: Path, config_path: Path) -> None:
    if not shortcuts_path.exists():
        raise ValidationError(f"stage5: shortcuts.vdf was not written: {shortcuts_path}")
    if not config_path.exists():
        raise ValidationError(f"stage5: config.vdf was not written: {config_path}")


def _restart_steam(cfg: Config) -> None:
    if cfg.dry_run:
        log.info("stage5: (dry-run) would restart Steam")
        return
    pids = pgrep("steam")
    if pids:
        terminate(pids, timeout=30)
        wait_for_exit(pids, timeout=30)
    log.info("stage5: launching %s", cfg.steam_bin)
    # Detach; Game Mode / gamescope-session is out of scope here, we just
    # bring the client back so the new shortcut is visible.
    stream_process([cfg.steam_bin])
