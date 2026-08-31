"""Tier0 ledger assembly with protected SLA — Tax v1.8（仿 PHA harness_tier0_assembly）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from tax_agent.harness_plan import FilingTurnPlan, TAX_HARNESS_TIER0_MAX_CHARS

TierLevel = Literal["full", "dropped"]

_PROFILE_PROTECTED: dict[str, frozenset[str]] = {
    "filing_narrative": frozenset({"FILING_TABLE_AUTHORITY", "NUMERICS_MANIFEST", "TASK"}),
    "filing_coach": frozenset({"FILING_TABLE_AUTHORITY", "TASK"}),
    "compute": frozenset({"NUMERICS_MANIFEST", "TASK"}),
    "explain_summary": frozenset({"NUMERICS_MANIFEST", "TASK"}),
    "policy_explain": frozenset({"TASK"}),
    "coverage_check": frozenset({"DATA_COVERAGE", "TASK"}),
}

_PROFILE_DEGRADE_ORDER: dict[str, tuple[str, ...]] = {
    "filing_narrative": ("RISK_BRIEF", "MASTER_ANCHOR"),
    "filing_coach": ("RISK_BRIEF", "FX_PROVENANCE", "MASTER_ANCHOR"),
    "general": ("FILING_SNAPSHOT", "MASTER_ANCHOR"),
}

# Compliance-oriented markers for dry-run integrity (domain strings only — no PII).
_SLOT_MARKERS: dict[str, str] = {
    "TASK": "【TASK】",
    "MASTER_ANCHOR": "【MASTER_ANCHOR】",
    "NUMERICS_MANIFEST": "【NUMERICS_MANIFEST】",
    "FILING_TABLE_AUTHORITY": "【FILING_TABLE_AUTHORITY】",
    "DATA_COVERAGE": "【DATA_COVERAGE】",
    "POLICY_CARDS": "【POLICY_CARDS】",
    "FX_PROVENANCE": "【FX_PROVENANCE】",
    "RISK_BRIEF": "【RISK_BRIEF】",
    "TAX_INSIGHT": "【TAX_INSIGHT】",
    "FILING_SNAPSHOT": "【FILING_SNAPSHOT】",
    "FILING_SCOPE": "【FILING_SCOPE】",
}


@dataclass
class SlotAssembly:
    slot_id: str
    text: str
    protected: bool
    present: bool
    level: TierLevel = "full"
    dropped: bool = False


def _truncate(text: str, max_len: int, *, note: str) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - len(note) - 1] + note


def slot_materialized_in_tier0(slot_id: str, tier0_text: str) -> bool:
    marker = _SLOT_MARKERS.get(slot_id)
    if not marker:
        # Unknown slots: treat non-empty presence as success when text appears.
        return True
    return marker in (tier0_text or "")


def build_tier0_integrity(
    plan: FilingTurnPlan,
    assemblies: list[SlotAssembly],
    *,
    tier0_text: str,
    budget: int,
    dropped_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Richer Tier0 integrity block for dry-run / report (PHA twin, tax-shaped)."""
    dropped_ids = dropped_ids or set()
    errors: list[str] = []
    warnings: list[str] = []
    slot_rows: list[dict[str, Any]] = []
    protected_ids = _PROFILE_PROTECTED.get(plan.profile, frozenset({"TASK"}))

    by_id = {a.slot_id: a for a in assemblies}
    for slot_id in plan.slots_tier0:
        asm = by_id.get(slot_id)
        present = bool(asm and asm.present)
        protected = slot_id in protected_ids
        dropped = slot_id in dropped_ids or bool(asm and asm.dropped)
        level: TierLevel = "dropped" if dropped else "full"
        chars = len(asm.text) if asm and asm.present and not dropped else 0
        materialized = (
            present
            and not dropped
            and slot_materialized_in_tier0(slot_id, tier0_text)
        )
        row = {
            "slot_id": slot_id,
            "present": present,
            "protected": protected,
            "level": level,
            "chars": chars,
            "materialized": materialized,
        }
        slot_rows.append(row)

        if protected and not present:
            errors.append(f"protected_slot_empty:{slot_id}")
        elif protected and dropped:
            errors.append(f"protected_slot_dropped:{slot_id}")
        elif present and not dropped and not materialized and slot_id in _SLOT_MARKERS:
            warnings.append(f"tier0_not_materialized:{slot_id}")
        elif not present and slot_id not in ("MASTER_ANCHOR", "TASK"):
            warnings.append(f"planned_slot_empty:{slot_id}")

    if "LLM_COMPUTE" in (plan.forbidden or ()) and "LLM_COMPUTE" in (
        plan.tools_allowed or ()
    ):
        errors.append("forbidden_vs_allowlist_conflict:LLM_COMPUTE")

    # Tax-domain compliance assertions (codes only — no amounts / PII).
    assertions: list[str] = []
    if plan.profile == "filing_narrative":
        assertions.append("assert:filing_table_authority_required")
        assertions.append("assert:numerics_manifest_required")
        assertions.append("assert:no_llm_compute")
    if plan.profile == "compute":
        assertions.append("assert:numerics_manifest_required")
        assertions.append("assert:no_llm_compute")
    if plan.profile == "policy_qa":
        assertions.append("assert:policy_cards_only")
        assertions.append("assert:no_invent_policy")
    if "INVENT_FX_RATE" in (plan.forbidden or ()):
        assertions.append("assert:no_invent_fx_rate")
    if "LLM_COMPUTE" in (plan.forbidden or ()):
        assertions.append("assert:no_llm_compute")

    return {
        "budget_limit": budget,
        "used_chars": len(tier0_text or ""),
        "slots": slot_rows,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "assertions": sorted(set(assertions)),
        "profile": plan.profile,
        "journey_phase": plan.journey_phase,
    }


def tier0_integrity_plan_diffs(integrity: dict[str, Any]) -> list[str]:
    """Flatten integrity errors/warnings into planVsActual-style codes."""
    diffs: list[str] = []
    for err in integrity.get("errors") or []:
        diffs.append(str(err))
    for warn in integrity.get("warnings") or []:
        if str(warn).startswith("tier0_not_materialized:"):
            diffs.append(str(warn))
    return sorted(set(diffs))


def assemble_filing_ledger(
    slot_blocks: list[tuple[str, str]],
    plan: FilingTurnPlan,
    *,
    budget: int | None = None,
) -> tuple[str, list[SlotAssembly], dict[str, Any]]:
    """
    Merge slot blocks under char budget; protected slots kept first.

    Returns (ledger_text, assemblies, tier0_integrity).
    slot_blocks: [(slot_id, markdown_text), ...] in plan slot order.
    """
    cap = budget if budget is not None else TAX_HARNESS_TIER0_MAX_CHARS
    protected_ids = _PROFILE_PROTECTED.get(plan.profile, frozenset({"TASK"}))
    degrade = _PROFILE_DEGRADE_ORDER.get(plan.profile, ("MASTER_ANCHOR",))

    assemblies: list[SlotAssembly] = []
    for slot_id, text in slot_blocks:
        t = (text or "").strip()
        assemblies.append(
            SlotAssembly(
                slot_id=slot_id,
                text=t,
                protected=slot_id in protected_ids,
                present=bool(t),
            )
        )

    def _join(parts: list[str]) -> str:
        return "\n\n---\n\n".join(p for p in parts if p)

    dropped_ids: set[str] = set()

    # Pass 1: all present slots
    parts = [a.text for a in assemblies if a.present]
    out = _join(parts)
    if len(out) <= cap:
        integrity = build_tier0_integrity(
            plan, assemblies, tier0_text=out, budget=cap, dropped_ids=dropped_ids
        )
        return out, assemblies, integrity

    # Pass 2: drop non-protected in degrade order
    for slot_id in degrade:
        dropped_ids.add(slot_id)
        for a in assemblies:
            if a.slot_id == slot_id and not a.protected:
                a.dropped = True
                a.level = "dropped"
        parts = [
            a.text
            for a in assemblies
            if a.present and (a.protected or a.slot_id not in dropped_ids)
        ]
        out = _join(parts)
        if len(out) <= cap:
            note = "\n…（账本已按 protected SLA 降级，完整数据请查申报 API）"
            out = out + note
            integrity = build_tier0_integrity(
                plan, assemblies, tier0_text=out, budget=cap, dropped_ids=dropped_ids
            )
            return out, assemblies, integrity

    # Pass 3: truncate lowest-priority protected-adjacent content
    parts = [a.text for a in assemblies if a.present and a.protected]
    if not parts:
        parts = [a.text for a in assemblies if a.present][:2]
    out = _join(parts)
    note = "\n…（账本已截断，FILING_TABLE/NUMERICS 优先保留）"
    out = _truncate(out, cap, note=note)
    integrity = build_tier0_integrity(
        plan, assemblies, tier0_text=out, budget=cap, dropped_ids=dropped_ids
    )
    return out, assemblies, integrity
