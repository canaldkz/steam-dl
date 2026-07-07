"""Reading and interpreting ``appmanifest_<AppID>.acf`` state.

The download watcher polls this file. ``StateFlags`` is a bitfield, not an
enumeration -- the values quoted in most guides (1026, 1042, ...) are just
common *combinations*. Relying on exact numbers is fragile, so we decode the
individual bits and additionally cross-check the byte counters.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..vdf import text_loads

# Individual StateFlags bits (see SteamKit EAppState).
STATE_UNINSTALLED = 1
STATE_UPDATE_REQUIRED = 2
STATE_FULLY_INSTALLED = 4
STATE_UPDATE_STARTED = 8
STATE_UNINSTALLING = 16
STATE_BACKUP_RUNNING = 32
STATE_RECONFIGURING = 64
STATE_VALIDATING = 128
STATE_ADDING_FILES = 256
STATE_PREALLOCATING = 512
STATE_DOWNLOADING = 1024
STATE_STAGING = 2048
STATE_COMMITTING = 4096
STATE_UPDATE_STOPPING = 8192

# Any of these bits means work is still in progress.
_IN_PROGRESS = (
    STATE_UPDATE_STARTED
    | STATE_UNINSTALLING
    | STATE_BACKUP_RUNNING
    | STATE_RECONFIGURING
    | STATE_VALIDATING
    | STATE_ADDING_FILES
    | STATE_PREALLOCATING
    | STATE_DOWNLOADING
    | STATE_STAGING
    | STATE_COMMITTING
    | STATE_UPDATE_STOPPING
)


@dataclass
class AppState:
    appid: int
    state_flags: int
    installdir: str
    bytes_downloaded: int
    bytes_to_download: int
    raw: dict

    @property
    def is_fully_installed(self) -> bool:
        """True only when installed *and* no in-progress bit remains.

        When byte counters are present we also require them to agree, which
        guards against the brief window where StateFlags already shows the
        installed bit but the final commit has not flushed.
        """
        if not (self.state_flags & STATE_FULLY_INSTALLED):
            return False
        if self.state_flags & _IN_PROGRESS:
            return False
        if self.bytes_to_download > 0:
            return self.bytes_downloaded >= self.bytes_to_download
        return True

    @property
    def progress(self) -> float:
        if self.bytes_to_download <= 0:
            return 1.0 if self.is_fully_installed else 0.0
        return min(1.0, self.bytes_downloaded / self.bytes_to_download)

    def describe_flags(self) -> str:
        names = []
        for bit, name in (
            (STATE_FULLY_INSTALLED, "installed"),
            (STATE_UPDATE_REQUIRED, "update-required"),
            (STATE_VALIDATING, "validating"),
            (STATE_PREALLOCATING, "preallocating"),
            (STATE_DOWNLOADING, "downloading"),
            (STATE_STAGING, "staging"),
            (STATE_COMMITTING, "committing"),
        ):
            if self.state_flags & bit:
                names.append(name)
        return "+".join(names) or f"0x{self.state_flags:x}"


def parse_acf(text: str) -> AppState:
    data = text_loads(text)
    app = data.get("AppState", {})
    if not isinstance(app, dict):
        raise ValueError("malformed .acf: no AppState block")

    def _int(key: str, default: int = 0) -> int:
        try:
            return int(str(app.get(key, default)).strip() or default)
        except (TypeError, ValueError):
            return default

    return AppState(
        appid=_int("appid"),
        state_flags=_int("StateFlags"),
        installdir=str(app.get("installdir", "")),
        bytes_downloaded=_int("BytesDownloaded"),
        bytes_to_download=_int("BytesToDownload"),
        raw=app,
    )


def read_app_state(path: Path) -> Optional[AppState]:
    """Return parsed state, or ``None`` if the file is absent/half-written."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    if not text.strip():
        return None
    try:
        return parse_acf(text)
    except ValueError:
        # Steam writes the file non-atomically; a torn read is expected.
        return None
