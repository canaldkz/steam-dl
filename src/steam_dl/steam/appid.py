"""Deterministic app-id math for non-Steam shortcuts.

Steam derives the identifier for a non-Steam game from the executable string
and the display name. Two forms exist:

* the **32-bit** id -- stored in the ``appid`` field of ``shortcuts.vdf`` and
  used as the key in ``config.vdf`` -> ``CompatToolMapping``;
* the **64-bit** id -- used only for ``steam://rungameid/<id>`` launch URLs.

``exe`` must be the *exact* string that is written into ``shortcuts.vdf``,
including its surrounding quotes, otherwise the CRC will not match what Steam
computes internally.
"""

from __future__ import annotations

import zlib


def shortcut_appid(exe: str, appname: str) -> int:
    """Return the 32-bit non-Steam app id (high bit set)."""
    crc = zlib.crc32((exe + appname).encode("utf-8")) & 0xFFFFFFFF
    return crc | 0x80000000


def shortcut_appid_signed(exe: str, appname: str) -> int:
    """Same id as :func:`shortcut_appid` but as a signed int32.

    Older Steam clients stored the ``appid`` field signed; writing the signed
    form keeps us compatible with both.
    """
    unsigned = shortcut_appid(exe, appname)
    return unsigned - 0x100000000 if unsigned >= 0x80000000 else unsigned


def big_picture_gameid(exe: str, appname: str) -> int:
    """Return the 64-bit id used by ``steam://rungameid/<id>``."""
    return (shortcut_appid(exe, appname) << 32) | 0x02000000
