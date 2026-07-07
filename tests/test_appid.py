from steam_dl.steam.appid import (
    big_picture_gameid,
    shortcut_appid,
    shortcut_appid_signed,
)


def test_appid_is_stable_and_high_bit_set():
    exe = '"/home/user/Games/My Game/game.exe"'
    name = "My Game"
    a = shortcut_appid(exe, name)
    assert a == shortcut_appid(exe, name)  # deterministic
    assert a & 0x80000000  # high bit always set


def test_signed_matches_unsigned():
    exe = '"/x/y.exe"'
    name = "Z"
    unsigned = shortcut_appid(exe, name)
    signed = shortcut_appid_signed(exe, name)
    assert (signed & 0xFFFFFFFF) == unsigned


def test_big_picture_id_derives_from_short_id():
    exe = '"/x/y.exe"'
    name = "Z"
    short = shortcut_appid(exe, name)
    assert big_picture_gameid(exe, name) == (short << 32) | 0x02000000
