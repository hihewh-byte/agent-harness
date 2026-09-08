"""Last HealthKit ingest receipt (success or fail-closed). File under data/, no secrets."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def receipt_path() -> Path:
    override = (os.environ.get("PHA_HEALTHKIT_INGEST_LAST") or "").strip()
    if override:
        return Path(override)
    return _repo_root() / "data" / "healthkit_ingest_last.json"


def _read_all() -> dict[str, Any]:
    path = receipt_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_all(payload: dict[str, Any]) -> None:
    path = receipt_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix="hk-ingest-last-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def record_healthkit_ingest_receipt(
    user_id: str,
    *,
    ok: bool,
    kind: str,
    error: Optional[str] = None,
    inserted: int = 0,
    ignored: int = 0,
    dropped: int = 0,
    days_rebuilt: Optional[list[Any]] = None,
    audit: Optional[dict[str, Any]] = None,
    metrics: Optional[list[str]] = None,
    at: Optional[datetime] = None,
    pack_version: Optional[str] = None,
) -> dict[str, Any]:
    """Overwrite this user's last ingest receipt. Never stores tokens or raw bodies."""
    uid = (user_id or "default").strip() or "default"
    stamp = (at or datetime.now()).replace(microsecond=0).isoformat()
    entry: dict[str, Any] = {
        "ok": bool(ok),
        "at": stamp,
        "kind": (kind or "unknown").strip() or "unknown",
        "error": (error or None),
        "inserted": int(inserted),
        "ignored": int(ignored),
        "dropped": int(dropped),
        "days_rebuilt": [str(d) for d in (days_rebuilt or [])],
        "metrics": [str(m) for m in (metrics or []) if str(m).strip()],
        "pack_version": (pack_version or "").strip() or None,
    }
    if audit:
        # Keep a short audit slice for the phone / fact-card line.
        slim = {
            key: audit[key]
            for key in (
                "kept",
                "wake_day",
                "union_asleep_h",
                "stage_overlap",
                "sleep_period_h",
                "window",
            )
            if key in audit
        }
        if slim:
            entry["audit"] = slim
    all_rows = _read_all()
    all_rows[uid] = entry
    _write_all(all_rows)
    return entry


def load_healthkit_ingest_last(user_id: str = "default") -> dict[str, Any]:
    uid = (user_id or "default").strip() or "default"
    entry = _read_all().get(uid)
    if not isinstance(entry, dict):
        return {
            "user_id": uid,
            "ok": None,
            "at": None,
            "kind": None,
            "error": None,
            "message": "no_ingest_yet",
        }
    out = dict(entry)
    out["user_id"] = uid
    return out


__all__ = [
    "load_healthkit_ingest_last",
    "receipt_path",
    "record_healthkit_ingest_receipt",
]
