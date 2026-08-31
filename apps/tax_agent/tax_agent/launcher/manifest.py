"""Versioned launcher ↔ API contract (stable across agent iterations)."""

from __future__ import annotations

LAUNCHER_VERSION = "1.0.0"
API_VERSION = "v1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8790

LAUNCHER_MANIFEST: dict[str, object] = {
    "launcherVersion": LAUNCHER_VERSION,
    "apiVersion": API_VERSION,
    "defaultOrigin": f"http://{DEFAULT_HOST}:{DEFAULT_PORT}",
    "pages": {
        "control": "/app",
        "advisory": "/",
    },
    "endpoints": {
        "health": "/health",
        "launcherStatus": f"/api/{API_VERSION}/launcher/status",
        "rulesStatus": "/rules/status",
        "upload": "/tax/upload",
        "compute": "/tax/compute",
        "chat": "/tax/chat",
        "selfcheck": f"/api/{API_VERSION}/ops/selfcheck",
    },
    "cliReplaced": [
        "tax-agent-api → tax-agent start",
        "scripts/run_all_selfchecks.py → tax-agent selfcheck (or /app UI)",
        "open browser → tax-agent open",
        "one-shot → tax-agent app",
    ],
}
