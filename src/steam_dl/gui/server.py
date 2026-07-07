"""Local web server exposing the install pipeline as a JSON API.

Built entirely on the standard library so it runs on a stock handheld image.
The browser is the GUI: open the served page on the device's touchscreen (or
from a phone on the same network with ``--host 0.0.0.0``). Long-running
installs run in a background thread; their log output is captured per-job and
polled by the page.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from .. import bundle, pipeline
from ..config import Config, load_config
from ..logutil import get_logger, setup_logging
from ..models import Depot, GameSpec
from ..steam import applist, paths

log = get_logger()

_HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
_UPLOAD_DIR = Path.home() / ".cache" / "steam-dl" / "uploads"


# --------------------------------------------------------------------------
# Job manager: captures logging output per background install.
# --------------------------------------------------------------------------
@dataclass
class Job:
    id: str
    lines: List[str] = field(default_factory=list)
    done: bool = False
    error: Optional[str] = None
    result: Optional[dict] = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, line: str) -> None:
        with self.lock:
            self.lines.append(line)

    def snapshot(self, since: int) -> dict:
        with self.lock:
            return {
                "lines": self.lines[since:],
                "next": len(self.lines),
                "done": self.done,
                "error": self.error,
                "result": self.result,
            }


class _JobRegistry:
    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._local = threading.local()

    def create(self) -> Job:
        job = Job(id=uuid.uuid4().hex[:12])
        self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    # thread-local binding so the log handler knows which job to write to
    def bind(self, job: Job) -> None:
        self._local.job = job

    def current(self) -> Optional[Job]:
        return getattr(self._local, "job", None)


JOBS = _JobRegistry()


class _JobLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        job = JOBS.current()
        if job is not None:
            job.append(self.format(record))


def _install_log_capture() -> None:
    handler = _JobLogHandler()
    handler.setFormatter(logging.Formatter("%(levelname)-7s %(message)s"))
    get_logger().addHandler(handler)


# --------------------------------------------------------------------------
# Spec building + install worker
# --------------------------------------------------------------------------
def _build_spec_and_source(payload: dict):
    """Return (GameSpec, manifest_source, ingested_or_None) from a request."""
    ingested = None
    bundle_path = payload.get("bundle_path")
    if bundle_path:
        ingested = bundle.ingest(Path(bundle_path), name=payload.get("name") or None)
        spec = ingested.spec
        if payload.get("exe"):
            spec.executable = payload["exe"]
        if payload.get("install_dir"):
            spec.install_dir = payload["install_dir"]
        if payload.get("launch_options"):
            spec.launch_options = payload["launch_options"]
        manifest_source = ingested.manifest_dir
    else:
        depots = [
            Depot(
                depot_id=int(d["id"]),
                key=(d.get("key") or None),
                manifest_id=(str(d["manifest"]) if d.get("manifest") else None),
            )
            for d in payload.get("depots", [])
            if str(d.get("id", "")).strip()
        ]
        spec = GameSpec(
            appid=int(payload["appid"]),
            name=payload.get("name") or f"App {payload['appid']}",
            depots=depots,
            executable=payload.get("exe") or None,
            install_dir=payload.get("install_dir") or None,
            launch_options=payload.get("launch_options") or "",
        )
        manifest_source = None
    return spec, manifest_source, ingested


def _config_from_payload(base: Config, payload: dict) -> Config:
    over = {
        "backend": payload.get("backend"),
        "prefix_name": payload.get("prefix"),
        "proton_tool": payload.get("proton"),
        "user_id": payload.get("user_id"),
    }
    if payload.get("goldberg_dir"):
        over["goldberg_dir"] = Path(payload["goldberg_dir"]).expanduser()
    cfg = base.merged(**over)
    cfg = cfg.merged(
        dry_run=bool(payload.get("dry_run")),
        add_to_steam=not payload.get("no_steam"),
        patch_drm=not payload.get("no_drm"),
    )
    return cfg


def _run_install(job: Job, base_cfg: Config, payload: dict) -> None:
    JOBS.bind(job)
    ingested = None
    try:
        spec, manifest_source, ingested = _build_spec_and_source(payload)
        cfg = _config_from_payload(base_cfg, payload)
        result = pipeline.run(spec, cfg, manifest_source=manifest_source)
        job.result = {
            "game_dir": str(result.game_dir),
            "exe_path": str(result.exe_path),
            "shortcut_appid": result.shortcut_appid,
            "patched_dlls": len(result.patched_dlls),
        }
    except Exception as exc:  # surface any failure to the UI
        job.error = f"{type(exc).__name__}: {exc}"
        job.append(f"ERROR   {job.error}")
    finally:
        if ingested is not None:
            ingested.cleanup()
        job.done = True


# --------------------------------------------------------------------------
# HTTP handler
# --------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    base_cfg: Config = Config()

    def log_message(self, *args) -> None:  # silence default access log
        pass

    # -- helpers --
    def _send_json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    # -- routing --
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)
        try:
            if route in ("/", "/index.html"):
                self._send_html()
            elif route == "/api/env":
                self._send_json(_env_info(self.base_cfg))
            elif route == "/api/search":
                q = (query.get("q") or [""])[0]
                matches = applist.search(q) if q else []
                self._send_json([{"appid": m.appid, "name": m.name} for m in matches])
            elif route == "/api/job":
                job = JOBS.get((query.get("id") or [""])[0])
                if job is None:
                    self._send_json({"error": "unknown job"}, 404)
                else:
                    since = int((query.get("since") or ["0"])[0])
                    self._send_json(job.snapshot(since))
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as exc:  # never 500 with an empty body
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        try:
            if route == "/api/upload":
                self._handle_upload()
            elif route == "/api/install":
                payload = json.loads(self._read_body() or b"{}")
                job = JOBS.create()
                threading.Thread(
                    target=_run_install,
                    args=(job, self.base_cfg, payload),
                    daemon=True,
                ).start()
                self._send_json({"job_id": job.id})
            else:
                self._send_json({"error": "not found"}, 404)
        except Exception as exc:
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 500)

    def _handle_upload(self) -> None:
        name = self.headers.get("X-Filename", "bundle.bin")
        safe = Path(name).name  # strip any path components
        _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = _UPLOAD_DIR / safe
        dest.write_bytes(self._read_body())
        self._send_json({"path": str(dest), "name": safe})

    def _send_html(self) -> None:
        body = _HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _env_info(cfg: Config) -> dict:
    root = paths.native_steam_root()
    uid = paths.detect_user_id(root, cfg.user_id) if root else None
    layout = paths.portproton_layout(cfg.prefix_name)
    return {
        "steam_root": str(root) if root else None,
        "user_id": uid,
        "prefix": str(layout.prefix_root),
        "prefix_exists": layout.prefix_root.is_dir(),
        "steamtools_exists": layout.steamtools_dir.is_dir(),
        "games_dir": str(cfg.games_dir),
        "backend": cfg.backend,
        "prefix_name": cfg.prefix_name,
        "proton_tool": cfg.proton_tool,
        "goldberg_dir": str(cfg.goldberg_dir) if cfg.goldberg_dir else "",
    }


def serve(
    host: str = "127.0.0.1",
    port: int = 8756,
    *,
    config: Optional[Path] = None,
    open_browser: bool = True,
) -> None:
    setup_logging(verbose=False)
    _install_log_capture()
    _Handler.base_cfg = load_config(config)

    httpd = ThreadingHTTPServer((host, port), _Handler)
    url = f"http://{host if host != '0.0.0.0' else 'localhost'}:{port}/"
    log.info("steam-dl GUI at %s  (Ctrl-C to stop)", url)
    if open_browser:
        threading.Thread(target=lambda: (time.sleep(0.5), webbrowser.open(url)), daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
    finally:
        httpd.server_close()
