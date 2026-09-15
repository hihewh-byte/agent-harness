"""Live Loop A harvest for the fact-card approval block (no weekly cron).

Reads recent chat utterances, proposes phrase-level aliases for an existing
catalog key, and enqueues a pending approval. Never edits the repo catalog.
Unknown metrics and single Latin junk tokens are skipped.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pha.health_intent_catalog import (
    catalog_all_metric_keys,
    catalog_metric_aliases,
    health_intent_catalog_enabled,
    infer_metrics_from_message,
    is_weak_close_followup,
)
from pha.loop_keyword_conflicts import gate_1e_d_ocr_ui_junk
from pha.loop_local_aliases import is_toxic_alias, local_aliases_for_metric
from pha import loop_weekly as loop_weekly_mod

logger = logging.getLogger(__name__)

_LIVE_LOCK = threading.Lock()
_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9]+")
_MAX_ALIAS_CHARS = 48
_MIN_ALIAS_CHARS = 4
_MIN_LATIN_OVERLAP = 4


def live_harvest_enabled() -> bool:
    raw = (os.environ.get("PHA_LOOP_LIVE_HARVEST") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _max_pending() -> int:
    try:
        return max(1, min(int(os.environ.get("PHA_LOOP_LIVE_MAX_PENDING") or "5"), 12))
    except ValueError:
        return 5


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _normalize_alias(message: str) -> str:
    text = re.sub(r"\s+", " ", (message or "").strip())
    text = text.strip(" \t\n\"'“”‘’")
    if len(text) > _MAX_ALIAS_CHARS:
        text = text[:_MAX_ALIAS_CHARS].rstrip()
    return text


def _is_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _tokenize(text: str) -> list[str]:
    return [m.group(0) for m in _TOKEN_RE.finditer(text or "")]


def _latin_overlap(a: str, b: str) -> bool:
    x = (a or "").lower()
    y = (b or "").lower()
    if not x or not y:
        return False
    if x == y:
        return True
    if len(x) >= _MIN_LATIN_OVERLAP and len(y) >= _MIN_LATIN_OVERLAP:
        return x.startswith(y) or y.startswith(x)
    return False


def _canonical_catalog_key(raw: str) -> Optional[str]:
    key = (raw or "").strip()
    if not key:
        return None
    known = set(catalog_all_metric_keys())
    if key in known:
        return key
    try:
        from pha.wearable_metric_registry import catalog_key_for

        mapped = str(catalog_key_for(key) or "").strip()
    except Exception:
        mapped = ""
    if mapped and mapped in known:
        return mapped
    return None


def unique_metric_from_alias_overlap(message: str) -> Optional[str]:
    """A message token that maps to exactly one catalog key (shared stems skipped)."""
    token_keys: dict[str, set[str]] = {}
    for key in catalog_all_metric_keys():
        for alias in catalog_metric_aliases(key):
            for atok in _tokenize(str(alias)):
                if _is_cjk(atok):
                    if len(atok) < 2:
                        continue
                    token_keys.setdefault(atok, set()).add(key)
                    continue
                low = atok.lower()
                if len(low) < _MIN_LATIN_OVERLAP:
                    continue
                token_keys.setdefault(low, set()).add(key)
    exclusive: set[str] = set()
    for tok in _tokenize(message):
        keys: set[str] = set()
        if _is_cjk(tok):
            keys |= token_keys.get(tok, set())
        else:
            low = tok.lower()
            for atok, owners in token_keys.items():
                if _is_cjk(atok):
                    continue
                if _latin_overlap(atok, low):
                    keys |= owners
        if len(keys) == 1:
            exclusive |= keys
    if len(exclusive) == 1:
        return next(iter(exclusive))
    return None


def _already_known_alias(metric_id: str, alias: str) -> bool:
    want = (alias or "").strip().lower()
    if not want:
        return True
    for existing in catalog_metric_aliases(metric_id):
        if str(existing).strip().lower() == want:
            return True
    for existing in local_aliases_for_metric(metric_id):
        if str(existing).strip().lower() == want:
            return True
    return False


def _pending_pairs() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for doc in loop_weekly_mod.list_pending_approvals():
        for line in doc.get("aliases") or []:
            text = str(line or "")
            if "←" not in text:
                continue
            mid, alias = text.split("←", 1)
            pair = (mid.strip(), alias.strip().lower())
            if pair[0] and pair[1]:
                out.add(pair)
    return out


def consider_utterance(
    message: str,
    *,
    focus_metric: str = "",
    session_prior_metric: str = "",
) -> Optional[dict[str, str]]:
    """Return a phrase-level alias proposal, or None if Loop A must skip."""
    alias = _normalize_alias(message)
    if len(alias) < _MIN_ALIAS_CHARS:
        return None
    if is_weak_close_followup(alias):
        return None
    if alias.isascii() and " " not in alias:
        return None
    if is_toxic_alias(alias):
        return None
    if gate_1e_d_ocr_ui_junk(alias).errors():
        return None
    inferred = infer_metrics_from_message(alias)
    if inferred:
        return None
    metric = (
        unique_metric_from_alias_overlap(alias)
        or _canonical_catalog_key(session_prior_metric)
        or _canonical_catalog_key(focus_metric)
    )
    if not metric:
        return None
    if _already_known_alias(metric, alias):
        return None
    return {"metric_id": metric, "alias": alias, "source_message": alias}


def _write_live_proposal(row: dict[str, str]) -> Path:
    mid = row["metric_id"]
    alias = row["alias"]
    doc = {
        "schema": "pha.loop_proposal/v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": "4-alpha-live",
        "source": "live_chat",
        "accepted_catalog": [
            {
                "layer": "catalog",
                "target": mid,
                "alias": alias,
                "metric_id": mid,
                "signal": "live_alias_miss",
                "source_message": row.get("source_message") or alias,
            }
        ],
        "accepted_schema": [],
        "slot_candidates": [],
        "rejected": [],
        "patch_ops": [
            {
                "op": "add",
                "path": f"/metric_aliases/{mid}",
                "value": alias,
                "signal": "live_alias_miss",
                "source_message": row.get("source_message") or alias,
            }
        ],
        "counts": {"accepted_catalog": 1, "accepted_schema": 0, "slot_candidates": 0, "rejected": 0},
        "notes": "Live fact-card harvest. Phrase-level only. Human approve writes local aliases, not the repo catalog.",
    }
    folder = loop_weekly_mod.REPORTS_LOOP / "proposals"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"alias_proposal_live_{_now_stamp()}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def enqueue_live_proposal(row: dict[str, str]) -> Optional[dict[str, Any]]:
    mid = str(row.get("metric_id") or "").strip()
    alias = str(row.get("alias") or "").strip()
    if not mid or not alias:
        return None
    if (mid, alias.lower()) in _pending_pairs():
        return None
    if len(loop_weekly_mod.list_pending_approvals()) >= _max_pending():
        logger.info("loop live harvest skipped: pending cap")
        return None
    path = _write_live_proposal(row)
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not loop_weekly_mod.proposal_has_work(doc):
        return None
    return loop_weekly_mod.create_pending_approval(proposal_path=path, source="live_chat")


def sync_live_alias_approvals(user_id: str = "default") -> dict[str, Any]:
    """Scan recent chat and enqueue at most new phrase-level approvals."""
    result: dict[str, Any] = {"ok": True, "enabled": live_harvest_enabled(), "added": []}
    if not live_harvest_enabled() or not health_intent_catalog_enabled():
        result["skipped"] = True
        return result
    from pha.chat_storage import list_recent_user_messages
    from pha.session_turn_focus import get_session_turn_focus

    rows = list(reversed(list_recent_user_messages(user_id, limit=40)))
    session_prior: dict[str, str] = {}
    added: list[str] = []
    with _LIVE_LOCK:
        for msg in rows:
            text = (msg.content or "").strip()
            sid = msg.session_id
            inferred = infer_metrics_from_message(text)
            if len(inferred) == 1:
                session_prior[sid] = inferred[0]
                continue
            if len(inferred) > 1:
                continue
            focus = ""
            try:
                row = get_session_turn_focus(sid)
                if row is not None:
                    focus = str(getattr(row, "focus_metric", "") or "")
            except Exception:
                focus = ""
            proposal = consider_utterance(
                text,
                focus_metric=focus,
                session_prior_metric=session_prior.get(sid, ""),
            )
            if not proposal:
                continue
            pending = enqueue_live_proposal(proposal)
            if pending:
                added.append(str(pending.get("approval_id") or ""))
                session_prior[sid] = proposal["metric_id"]
    result["added"] = added
    result["added_n"] = len(added)
    return result


def schedule_live_alias_sync(user_id: str = "default") -> None:
    uid = (user_id or "default").strip() or "default"

    def _run() -> None:
        try:
            sync_live_alias_approvals(uid)
        except Exception:
            logger.exception("loop live harvest failed")

    threading.Thread(target=_run, name="pha-loop-live-harvest", daemon=True).start()


__all__ = [
    "consider_utterance",
    "enqueue_live_proposal",
    "live_harvest_enabled",
    "schedule_live_alias_sync",
    "sync_live_alias_approvals",
    "unique_metric_from_alias_overlap",
]
