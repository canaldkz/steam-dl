import sqlite3
from pathlib import Path

from steam_dl.config import Config
from steam_dl.goldberg_config import SteamSettings, write_steam_settings
from steam_dl.launchers import make_launcher


def test_steam_settings_files():
    s = SteamSettings(account_name="Neo", listen_port=1234, offline=True)
    files = s.files(220)
    assert files["steam_appid.txt"].strip() == "220"
    assert files["force_account_name.txt"].strip() == "Neo"
    assert files["listen_port.txt"].strip() == "1234"
    assert "offline.txt" in files


def test_write_steam_settings(tmp_path: Path):
    d = tmp_path / "bin"
    d.mkdir()
    write_steam_settings([d], 220, SteamSettings(account_name="Neo"))
    st = d / "steam_settings"
    assert (st / "force_account_name.txt").read_text().strip() == "Neo"
    assert (st / "steam_appid.txt").read_text().strip() == "220"


def test_script_launcher(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    cfg = Config(launcher="script", proton_tool="GE-Proton")
    game = tmp_path / "Games" / "MyGame"
    game.mkdir(parents=True)
    exe = game / "game.exe"
    exe.write_text("")
    res = make_launcher(cfg).register("My Game", exe, game)
    script = next(f for f in res.files if f.suffix == ".sh")
    body = script.read_text()
    assert "umu-run" in body and "game.exe" in body
    assert "GE-Proton" in body
    assert script.stat().st_mode & 0o100  # executable


def test_portproton_launcher(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    cfg = Config(launcher="portproton")
    game = tmp_path / "g"
    game.mkdir()
    exe = game / "game.exe"
    exe.write_text("")
    res = make_launcher(cfg).register("G", exe, game)
    body = next(f for f in res.files if f.suffix == ".sh").read_text()
    assert "flatpak run ru.linux_gaming.PortProton" in body


def test_lutris_launcher_writes_yaml_and_db(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    # Prepare a minimal Lutris DB so the insert path is exercised.
    db = tmp_path / ".local/share/lutris/pga.db"
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE games (id INTEGER PRIMARY KEY, name TEXT, slug TEXT, "
        "runner TEXT, directory TEXT, installed INTEGER, configpath TEXT, "
        "platform TEXT, hidden INTEGER, installed_at INTEGER)"
    )
    con.commit()
    con.close()
    (tmp_path / ".config/lutris").mkdir(parents=True)

    cfg = Config(launcher="lutris")
    game = tmp_path / "Games" / "MyGame"
    game.mkdir(parents=True)
    exe = game / "game.exe"
    exe.write_text("")
    res = make_launcher(cfg).register("My Game", exe, game)

    yml = next(f for f in res.files if f.suffix == ".yml")
    assert "game.exe" in yml.read_text()
    con = sqlite3.connect(db)
    rows = list(con.execute("SELECT name, runner, directory FROM games"))
    con.close()
    assert rows == [("My Game", "wine", str(game))]
