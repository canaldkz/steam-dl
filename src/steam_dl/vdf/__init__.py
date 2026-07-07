"""Dependency-free Valve KeyValues (VDF) codecs.

Two on-disk formats are used by Steam:

* Text KeyValues -- ``config.vdf``, ``appmanifest_*.acf``, ``libraryfolders.vdf``.
* Binary KeyValues -- ``shortcuts.vdf`` and the app-info caches.

Both are implemented here without any third-party dependency so the tool can
run on a stock handheld image with only the Python standard library.
"""

from .text import dumps as text_dumps
from .text import loads as text_loads
from .binary import dumps as binary_dumps
from .binary import loads as binary_loads

__all__ = ["text_dumps", "text_loads", "binary_dumps", "binary_loads"]
