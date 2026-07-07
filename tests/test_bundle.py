import zipfile
from pathlib import Path

from steam_dl.bundle import ingest, parse_lua, spec_from_lua

_LUA = '''
-- Half-Life 2 unlock
addappid(220)
addappid(221, 1, "deadbeefdeadbeef")
setManifestid(221, "1234567890", 0)
addappid(222, 1, "cafebabecafebabe")
'''


def test_parse_lua_extracts_ids_keys_manifests():
    ids, keys, manifests = parse_lua(_LUA)
    assert ids == [220, 221, 222]
    assert keys == {221: "deadbeefdeadbeef", 222: "cafebabecafebabe"}
    assert manifests == {221: "1234567890"}


def test_spec_from_lua_uses_filename_appid(tmp_path: Path):
    lua = tmp_path / "app_220.lua"
    lua.write_text(_LUA)
    spec = spec_from_lua(lua, name="Half-Life 2")
    assert spec.appid == 220
    assert spec.name == "Half-Life 2"
    depot_ids = {d.depot_id for d in spec.depots}
    assert depot_ids == {221, 222}          # app id excluded from depots
    d221 = next(d for d in spec.depots if d.depot_id == 221)
    assert d221.key == "deadbeefdeadbeef"
    assert d221.manifest_id == "1234567890"


def test_spec_fills_manifest_id_from_filename(tmp_path: Path):
    # No setManifestid line; manifest gid must be recovered from the filename.
    lua = tmp_path / "app_300.lua"
    lua.write_text("addappid(300)\naddappid(301, 1, \"aa\")\n")
    (tmp_path / "301_9988776655.manifest").write_bytes(b"x")
    spec = spec_from_lua(lua)
    d = next(d for d in spec.depots if d.depot_id == 301)
    assert d.manifest_id == "9988776655"


def test_ingest_folder(tmp_path: Path):
    lua = tmp_path / "app_220.lua"
    lua.write_text(_LUA)
    (tmp_path / "221_1234567890.manifest").write_bytes(b"m")
    res = ingest(tmp_path, name="HL2")
    assert res.spec.appid == 220
    assert res.manifest_dir == tmp_path


def test_ingest_lone_lua(tmp_path: Path):
    lua = tmp_path / "app_220.lua"
    lua.write_text(_LUA)
    res = ingest(lua, name="HL2")
    assert res.spec.appid == 220
    assert {d.depot_id for d in res.spec.depots} == {221, 222}
    assert res.manifest_dir == tmp_path


def test_ingest_zip(tmp_path: Path):
    zip_path = tmp_path / "hl2.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("app_220.lua", _LUA)
        zf.writestr("221_1234567890.manifest", "m")
    res = ingest(zip_path)
    try:
        assert res.spec.appid == 220
        assert {d.depot_id for d in res.spec.depots} == {221, 222}
        assert (res.manifest_dir / "221_1234567890.manifest").exists()
    finally:
        res.cleanup()
