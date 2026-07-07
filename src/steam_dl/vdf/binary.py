"""Parser and serializer for the *binary* Valve KeyValues format.

Used by ``shortcuts.vdf``. The encoding is a tag-length-value stream:

===========  ==================================================
type byte     payload
===========  ==================================================
``0x00``      nested map, terminated by a ``0x08`` byte
``0x01``      NUL-terminated UTF-8 string
``0x02``      little-endian signed int32
``0x08``      end-of-map marker (no key, no payload)
===========  ==================================================

Every non-terminator entry is ``<type><key\\x00><payload>``. Integers are kept
as Python ``int`` and strings as ``str``; nested maps become ``dict``.
"""

from __future__ import annotations

import struct
from typing import Dict, Union

BinKeyValues = Dict[str, Union[str, int, "BinKeyValues"]]

_TYPE_MAP = 0x00
_TYPE_STR = 0x01
_TYPE_INT = 0x02
_TYPE_END = 0x08


def _read_cstr(buf: bytes, pos: int) -> tuple[str, int]:
    end = buf.index(b"\x00", pos)
    return buf[pos:end].decode("utf-8", "replace"), end + 1


def _parse_map(buf: bytes, pos: int) -> tuple[BinKeyValues, int]:
    out: BinKeyValues = {}
    while True:
        tag = buf[pos]
        pos += 1
        if tag == _TYPE_END:
            return out, pos
        key, pos = _read_cstr(buf, pos)
        if tag == _TYPE_MAP:
            value, pos = _parse_map(buf, pos)
        elif tag == _TYPE_STR:
            value, pos = _read_cstr(buf, pos)
        elif tag == _TYPE_INT:
            (value,) = struct.unpack_from("<i", buf, pos)
            pos += 4
        else:
            raise ValueError(f"unsupported binary VDF tag 0x{tag:02x} at {pos}")
        out[key] = value


def loads(data: bytes) -> BinKeyValues:
    """Parse a binary KeyValues blob into a nested dict."""
    result, _ = _parse_map(data, 0)
    return result


def _dump_map(data: BinKeyValues) -> bytes:
    out = bytearray()
    for key, value in data.items():
        kb = str(key).encode("utf-8") + b"\x00"
        if isinstance(value, dict):
            out += bytes([_TYPE_MAP]) + kb + _dump_map(value)
        elif isinstance(value, bool):
            out += bytes([_TYPE_INT]) + kb + struct.pack("<i", int(value))
        elif isinstance(value, int):
            out += bytes([_TYPE_INT]) + kb + struct.pack("<i", value)
        else:
            out += bytes([_TYPE_STR]) + kb + str(value).encode("utf-8") + b"\x00"
    out += bytes([_TYPE_END])
    return bytes(out)


def dumps(data: BinKeyValues) -> bytes:
    """Serialize a nested dict back to a binary KeyValues blob."""
    return _dump_map(data)
