from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _state_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    d = root / ".data"
    d.mkdir(parents=True, exist_ok=True)
    return d / "rule_sync_state.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_sync_state() -> dict[str, Any]:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def save_sync_state(result: dict[str, Any], *, trigger: str = "manual") -> dict[str, Any]:
    previous = load_sync_state()
    prev_stable = previous.get("latestStable")
    latest = result.get("latestStable")
    entry = {
        "updatedAt": _utc_now(),
        "trigger": trigger,
        "latestStable": latest,
        "previousStable": prev_stable,
        "stableChanged": bool(prev_stable and latest and prev_stable != latest),
        "autoPublishEnabled": result.get("autoPublishEnabled"),
        "published": result.get("published") or [],
        "errors": result.get("errors") or [],
        "feedSync": result.get("feedSync") or [],
        "inboxSync": result.get("inboxSync") or [],
        "regression": result.get("regression") or [],
        "skipped": result.get("skipped") or [],
    }
    path = _state_path()
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry


def read_publish_log_tail(limit: int = 5) -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parent.parent / ".data" / "rule_publish_log.jsonl"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
