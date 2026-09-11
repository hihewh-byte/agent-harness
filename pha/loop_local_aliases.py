"""Local (gitignored) metric alias overrides from Loop approvals — Path B.

Writes under ``data/loop_local_aliases.json``. Never edits
``rules/health_intent_catalog.json``. Runtime ``catalog_metric_aliases`` merges
these so chat / intent routing picks them up on this machine only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PATH = _ROOT / "data" / "loop_local_aliases.json"
_LOCK = threading.Lock()


def local_aliases_path() -> Path:
    override = (os.environ.get("PHA_LOOP_LOCAL_ALIASES_PATH") or "").strip()
    if override:
        return Path(override)
    return _DEFAULT_PATH

_TOXIC_LATIN = frozenset(
    {
        "query",
        "cancel",
        "ok",
        "done",
        "save",
        "edit",
        "delete",
        "share",
        "close",
        "back",
        "next",
        "search",
        "filter",
        "settings",
    }
)

_SCHEMA = "pha.loop_local_aliases/v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_doc() -> dict[str, Any]:
    return {
        "schema": _SCHEMA,
        "updated_at": None,
        "metric_aliases": {},
        "history": [],
    }


def load_local_aliases() -> dict[str, Any]:
    path = local_aliases_path()
    if not path.is_file():
        return _empty_doc()
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("loop_local_aliases unreadable: %s", e)
        return _empty_doc()
    if not isinstance(doc, dict):
        return _empty_doc()
    aliases = doc.get("metric_aliases")
    if not isinstance(aliases, dict):
        doc["metric_aliases"] = {}
    return doc


def save_local_aliases(doc: dict[str, Any]) -> None:
    path = local_aliases_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = dict(doc)
    doc["schema"] = _SCHEMA
    doc["updated_at"] = _now_iso()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def local_aliases_for_metric(metric_key: str) -> list[str]:
    key = (metric_key or "").strip()
    if not key:
        return []
    raw = (load_local_aliases().get("metric_aliases") or {}).get(key) or []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        a = str(item or "").strip()
        if not a:
            continue
        low = a.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(a)
    return out


def local_alias_metric_keys() -> list[str]:
    return [str(k) for k in (load_local_aliases().get("metric_aliases") or {}).keys() if str(k).strip()]


def _known_metric_keys() -> set[str]:
    from pha.health_intent_catalog import load_health_intent_catalog

    keys = set((load_health_intent_catalog().get("metric_aliases") or {}).keys())
    try:
        from pha.wearable_metric_registry import catalog_keys_canonical

        keys |= set(catalog_keys_canonical() or [])
    except Exception:
        pass
    return {str(k) for k in keys if str(k).strip()}


def is_toxic_alias(alias: str) -> bool:
    a = (alias or "").strip()
    if not a:
        return True
    if len(a) <= 1:
        return True
    if a.isascii() and a.lower() in _TOXIC_LATIN:
        return True
    if a.isascii() and re.fullmatch(r"[A-Za-z]{1,3}", a):
        # Bare OCR crumbs like "HR" alone are ok for hrv? allow 2–3 letter known units later;
        # reject pure UI crumbs already in _TOXIC_LATIN; keep short medical tokens.
        if a.lower() in _TOXIC_LATIN:
            return True
    return False


def apply_proposal_aliases(
    proposal: dict[str, Any],
    *,
    approval_id: str = "",
    source: str = "loop_approve",
) -> dict[str, Any]:
    """Merge Tier-A ``accepted_catalog`` rows into local aliases. Returns apply report."""
    rows = proposal.get("accepted_catalog") or []
    if not isinstance(rows, list):
        rows = []
    known = _known_metric_keys()
    added: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    with _LOCK:
        doc = load_local_aliases()
        aliases: dict[str, list[str]] = {
            str(k): [str(x) for x in (v or [])]
            for k, v in (doc.get("metric_aliases") or {}).items()
            if isinstance(v, list)
        }
        for row in rows:
            if not isinstance(row, dict):
                continue
            mid = str(row.get("metric_id") or row.get("target") or "").strip()
            alias = str(row.get("alias") or "").strip()
            if not mid or not alias:
                skipped.append({"metric_id": mid, "alias": alias, "reason": "empty"})
                continue
            if mid not in known:
                skipped.append({"metric_id": mid, "alias": alias, "reason": "unknown_metric"})
                continue
            if is_toxic_alias(alias):
                skipped.append({"metric_id": mid, "alias": alias, "reason": "toxic"})
                continue
            bucket = aliases.setdefault(mid, [])
            if any(a.lower() == alias.lower() for a in bucket):
                skipped.append({"metric_id": mid, "alias": alias, "reason": "duplicate"})
                continue
            bucket.append(alias)
            added.append({"metric_id": mid, "alias": alias})

        doc["metric_aliases"] = aliases
        hist = list(doc.get("history") or [])
        hist.append(
            {
                "at": _now_iso(),
                "approval_id": approval_id,
                "source": source,
                "added": added,
                "skipped": skipped,
            }
        )
        doc["history"] = hist[-50:]
        save_local_aliases(doc)

    return {
        "ok": True,
        "added_n": len(added),
        "skipped_n": len(skipped),
        "added": added,
        "skipped": skipped,
        "path": str(local_aliases_path()),
        "catalog_repo_edited": False,
    }


def local_aliases_summary(*, limit: int = 20) -> dict[str, Any]:
    doc = load_local_aliases()
    aliases = doc.get("metric_aliases") or {}
    flat: list[str] = []
    for mid, items in sorted(aliases.items()):
        for a in items or []:
            flat.append(f"{mid} ← {a}")
    path = local_aliases_path()
    return {
        "updated_at": doc.get("updated_at"),
        "metric_n": len(aliases),
        "alias_n": len(flat),
        "lines": flat[:limit],
        "path": str(path) if path.is_file() else "",
    }


__all__ = [
    "apply_proposal_aliases",
    "is_toxic_alias",
    "load_local_aliases",
    "local_alias_metric_keys",
    "local_aliases_for_metric",
    "local_aliases_path",
    "local_aliases_summary",
    "save_local_aliases",
]
