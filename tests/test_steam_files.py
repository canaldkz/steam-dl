from pathlib import Path

from steam_dl.steam.appid import shortcut_appid
from steam_dl.steam.compat import set_compat_tool
from steam_dl.steam.shortcuts import Shortcut, add_shortcut, load_shortcuts
from steam_dl.vdf import text_loads


def test_add_shortcut_and_dedup(tmp_path: Path):
    path = tmp_path / "shortcuts.vdf"
    sc = Shortcut(app_name="My Game", exe="/games/mygame/game.exe", start_dir="/games/mygame")
    appid = add_shortcut(path, sc)

    data = load_shortcuts(path)
    entries = data["shortcuts"]
    assert len(entries) == 1
    entry = entries["0"]
    # Exe stored with quotes, and appid matches the quoted-exe hash.
    assert entry["Exe"] == '"/games/mygame/game.exe"'
    assert appid == shortcut_appid('"/games/mygame/game.exe"', "My Game")

    # Adding the same game again replaces rather than duplicating.
    add_shortcut(path, Shortcut(app_name="My Game", exe='"/games/mygame/game.exe"', start_dir="/games/mygame"))
    assert len(load_shortcuts(path)["shortcuts"]) == 1


def test_set_compat_tool_creates_hierarchy(tmp_path: Path):
    path = tmp_path / "config.vdf"
    set_compat_tool(path, 3405691582, "GE-Proton", priority=250)
    data = text_loads(path.read_text())
    node = data["InstallConfigStore"]["Software"]["Valve"]["Steam"]["CompatToolMapping"]["3405691582"]
    assert node == {"name": "GE-Proton", "config": "", "priority": "250"}


def test_set_compat_tool_preserves_existing(tmp_path: Path):
    path = tmp_path / "config.vdf"
    path.write_text(
        '"InstallConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n'
        '\t\t\t"Steam"\n\t\t\t{\n\t\t\t\t"KeepMe"\t\t"1"\n\t\t\t}\n\t\t}\n\t}\n}\n'
    )
    set_compat_tool(path, 42, "GE-Proton")
    data = text_loads(path.read_text())
    steam = data["InstallConfigStore"]["Software"]["Valve"]["Steam"]
    assert steam["KeepMe"] == "1"
    assert steam["CompatToolMapping"]["42"]["name"] == "GE-Proton"
