"""Process management for Tax Agent API server."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from tax_agent.launcher.manifest import DEFAULT_HOST, DEFAULT_PORT

ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / ".data"
PIDFILE = DATA_DIR / "tax_agent.pid"
LOGFILE = DATA_DIR / "tax_agent.log"


def _origin(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    return f"http://{host}:{port}"


def is_healthy(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"{_origin(host, port)}/health", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def read_pid() -> int | None:
    if not PIDFILE.is_file():
        return None
    try:
        return int(PIDFILE.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def clear_stale_pid() -> None:
    pid = read_pid()
    if pid is not None and not _pid_alive(pid):
        PIDFILE.unlink(missing_ok=True)


def status(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict[str, object]:
    clear_stale_pid()
    pid = read_pid()
    running = pid is not None and _pid_alive(pid)
    healthy = is_healthy(host, port) if running or True else False
    return {
        "running": running,
        "healthy": healthy,
        "pid": pid,
        "origin": _origin(host, port),
        "pidFile": str(PIDFILE),
        "logFile": str(LOGFILE),
    }


def start(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    wait_ready: bool = True,
    timeout: float = 25.0,
) -> dict[str, object]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    clear_stale_pid()

    if is_healthy(host, port):
        st = status(host, port)
        st["message"] = "already running"
        return st

    pid = read_pid()
    if pid is not None and _pid_alive(pid):
        if wait_ready:
            _wait_health(host, port, timeout=timeout)
        return status(host, port)

    LOGFILE.parent.mkdir(parents=True, exist_ok=True)
    log_fp = open(LOGFILE, "a", encoding="utf-8")
    log_fp.write(f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    log_fp.flush()

    env = os.environ.copy()
    env.setdefault("TAX_AGENT_LLM_ENABLED", env.get("TAX_AGENT_LLM_ENABLED", "0"))

    proc = subprocess.Popen(
        [sys.executable, "-m", "tax_agent.api.server", "--host", host, "--port", str(port)],
        cwd=str(ROOT),
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env,
    )
    PIDFILE.write_text(str(proc.pid), encoding="utf-8")

    if wait_ready:
        ok = _wait_health(host, port, timeout=timeout)
        st = status(host, port)
        st["started"] = ok
        st["message"] = "started" if ok else "process started but health check timed out"
        return st

    st = status(host, port)
    st["message"] = "started (no wait)"
    return st


def _wait_health(host: str, port: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_healthy(host, port):
            return True
        time.sleep(0.35)
    return is_healthy(host, port)


def stop(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict[str, object]:
    clear_stale_pid()
    pid = read_pid()
    if pid is not None and _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        for _ in range(40):
            if not _pid_alive(pid):
                break
            time.sleep(0.15)
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    PIDFILE.unlink(missing_ok=True)
    st = status(host, port)
    st["message"] = "stopped"
    return st


def open_browser(path: str = "/app", host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    import webbrowser

    url = f"{_origin(host, port)}{path}"
    webbrowser.open(url)
