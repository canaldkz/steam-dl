"""Stage 3 -- poll ``appmanifest_<AppID>.acf`` until the download completes."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from ..errors import TimeoutError_
from ..logutil import get_logger
from ..steam.acf import AppState, read_app_state

log = get_logger()

ProgressCb = Callable[[AppState], None]


def wait_for_manifest(acf_path: Path, timeout: float, poll: float) -> None:
    """Block until the ``.acf`` first appears (Steam creates it lazily)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if acf_path.exists():
            log.info("stage3: appmanifest appeared: %s", acf_path.name)
            return
        time.sleep(min(poll, 2.0))
    raise TimeoutError_(
        f"appmanifest did not appear within {timeout:.0f}s: {acf_path}"
    )


def wait_until_installed(
    acf_path: Path,
    timeout: float,
    poll: float,
    *,
    on_progress: Optional[ProgressCb] = None,
) -> AppState:
    """Poll the manifest until StateFlags reports a completed install."""
    deadline = time.time() + timeout
    last_desc = ""
    while time.time() < deadline:
        state = read_app_state(acf_path)
        if state is not None:
            if on_progress:
                on_progress(state)
            desc = f"{state.describe_flags()} {state.progress * 100:5.1f}%"
            if desc != last_desc:
                log.info("stage3: %s", desc)
                last_desc = desc
            if state.is_fully_installed:
                log.info("stage3: fully installed")
                return state
        time.sleep(poll)
    raise TimeoutError_(f"download did not finish within {timeout:.0f}s")
