from pathlib import Path

from steam_dl.models import Depot, GameSpec
from steam_dl.stages.manifests import build_lua
from steam_dl.stages.relocate import apply_goldberg, find_steam_api_dlls, relocate


def test_build_lua_emits_keys_and_manifests():
    spec = GameSpec(
        appid=220,
        name="HL2",
        depots=[
            Depot(depot_id=221, key="deadbeef", manifest_id="999"),
            Depot(depot_id=222),
        ],
    )
    lua = build_lua(spec)
    assert "addappid(220)" in lua
    assert 'addappid(221, 1, "deadbeef")' in lua
    assert 'setManifestid(221, "999", 0)' in lua
    assert "addappid(222)" in lua


def test_relocate_moves_tree(tmp_path: Path):
    src = tmp_path / "common" / "Game"
    src.mkdir(parents=True)
    (src / "game.exe").write_text("x")
    dest = tmp_path / "Games" / "Game"
    relocate(src, dest)
    assert (dest / "game.exe").exists()
    assert not src.exists()


def test_apply_goldberg_patches_and_writes_appid(tmp_path: Path):
    game = tmp_path / "Game"
    (game / "bin").mkdir(parents=True)
    (game / "bin" / "steam_api64.dll").write_bytes(b"ORIGINAL")

    gold = tmp_path / "goldberg"
    gold.mkdir()
    (gold / "steam_api64.dll").write_bytes(b"GOLDBERG")

    patched = apply_goldberg(game, 220, gold)
    assert len(patched) == 1
    assert (game / "bin" / "steam_api64.dll").read_bytes() == b"GOLDBERG"
    assert (game / "bin" / "steam_api64.dll.orig").read_bytes() == b"ORIGINAL"
    assert (game / "bin" / "steam_appid.txt").read_text().strip() == "220"


def test_find_dlls_is_recursive(tmp_path: Path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "steam_api.dll").write_text("")
    (tmp_path / "a" / "b" / "steam_api64.dll").write_text("")
    assert len(find_steam_api_dlls(tmp_path)) == 2
