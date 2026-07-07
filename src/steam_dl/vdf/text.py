"""Parser and serializer for the *text* Valve KeyValues format.

The grammar is small: a key is a quoted (or bare) token; it is followed either
by a value token (another string) or by a ``{ ... }`` block of nested pairs.
Line (``//``) comments and ``#base`` / ``#include`` directives are tolerated.

Order matters for round-tripping ``config.vdf`` so nested objects are returned
as ``dict`` which preserves insertion order on Python 3.7+.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Union

KeyValues = Dict[str, Union[str, "KeyValues"]]

_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t"}
_UNESCAPES = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}


def _tokenize(text: str) -> List[Tuple[str, str]]:
    tokens: List[Tuple[str, str]] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c in "{}":
            tokens.append(("brace", c))
            i += 1
            continue
        if c == '"':
            i += 1
            buf: List[str] = []
            while i < n:
                ch = text[i]
                if ch == "\\" and i + 1 < n:
                    buf.append(_UNESCAPES.get(text[i + 1], text[i + 1]))
                    i += 2
                    continue
                if ch == '"':
                    i += 1
                    break
                buf.append(ch)
                i += 1
            tokens.append(("str", "".join(buf)))
            continue
        # bare (unquoted) token -- e.g. #base directives
        start = i
        while i < n and text[i] not in ' \t\r\n"{}':
            i += 1
        tokens.append(("str", text[start:i]))
    return tokens


def loads(text: str) -> KeyValues:
    """Parse text KeyValues into an ordered nested dict."""
    tokens = _tokenize(text)
    pos = 0

    def parse_block(expect_close: bool) -> KeyValues:
        nonlocal pos
        out: KeyValues = {}
        while pos < len(tokens):
            kind, val = tokens[pos]
            if kind == "brace" and val == "}":
                if not expect_close:
                    raise ValueError("unexpected '}'")
                pos += 1
                return out
            if kind != "str":
                raise ValueError(f"expected key, got {kind!r}")
            key = val
            pos += 1
            if pos >= len(tokens):
                # trailing bare key with no value
                out[key] = ""
                return out
            nkind, nval = tokens[pos]
            if nkind == "brace" and nval == "{":
                pos += 1
                out[key] = parse_block(expect_close=True)
            elif nkind == "brace" and nval == "}":
                out[key] = ""
            else:
                out[key] = nval
                pos += 1
        if expect_close:
            raise ValueError("missing '}'")
        return out

    return parse_block(expect_close=False)


def _escape(s: str) -> str:
    return "".join(_ESCAPES.get(ch, ch) for ch in s)


def dumps(data: KeyValues, indent: str = "\t", _level: int = 0) -> str:
    """Serialize a nested dict back to text KeyValues."""
    pad = indent * _level
    lines: List[str] = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f'{pad}"{_escape(str(key))}"')
            lines.append(f"{pad}{{")
            lines.append(dumps(value, indent, _level + 1))
            lines.append(f"{pad}}}")
        else:
            lines.append(f'{pad}"{_escape(str(key))}"\t\t"{_escape(str(value))}"')
    return "\n".join(lines)
