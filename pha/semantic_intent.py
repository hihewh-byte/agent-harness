"""Stage 2 — gated semantic intent proposal for zero-entity wearable turns.

Proposer (local LLM) only *proposes* registry metric ids with a verbatim
evidence span; the deterministic gate here decides:

  adopt   — every proposed metric has its own literal evidence span in the
            message (≤ ``max_adopt_metrics``); ids are adopted for this turn only
  clarify — one evidence span maps to several metrics, or too many metrics
  none    — feeling/symptom/other, no surviving evidence, proposer failure

Adoption is a turn-scoped contextvar keyed by the exact message text; the
registry/scope resolvers consult it only when their own token resolution is
empty. The user message is never rewritten. Spec: ``rules/semantic_intent_spec.json``.
"""

from __future__ import annotations

import contextvars
import functools
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_SPEC_PATH = Path(__file__).resolve().parent.parent / "rules" / "semantic_intent_spec.json"

METRIC_PICK_KIND = "metric_pick"
METRIC_PICK_ACTION = "metric_pick"

_ADOPTION: contextvars.ContextVar[Optional[tuple[str, tuple[str, ...]]]] = contextvars.ContextVar(
    "pha_semantic_adoption", default=None
)


def semantic_intent_mode() -> str:
    raw = (os.environ.get("PHA_SEMANTIC_INTENT") or "off").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return "on"
    if raw == "shadow":
        return "shadow"
    return "off"


@functools.lru_cache(maxsize=1)
def load_semantic_intent_spec() -> dict[str, Any]:
    with _SPEC_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------- turn adoption


def _msg_key(message: str) -> str:
    return (message or "").strip()


def set_turn_adoption(message: str, metric_ids: tuple[str, ...] | list[str]) -> contextvars.Token:
    return _ADOPTION.set((_msg_key(message), tuple(metric_ids)))


def reset_turn_adoption(token: contextvars.Token) -> None:
    _ADOPTION.reset(token)


def adopted_metric_ids_for(message: str) -> tuple[str, ...]:
    cur = _ADOPTION.get()
    if not cur or not message:
        return ()
    key, ids = cur
    return ids if key == _msg_key(message) else ()


# --------------------------------------------------------------------------- metric enum


def eligible_metric_rows() -> list[dict[str, str]]:
    """Chat-resolvable registry metrics (non-hidden, with catalog key)."""
    from pha.wearable_metric_registry import list_metric_entries

    rows: list[dict[str, str]] = []
    for m in list_metric_entries():
        cat = m.get("catalog") or {}
        if cat.get("hidden") or not str(cat.get("key") or "").strip():
            continue
        ui = m.get("ui") or {}
        rows.append(
            {
                "metric_id": str(m["metric_id"]),
                "label_zh": str(ui.get("label_zh") or cat.get("label_zh") or m["metric_id"]),
                "label_en": str(ui.get("label_en") or cat.get("label_en") or m["metric_id"]),
                "group": str(ui.get("group_zh") or ""),
            }
        )
    return rows


def metric_label(metric_id: str, *, locale: str | None = None) -> str:
    for row in eligible_metric_rows():
        if row["metric_id"] == metric_id:
            return row["label_en"] if (locale or "").lower() == "en" else row["label_zh"]
    return metric_id


# --------------------------------------------------------------------------- proposer


def _proposal_schema(metric_ids: list[str], max_metrics: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["metric_query", "feeling_or_symptom", "other"]},
            "metrics": {
                "type": "array",
                "maxItems": max_metrics,
                "items": {
                    "type": "object",
                    "properties": {
                        "metric_id": {"type": "string", "enum": metric_ids},
                        "evidence": {"type": "string"},
                    },
                    "required": ["metric_id", "evidence"],
                },
            },
        },
        "required": ["kind", "metrics"],
    }


def _listing(rows: list[dict[str, str]]) -> str:
    return "\n".join(
        f"- {r['metric_id']}: {r['label_zh']} / {r['label_en']}" + (f" ({r['group']})" if r["group"] else "")
        for r in rows
    )


def _ollama_json(spec: dict[str, Any], model: str, schema: dict[str, Any], user_content: str) -> dict[str, Any]:
    import httpx

    body: dict[str, Any] = {
        "model": model,
        "stream": False,
        "keep_alive": spec.get("keep_alive", "30m"),
        "format": schema,
        "options": {"temperature": float(spec.get("temperature") or 0)},
        "messages": [
            {"role": "system", "content": spec["system"]},
            {"role": "user", "content": user_content},
        ],
    }
    base = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    resp = httpx.post(f"{base}/api/chat", json=body, timeout=float(spec.get("timeout_seconds") or 20))
    resp.raise_for_status()
    return json.loads(((resp.json() or {}).get("message") or {}).get("content") or "{}")


def _use_model(spec: dict[str, Any], model: str | None) -> str:
    return model or os.environ.get("PHA_SEMANTIC_INTENT_MODEL") or spec["model"]


def verify_metric(message: str, metric_id: str, evidence: str, *, model: str | None = None) -> dict[str, Any]:
    """Contrastive re-pick among the proposed metric, its registry group siblings and 'none'."""
    spec = load_semantic_intent_spec()
    rows = eligible_metric_rows()
    group = next((r["group"] for r in rows if r["metric_id"] == metric_id), "")
    options = [r for r in rows if r["metric_id"] == metric_id or (group and r["group"] == group)]
    ids = [r["metric_id"] for r in options] + ["none"]
    schema = {
        "type": "object",
        "properties": {"metric_id": {"type": "string", "enum": ids}},
        "required": ["metric_id"],
    }
    prompt = (
        f"{spec['verify_instruction']}\n\nOptions:\n{_listing(options)}\n- none: none of these\n\n"
        f"Message: {message}\nPhrase: {evidence}"
    )
    t0 = time.perf_counter()
    out: dict[str, Any] = {"options": ids}
    try:
        out["metric_id"] = str(_ollama_json(spec, _use_model(spec, model), schema, prompt).get("metric_id") or "none")
    except Exception as exc:  # noqa: BLE001
        out["metric_id"] = "none"
        out["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    out["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return out


def propose(message: str, *, model: str | None = None) -> dict[str, Any]:
    """Call the local proposer. Never raises; ``error`` set on failure."""
    spec = load_semantic_intent_spec()
    rows = eligible_metric_rows()
    ids = [r["metric_id"] for r in rows]
    use_model = _use_model(spec, model)
    t0 = time.perf_counter()
    out: dict[str, Any] = {"model": use_model, "kind": "other", "metrics": []}
    try:
        doc = _ollama_json(
            spec,
            use_model,
            _proposal_schema(ids, int(spec.get("max_adopt_metrics") or 3)),
            f"{spec['instruction']}\n\nMetrics:\n{_listing(rows)}\n\nMessage: {message}",
        )
        out["kind"] = str(doc.get("kind") or "other")
        out["metrics"] = [
            {"metric_id": str(m.get("metric_id") or ""), "evidence": str(m.get("evidence") or "")}
            for m in (doc.get("metrics") or [])
            if isinstance(m, dict)
        ]
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
    out["latency_ms"] = int((time.perf_counter() - t0) * 1000)
    return out


# --------------------------------------------------------------------------- gate


@dataclass
class SemanticDecision:
    action: str  # adopt | clarify | none
    metric_ids: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def as_report(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "metricIds": list(self.metric_ids),
            "candidates": list(self.candidates),
            "reasons": list(self.reasons),
        }


def _evidence_in_message(evidence: str, message: str) -> bool:
    ev = (evidence or "").strip()
    if not ev:
        return False
    if ev.isascii():
        return ev.lower() in (message or "").lower()
    return ev in (message or "")


def _evidence_long_enough(evidence: str, spec: dict[str, Any]) -> bool:
    ev = (evidence or "").strip()
    if ev.isascii():
        return len(ev) >= int(spec.get("min_evidence_len_ascii") or 3)
    return len(ev) >= int(spec.get("min_evidence_len_cjk") or 2)


def _evidence_only_modifiers(evidence: str) -> bool:
    """Time / aggregation words alone are slots, not metric evidence (reuses 1E-a token lists)."""
    from pha.loop_keyword_conflicts import strip_dynamic_modifiers

    core, _slots = strip_dynamic_modifiers(evidence)
    return not (core or "").strip()


def gate_proposal(message: str, proposal: dict[str, Any], spec: dict[str, Any] | None = None) -> SemanticDecision:
    spec = spec or load_semantic_intent_spec()
    if proposal.get("error"):
        return SemanticDecision("none", reasons=[f"proposer_error:{proposal['error'][:80]}"])
    kind = str(proposal.get("kind") or "other")
    if kind != "metric_query":
        return SemanticDecision("none", reasons=[f"kind:{kind}"])

    eligible = {r["metric_id"] for r in eligible_metric_rows()}
    reasons: list[str] = []
    by_evidence: dict[str, list[str]] = {}
    for m in proposal.get("metrics") or []:
        mid, ev = str(m.get("metric_id") or ""), str(m.get("evidence") or "").strip()
        if mid not in eligible:
            reasons.append(f"not_eligible:{mid}")
            continue
        if not _evidence_in_message(ev, message):
            reasons.append(f"evidence_not_verbatim:{mid}")
            continue
        if not _evidence_long_enough(ev, spec):
            reasons.append(f"evidence_too_short:{mid}")
            continue
        if _evidence_only_modifiers(ev):
            reasons.append(f"evidence_modifier_only:{mid}")
            continue
        bucket = by_evidence.setdefault(ev.lower(), [])
        if mid not in bucket:
            bucket.append(mid)

    survivors: list[str] = []
    for mids in by_evidence.values():
        for mid in mids:
            if mid not in survivors:
                survivors.append(mid)
    if not survivors:
        return SemanticDecision("none", reasons=reasons or ["no_metrics"])

    shared = [mids for mids in by_evidence.values() if len(mids) > 1]
    if shared:
        cap = int(spec.get("max_clarify_choices") or 4)
        return SemanticDecision("clarify", candidates=survivors[:cap], reasons=reasons + ["shared_evidence"])
    if len(survivors) > int(spec.get("max_adopt_metrics") or 3):
        cap = int(spec.get("max_clarify_choices") or 4)
        return SemanticDecision("clarify", candidates=survivors[:cap], reasons=reasons + ["too_many_metrics"])
    return SemanticDecision("adopt", metric_ids=survivors, reasons=reasons)


# --------------------------------------------------------------------------- eligibility


def needs_semantic_proposal(user_id: str, message: str) -> bool:
    """Zero wearable entities by tokens, not casual, not a lab question."""
    msg = (message or "").strip()
    if not msg or semantic_intent_mode() == "off":
        return False
    from pha.health_intent_catalog import message_has_lab_marker
    from pha.intent_gates import user_message_is_casual
    from pha.ledger_passthrough_lookup import _named_registry_metric_ids, match_ledger_passthrough_types

    if user_message_is_casual(msg) or message_has_lab_marker(msg):
        return False
    if _named_registry_metric_ids(msg):
        return False
    return not match_ledger_passthrough_types(user_id, msg)


# --------------------------------------------------------------------------- clarify


def build_metric_pick_scope(message: str, candidates: list[str], *, locale: str | None = None):
    from pha.health_intent_catalog import catalog_clarify_kind
    from pha.health_turn_resolver import HealthTurnScope

    cfg = catalog_clarify_kind(METRIC_PICK_KIND)
    en = (locale or "").lower() == "en"
    prompt = str(cfg.get("prompt_template_en" if en else "prompt_template") or "")
    choices: list[dict[str, Any]] = [
        {
            "id": f"{METRIC_PICK_ACTION}:{mid}",
            "label": metric_label(mid, locale=locale),
            "payload": {"action": METRIC_PICK_ACTION, "metric_id": mid, "original_message": message},
        }
        for mid in candidates
    ]
    none_label = str(cfg.get("none_label_en" if en else "none_label") or "")
    if none_label:
        choices.append(
            {
                "id": f"{METRIC_PICK_ACTION}:none",
                "label": none_label,
                "payload": {"action": METRIC_PICK_ACTION, "metric_id": "", "original_message": message},
            }
        )
    return HealthTurnScope(
        metric_source="semantic_clarify",
        needs_clarification=True,
        clarify_kind=METRIC_PICK_KIND,
        clarify_prompt=prompt,
        clarify_choices=choices,
    )


@dataclass
class SemanticTurnResult:
    mode: str
    proposal: dict[str, Any]
    decision: SemanticDecision

    def as_report(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "model": self.proposal.get("model"),
            "latencyMs": self.proposal.get("latency_ms"),
            "kind": self.proposal.get("kind"),
            "proposed": list(self.proposal.get("metrics") or []),
            "verify": list(self.proposal.get("verify") or []),
            "error": self.proposal.get("error") or "",
            **self.decision.as_report(),
        }


def verify_decision(
    message: str,
    proposal: dict[str, Any],
    decision: SemanticDecision,
    *,
    model: str | None = None,
) -> SemanticDecision:
    """Adopt only metrics the contrastive re-pick confirms; a sibling re-pick → clarify; none → drop."""
    if decision.action != "adopt":
        return decision
    evidence = {str(m.get("metric_id")): str(m.get("evidence") or "") for m in proposal.get("metrics") or []}
    kept: list[str] = []
    contested: list[str] = []
    reasons = list(decision.reasons)
    checks: list[dict[str, Any]] = []
    for mid in decision.metric_ids:
        v = verify_metric(message, mid, evidence.get(mid, ""), model=model)
        checks.append({"metric_id": mid, "repick": v["metric_id"], "latency_ms": v["latency_ms"]})
        if v["metric_id"] == mid:
            kept.append(mid)
        elif v["metric_id"] == "none":
            reasons.append(f"verify_none:{mid}")
        else:
            reasons.append(f"verify_switch:{mid}->{v['metric_id']}")
            contested.extend(x for x in (mid, v["metric_id"]) if x not in contested)
    proposal["verify"] = checks
    if contested:
        cands = kept + [m for m in contested if m not in kept]
        cap = int(load_semantic_intent_spec().get("max_clarify_choices") or 4)
        return SemanticDecision("clarify", candidates=cands[:cap], reasons=reasons)
    if not kept:
        return SemanticDecision("none", reasons=reasons)
    return SemanticDecision("adopt", metric_ids=kept, reasons=reasons)


def run_semantic_proposal(user_id: str, message: str) -> SemanticTurnResult | None:
    """Proposer + gate (+ contrastive verify) for a zero-entity turn; None when not eligible or mode off."""
    if not needs_semantic_proposal(user_id, message):
        return None
    proposal = propose(message)
    decision = gate_proposal(message, proposal)
    if load_semantic_intent_spec().get("verify_adopt"):
        decision = verify_decision(message, proposal, decision)
    return SemanticTurnResult(semantic_intent_mode(), proposal, decision)


def metric_pick_replay(session_id: str, choice_id: str | None) -> tuple[str, str] | None:
    """(original_message, metric_id) for a metric_pick chip click; metric_id '' = none-of-these."""
    cid = (choice_id or "").strip()
    if semantic_intent_mode() != "on" or not cid.startswith(f"{METRIC_PICK_ACTION}:"):
        return None
    from pha.clarify_turns import clarify_turns_enabled, resolve_scope_from_clarify_choice

    if not clarify_turns_enabled():
        return None
    try:
        scope = resolve_scope_from_clarify_choice(cid, session_id=session_id)
    except (TypeError, ValueError):
        return None
    pick = metric_pick_from_scope(scope)
    if not pick or not pick[0].strip():
        return None
    original, mid = pick
    eligible = {r["metric_id"] for r in eligible_metric_rows()}
    return original.strip(), (mid if mid in eligible else "")


def metric_pick_from_scope(scope: Any) -> tuple[str, str] | None:
    """(original_message, metric_id) when a resolved clarify scope is a metric pick."""
    if scope is None or getattr(scope, "metric_source", "") != "semantic_pick":
        return None
    picked = getattr(scope, "clarify_choices", None) or []
    if not picked:
        return None
    payload = dict(picked[0].get("payload") or {})
    return str(payload.get("original_message") or ""), str(payload.get("metric_id") or "")


__all__ = [
    "METRIC_PICK_ACTION",
    "METRIC_PICK_KIND",
    "SemanticDecision",
    "SemanticTurnResult",
    "adopted_metric_ids_for",
    "build_metric_pick_scope",
    "eligible_metric_rows",
    "gate_proposal",
    "load_semantic_intent_spec",
    "metric_label",
    "metric_pick_from_scope",
    "metric_pick_replay",
    "needs_semantic_proposal",
    "propose",
    "reset_turn_adoption",
    "run_semantic_proposal",
    "semantic_intent_mode",
    "set_turn_adoption",
    "verify_decision",
    "verify_metric",
]
