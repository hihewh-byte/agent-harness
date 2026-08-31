"""Tax harness build report — v1 可观测（对照 PHA harness_report）。"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPORT_SCHEMA = "tax.harness_report/v2"


def harness_debug_enabled() -> bool:
    return os.environ.get("TAX_HARNESS_DEBUG", "0").strip() in ("1", "true", "yes", "on")


def harness_report_enabled() -> bool:
    if harness_debug_enabled():
        return True
    return os.environ.get("TAX_HARNESS_REPORT", "1").strip() in ("1", "true", "yes", "on")


def _sha_prefix(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def compute_plan_vs_actual(
    plan: Any,
    *,
    mode: str,
    tools_executed: list[str] | None = None,
    slot_contents: dict[str, str] | None = None,
    tool_error: str | None = None,
) -> list[str]:
    """Machine-diff plan contract vs runtime (PHA ``compute_plan_vs_actual`` tax twin).

    Returns sorted unique diff codes. No user PII — codes only.
    """
    diffs: list[str] = []
    tools_executed = list(tools_executed or [])
    allowed = set(getattr(plan, "tools_allowed", ()) or [])
    forbidden = set(getattr(plan, "forbidden", ()) or [])
    slot_contents = slot_contents or {}

    for t in tools_executed:
        if t not in allowed:
            diffs.append(f"tool_not_allowed:{t}")
            # keep legacy warning string for older consumers
            diffs.append(f"tool_not_in_allowlist:{t}")

    if "LLM_COMPUTE" in forbidden and any(
        t in ("compute", "run_compute", "llm_compute") for t in tools_executed
    ):
        diffs.append("forbidden_tool_llm_compute")

    if tool_error:
        diffs.append("tool_error")

    # Soft presence: planned Tier0 slots that were explicitly tracked as empty
    for slot in getattr(plan, "slots_tier0", ()) or ():
        if slot in ("MASTER_ANCHOR", "TASK"):
            continue
        if slot in slot_contents and not (slot_contents.get(slot) or "").strip():
            diffs.append(f"missing_tier0_slot:{slot}")

    # Deduplicate while preferring canonical tool_not_allowed over legacy twin
    out = sorted(set(diffs))
    if any(x.startswith("tool_not_allowed:") for x in out):
        out = [x for x in out if not x.startswith("tool_not_in_allowlist:")]
    return out


def build_harness_report(
    *,
    session_id: str,
    user_message: str,
    plan: Any,
    meta: dict[str, Any],
    mode: str,
    harness_block_len: int = 0,
    turn_focus: dict[str, Any] | None = None,
    action: str = "none",
    slot_contents: dict[str, str] | None = None,
    tier0_integrity: dict[str, Any] | None = None,
    turn_phases: list[str] | None = None,
) -> dict[str, Any]:
    """构建单轮 Harness 报告（plan vs runtime）。"""
    tools_executed = list(meta.get("toolsExecuted") or [])
    tools_allowed = list(getattr(plan, "tools_allowed", []) or [])
    composer_raw = (meta.get("runtime") or {}).get("composer") or meta.get("composer") or {}
    numerics = composer_raw.get("numericsAudit") or meta.get("numericsAudit") or {}
    warnings: list[str] = list(numerics.get("warnings") or [])

    integrity = dict(tier0_integrity or meta.get("tier0Integrity") or {})
    if integrity:
        from tax_agent.harness_tier0_assembly import tier0_integrity_plan_diffs

        for code in tier0_integrity_plan_diffs(integrity):
            if code not in warnings:
                warnings.append(code)

    plan_vs_actual = compute_plan_vs_actual(
        plan,
        mode=mode,
        tools_executed=tools_executed,
        slot_contents=slot_contents or meta.get("slotContents") or {},
        tool_error=str(meta["toolError"])[:120] if meta.get("toolError") else None,
    )
    if integrity:
        from tax_agent.harness_tier0_assembly import tier0_integrity_plan_diffs

        for code in tier0_integrity_plan_diffs(integrity):
            if code not in plan_vs_actual:
                plan_vs_actual.append(code)
        plan_vs_actual = sorted(set(plan_vs_actual))

    # Surface diffs in warnings for backward-compatible dashboards
    for code in plan_vs_actual:
        if code not in warnings:
            warnings.append(code)
    if meta.get("toolError") and f"tool_error:{str(meta['toolError'])[:120]}" not in warnings:
        warnings.append(f"tool_error:{str(meta['toolError'])[:120]}")

    phases = list(turn_phases or meta.get("turnPhases") or [])

    return {
        "schema": REPORT_SCHEMA,
        "ts": datetime.now(timezone.utc).isoformat(),
        "turnId": f"{session_id}:{_sha_prefix(user_message)}",
        "sessionId": session_id,
        "userMessageLen": len(user_message or ""),
        "userMessageSha": _sha_prefix(user_message),
        "mode": mode,
        "action": action,
        "plan": {
            "profile": getattr(plan, "profile", None),
            "journeyPhase": getattr(plan, "journey_phase", None),
            "taxYear": getattr(plan, "tax_year", None),
            "slotsTier0": list(getattr(plan, "slots_tier0", []) or []),
            "slotsTier1": list(getattr(plan, "slots_tier1", []) or []),
            "forbidden": list(getattr(plan, "forbidden", []) or []),
            "toolsAllowed": tools_allowed,
            "fastLane": bool(getattr(plan, "fast_lane", False)),
        },
        "runtime": {
            "llmMode": meta.get("mode"),
            "model": meta.get("model"),
            "toolsExecuted": tools_executed,
            "harnessBlockChars": harness_block_len,
            "narrativePolished": bool(meta.get("narrativePolished")),
            "turnFocus": turn_focus or {},
            "turnScope": meta.get("turnScope") or {},
            "turnPhases": phases,
            "intentScore": meta.get("intentScore"),
            "messageStack": meta.get("messageStack"),
            "composer": {
                "profile": composer_raw.get("profile"),
                "narrated": bool(composer_raw.get("narrated")),
                "fallbackReason": composer_raw.get("fallbackReason"),
                "auditMs": composer_raw.get("auditMs"),
            },
        },
        "numericsAudit": numerics,
        "tier0Integrity": integrity,
        "planVsActual": plan_vs_actual,
        "warnings": warnings[:16],
    }


def format_harness_summary_zh(report: dict[str, Any]) -> str:
    plan = report.get("plan") or {}
    rt = report.get("runtime") or {}
    warns = report.get("warnings") or []
    w = f" WARN:{len(warns)}" if warns else ""
    tools = rt.get("toolsExecuted") or []
    tool_s = f" tools={','.join(tools)}" if tools else ""
    polish = " polish=1" if rt.get("narrativePolished") else ""
    t0 = report.get("tier0Integrity") or {}
    asserts = t0.get("assertions") or []
    a_s = f" assert={len(asserts)}" if asserts else ""
    errs = t0.get("errors") or []
    e_s = f" t0err={len(errs)}" if errs else ""
    phases = rt.get("turnPhases") or []
    ph_s = f" phases={len(phases)}" if phases else ""
    return (
        f"[Tax Harness] {report.get('mode')} {plan.get('profile')} "
        f"| year={plan.get('taxYear')} fast={1 if plan.get('fastLane') else 0}"
        f"{tool_s}{polish}{a_s}{e_s}{ph_s}{w}"
    )


def write_harness_report(
    *,
    session_id: str,
    user_message: str,
    plan: Any,
    meta: dict[str, Any],
    mode: str,
    harness_block_len: int = 0,
    turn_focus: dict[str, Any] | None = None,
    action: str = "none",
    slot_contents: dict[str, str] | None = None,
    tier0_integrity: dict[str, Any] | None = None,
    turn_phases: list[str] | None = None,
) -> dict[str, Any] | None:
    if not harness_report_enabled():
        return None
    report = build_harness_report(
        session_id=session_id,
        user_message=user_message,
        plan=plan,
        meta=meta,
        mode=mode,
        harness_block_len=harness_block_len,
        turn_focus=turn_focus,
        action=action,
        slot_contents=slot_contents,
        tier0_integrity=tier0_integrity,
        turn_phases=turn_phases,
    )
    summary = format_harness_summary_zh(report)
    if harness_debug_enabled():
        logger.info(summary)
        path = Path(os.environ.get("TAX_HARNESS_REPORT_PATH", "/tmp/tax-harness-reports.jsonl"))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(report, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("harness report write failed: %s", exc)
    return report
