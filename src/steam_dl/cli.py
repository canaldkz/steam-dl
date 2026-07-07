"""Command-line entry point.

Sub-commands
------------
search    resolve a name to candidate AppIDs
install   run the full install pipeline for an appid / name / spec file
env       print detected paths (native Steam, PortProton prefix, user id)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from . import pipeline
from .config import Config, load_config
from .errors import SteamDlError
from .logutil import setup_logging
from .models import Depot, GameSpec
from .steam import applist, paths


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("-c", "--config", type=Path, help="JSON/YAML config file")
    p.add_argument("--backend", choices=["portproton", "depotdownloader"])
    p.add_argument("--prefix", dest="prefix_name", help="PortProton prefix name")
    p.add_argument("--games-dir", type=Path, help="destination root (default ~/Games)")
    p.add_argument("--goldberg-dir", type=Path, help="Goldberg template dir")
    p.add_argument("--proton", dest="proton_tool", help="compat tool name (default GE-Proton)")
    p.add_argument("--user-id", help="Steam userdata id override")
    p.add_argument("--no-drm-patch", action="store_true", help="skip Goldberg patching")
    p.add_argument(
        "--launcher",
        choices=["steam", "lutris", "portproton", "script", "none"],
        help="how to register the game (default steam; lutris/portproton/script = no Steam)",
    )
    p.add_argument("--no-steam", action="store_true", help="alias for --launcher none")
    p.add_argument("--account-name", help="Goldberg emulated player name")
    p.add_argument("--no-emulate-settings", action="store_true",
                   help="do not write Goldberg steam_settings/")
    p.add_argument("--restart-steam", action="store_true", help="restart Steam at the end")
    p.add_argument("-n", "--dry-run", action="store_true", help="log actions without doing them")
    p.add_argument("-v", "--verbose", action="store_true")


def _cfg_from_args(args: argparse.Namespace) -> Config:
    cfg = load_config(args.config)
    cfg = cfg.merged(
        backend=getattr(args, "backend", None),
        prefix_name=getattr(args, "prefix_name", None),
        games_dir=getattr(args, "games_dir", None),
        goldberg_dir=getattr(args, "goldberg_dir", None),
        proton_tool=getattr(args, "proton_tool", None),
        user_id=getattr(args, "user_id", None),
        launcher=getattr(args, "launcher", None),
        account_name=getattr(args, "account_name", None),
    )
    if getattr(args, "no_drm_patch", False):
        cfg = cfg.merged(patch_drm=False)
    if getattr(args, "no_emulate_settings", False):
        cfg = cfg.merged(emulate_settings=False)
    if getattr(args, "no_steam", False):
        cfg = cfg.merged(launcher="none")
    if getattr(args, "restart_steam", False):
        cfg = cfg.merged(restart_steam=True)
    if getattr(args, "dry_run", False):
        cfg = cfg.merged(dry_run=True)
    return cfg


def cmd_search(args: argparse.Namespace) -> int:
    matches = applist.search(args.query, refresh=args.refresh)
    if not matches:
        print("no matches", file=sys.stderr)
        return 1
    for m in matches:
        print(f"{m.appid:>8}  {m.name}")
    return 0


def cmd_env(args: argparse.Namespace) -> int:
    cfg = _cfg_from_args(args)
    root = paths.native_steam_root()
    print(f"native steam root : {root}")
    if root:
        uid = paths.detect_user_id(root, cfg.user_id)
        print(f"user id           : {uid}")
        if uid:
            print(f"shortcuts.vdf     : {paths.shortcuts_vdf_path(root, uid)}")
        print(f"config.vdf        : {paths.config_vdf_path(root)}")
    layout = paths.portproton_layout(cfg.prefix_name)
    print(f"portproton prefix : {layout.prefix_root} (exists={layout.prefix_root.is_dir()})")
    print(f"steamtools dir    : {layout.steamtools_dir} (exists={layout.steamtools_dir.is_dir()})")
    print(f"games dir         : {cfg.games_dir}")
    return 0


def _build_spec(args: argparse.Namespace) -> GameSpec:
    if args.spec:
        return GameSpec.load(args.spec)

    # Resolve name/appid on the fly for the "simple" path.
    match = applist.resolve(args.target)
    if match is None:
        raise SteamDlError(
            f"'{args.target}' is ambiguous or unknown; run 'steam-dl search' "
            "or pass a --spec file with an explicit appid"
        )
    depots = []
    for d in args.depot or []:
        parts = d.split(":")
        depot = Depot(depot_id=int(parts[0]))
        if len(parts) > 1 and parts[1]:
            depot.key = parts[1]
        if len(parts) > 2 and parts[2]:
            depot.manifest_id = parts[2]
        depots.append(depot)
    return GameSpec(
        appid=match.appid,
        name=args.name or match.name,
        depots=depots,
        executable=args.exe,
        install_dir=args.install_dir,
        launch_options=args.launch_options or "",
    )


def cmd_install(args: argparse.Namespace) -> int:
    cfg = _cfg_from_args(args)
    ingested = None
    if args.bundle:
        from . import bundle

        ingested = bundle.ingest(args.bundle, name=args.name)
        spec = ingested.spec
        if args.exe:
            spec.executable = args.exe
        if args.install_dir:
            spec.install_dir = args.install_dir
        if args.launch_options:
            spec.launch_options = args.launch_options
        manifest_source = args.manifest_source or ingested.manifest_dir
    else:
        if not args.spec and not args.target:
            raise SteamDlError("provide a target AppID/name, --spec, or --bundle")
        spec = _build_spec(args)
        manifest_source = args.manifest_source

    try:
        result = pipeline.run(spec, cfg, manifest_source=manifest_source)
    finally:
        if ingested is not None:
            ingested.cleanup()
    print()
    print(f"game dir     : {result.game_dir}")
    print(f"executable   : {result.exe_path}")
    print(f"patched dlls : {len(result.patched_dlls)}")
    if result.launch is not None:
        print(f"launcher     : {result.launch.kind}")
        if result.launch.note:
            print(f"  {result.launch.note}")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    from .gui import serve

    serve(
        host=args.host,
        port=args.port,
        config=args.config,
        open_browser=not args.no_browser,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="steam-dl", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("search", help="resolve a name to AppIDs")
    ps.add_argument("query")
    ps.add_argument("--refresh", action="store_true", help="refresh the cached app list")
    ps.set_defaults(func=cmd_search)

    pe = sub.add_parser("env", help="show detected paths")
    _add_common(pe)
    pe.set_defaults(func=cmd_env)

    pi = sub.add_parser("install", help="install a game end-to-end")
    pi.add_argument("target", nargs="?", help="AppID or game name")
    pi.add_argument(
        "--bundle",
        type=Path,
        help="ready-made SteamTools bundle (folder or .zip) with lua + manifests",
    )
    pi.add_argument("--spec", type=Path, help="JSON/YAML spec with depots and keys")
    pi.add_argument("--name", help="override display name")
    pi.add_argument("--exe", help="relative path to the launch executable")
    pi.add_argument("--install-dir", help="steamapps/common dir name override")
    pi.add_argument("--launch-options", help="Steam launch options")
    pi.add_argument(
        "--depot",
        action="append",
        help="depot as ID[:KEY[:MANIFEST]] (repeatable)",
    )
    pi.add_argument(
        "--manifest-source",
        type=Path,
        help="dir with prebuilt .manifest files to copy into the prefix",
    )
    _add_common(pi)
    pi.set_defaults(func=cmd_install)

    pg = sub.add_parser("gui", help="launch the touch-friendly web GUI")
    pg.add_argument("--host", default="127.0.0.1", help="bind address (0.0.0.0 for LAN/phone)")
    pg.add_argument("--port", type=int, default=8756)
    pg.add_argument("--no-browser", action="store_true", help="do not auto-open a browser")
    pg.add_argument("-c", "--config", type=Path, help="JSON/YAML config file")
    pg.set_defaults(func=cmd_gui)
    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(getattr(args, "verbose", False))
    try:
        return args.func(args)
    except SteamDlError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
