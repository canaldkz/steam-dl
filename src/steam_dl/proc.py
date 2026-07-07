"""Process helpers: streaming subprocess launch and native-Steam control."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from typing import Callable, List, Optional

from .logutil import get_logger

log = get_logger()


def stream_process(
    cmd: List[str],
    *,
    on_line: Optional[Callable[[str], None]] = None,
    env: Optional[dict] = None,
) -> subprocess.Popen:
    """Launch ``cmd`` and pump merged stdout/stderr to ``on_line`` in a thread."""
    log.debug("exec: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
        env=env,
    )

    def _pump() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            if on_line:
                on_line(line)
            else:
                log.debug("child: %s", line)

    threading.Thread(target=_pump, daemon=True).start()
    return proc


def pgrep(pattern: str) -> List[int]:
    """Return PIDs whose command matches ``pattern`` (best-effort)."""
    try:
        out = subprocess.check_output(["pgrep", "-x", pattern], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [int(x) for x in out.split()]


def wait_for_exit(pids: List[int], timeout: float) -> bool:
    """Block until all ``pids`` are gone or ``timeout`` elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not any(_alive(pid) for pid in pids):
            return True
        time.sleep(0.5)
    return not any(_alive(pid) for pid in pids)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def terminate(pids: List[int], timeout: float = 20.0) -> None:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    if not wait_for_exit(pids, timeout):
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
