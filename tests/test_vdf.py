from steam_dl.vdf import binary_dumps, binary_loads, text_dumps, text_loads


def test_text_roundtrip_nested():
    src = {
        "InstallConfigStore": {
            "Software": {
                "Valve": {
                    "Steam": {
                        "CompatToolMapping": {
                            "3405691582": {"name": "GE-Proton", "config": "", "priority": "250"}
                        }
                    }
                }
            }
        }
    }
    text = text_dumps(src)
    assert text_loads(text) == src


def test_text_handles_comments_and_escapes():
    text = '''
    // a comment
    "root"
    {
        "path"   "C:\\\\Games\\\\x"
        "quote"  "he said \\"hi\\""
    }
    '''
    parsed = text_loads(text)
    assert parsed["root"]["path"] == "C:\\Games\\x"
    assert parsed["root"]["quote"] == 'he said "hi"'


def test_binary_roundtrip():
    src = {
        "shortcuts": {
            "0": {
                "appid": -889275714,
                "AppName": "My Game",
                "Exe": '"/home/user/Games/My Game/game.exe"',
                "IsHidden": 0,
                "tags": {"0": "installed"},
            }
        }
    }
    blob = binary_dumps(src)
    assert binary_loads(blob) == src
