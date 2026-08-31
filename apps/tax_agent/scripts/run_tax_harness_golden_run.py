#!/usr/bin/env python3
"""No-LLM tax harness golden run — Plan / Tier0 / report card without Ollama.

Usage (from tax_agent repo root)::

    python scripts/run_tax_harness_golden_run.py

Exit 0 = assertions passed. No Ollama / no API keys required.
Mirrors PHA ``scripts/pha_harness_golden_run.py`` for Phase A dual-domain basement.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("TAX_HARNESS_DEBUG", "1")
os.environ.setdefault(
    "TAX_HARNESS_REPORT_PATH",
    str(Path(os.environ.get("TMPDIR", "/tmp")) / "tax-harness-golden.jsonl"),
)

from tax_agent.harness_plan import build_filing_turn_plan  # noqa: E402
from tax_agent.harness_report import REPORT_SCHEMA, write_harness_report  # noqa: E402
from tax_agent.harness_tier0_assembly import assemble_filing_ledger  # noqa: E402
from tax_agent.harness_profile_registry import validate_harness_profile_registry  # noqa: E402
from tax_agent.chat_turn_fsm import (  # noqa: E402
    TaxTurnPhase,
    TaxTurnPhaseRecorder,
    plan_precedes_compose,
)


def _print_builder_card(
    case_id: str,
    *,
    plan: object,
    ledger_chars: int,
    assemblies: list,
    report: dict,
    integrity: dict | None = None,
) -> None:
    slots0 = list(getattr(plan, "slots_tier0", ()) or ())
    tools = list(getattr(plan, "tools_allowed", ()) or [])
    forbidden = list(getattr(plan, "forbidden", ()) or [])
    asm_bits = []
    for a in assemblies or []:
        sid = getattr(a, "slot_id", None)
        present = getattr(a, "present", False)
        protected = getattr(a, "protected", False)
        chars = len(getattr(a, "text", "") or "")
        if present:
            asm_bits.append(f"{sid}={'P' if protected else 'o'}({chars}c)")
    print(f"\n--- {case_id} ---")
    print(f"  profile        : {getattr(plan, 'profile', None)}")
    print(f"  journey_phase  : {getattr(plan, 'journey_phase', None)}")
    print(f"  tax_year       : {getattr(plan, 'tax_year', None)}")
    print(f"  fast_lane      : {bool(getattr(plan, 'fast_lane', False))}")
    print(f"  slots_tier0    : {slots0}")
    print(f"  tools_allowed  : {tools or '(none)'}")
    print(f"  forbidden      : {forbidden[:6]}{'…' if len(forbidden) > 6 else ''}")
    print(f"  tier0 assembled: {', '.join(asm_bits) if asm_bits else '(empty)'}")
    print(f"  tier0 used     : {ledger_chars} chars")
    t0 = integrity or report.get("tier0Integrity") or {}
    print(f"  tier0.assertions: {t0.get('assertions') or []}")
    print(f"  tier0.errors   : {t0.get('errors') or []}")
    print(f"  report.schema  : {report.get('schema')}")
    print(f"  report.warnings: {report.get('warnings') or []}")


def _synthetic_blocks(plan: object) -> list[tuple[str, str]]:
    """Minimal slot payloads so Tier0 assembly runs without a real filing DB."""
    blocks: list[tuple[str, str]] = []
    for sid in getattr(plan, "slots_tier0", ()) or ():
        if sid == "TASK":
            blocks.append((sid, f"【TASK】{getattr(plan, 'task_text', '')[:400]}"))
        elif sid == "NUMERICS_MANIFEST":
            blocks.append((sid, "【NUMERICS_MANIFEST】allowed=demo-only; no live filing_table"))
        elif sid == "FILING_TABLE_AUTHORITY":
            blocks.append((sid, "【FILING_TABLE_AUTHORITY】demo_row total=0 (golden fixture)"))
        elif sid == "MASTER_ANCHOR":
            blocks.append((sid, "【MASTER_ANCHOR】tax_year=demo"))
        else:
            blocks.append((sid, f"【{sid}】golden-placeholder"))
    return blocks


def main() -> int:
    report_path = os.environ["TAX_HARNESS_REPORT_PATH"]
    Path(report_path).write_text("", encoding="utf-8")

    cases = [
        (
            "T1_onboarding",
            "第一次报税需要什么材料？怎么开始？",
            {"has_dataset": False, "has_compute": False},
        ),
        (
            "T2_narrative",
            "帮我写一段申报说明，总结今年财产转让所得",
            {"has_dataset": True, "has_compute": True},
        ),
    ]

    print("=== Tax Harness — 30s No-LLM Golden Run ===")
    print("Control plane only: Plan → Tier0 assembly → BuildReport (no Ollama call).\n")

    # P1: registry + FSM smoke (no LLM)
    reg = validate_harness_profile_registry()
    if not reg.ok:
        print("FAIL: profile registry validation", reg.errors)
        return 1
    print("PASS profile registry validation")

    fsm_rec = TaxTurnPhaseRecorder()
    for ph in (
        TaxTurnPhase.INIT,
        TaxTurnPhase.SESSION,
        TaxTurnPhase.SCOPE,
        TaxTurnPhase.PLAN,
        TaxTurnPhase.FAST_LANE,
        TaxTurnPhase.POST_AUDIT,
        TaxTurnPhase.DONE,
    ):
        fsm_rec.enter(ph)
    fsm_rec.assert_plan_before_compose()
    if not plan_precedes_compose(fsm_rec.phases):
        print("FAIL: FSM plan_precedes_compose")
        return 1
    print(f"PASS turn FSM telemetry phases={fsm_rec.as_names()}")

    # Week 3: require local harness_core adapter (tax stays local-only)
    from tax_agent.harness_core_adapter import (
        harness_core_available,
        plan_vs_actual_via_core,
        smoke_adapter_roundtrip,
    )

    if not harness_core_available():
        print("FAIL: harness_core sibling required for tax adapter golden")
        return 1
    print("PASS harness_core available for tax adapter")

    failed = 0
    for case_id, msg, flags in cases:
        plan = build_filing_turn_plan(
            msg,
            default_tax_year=2023,
            has_dataset=bool(flags["has_dataset"]),
            has_compute=bool(flags["has_compute"]),
        )
        try:
            smoke = smoke_adapter_roundtrip(plan)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: harness_core adapter smoke ({case_id}):", exc)
            failed += 1
            continue
        if smoke.get("core_profile") != plan.profile:
            print("FAIL: adapter profile mismatch", smoke.get("core_profile"), plan.profile)
            failed += 1
        if "plan" not in (smoke.get("core_phases") or []):
            print("FAIL: adapter core spine missing plan", smoke)
            failed += 1
        if case_id == "T1_onboarding":
            print(
                f"PASS adapter smoke profile={smoke['core_profile']} "
                f"core_phases={smoke['core_phases']} meta_keys={sorted(smoke.get('domain_meta') or {})}"
            )

        blocks = _synthetic_blocks(plan)
        ledger, assemblies, integrity = assemble_filing_ledger(blocks, plan)
        report = write_harness_report(
            session_id="golden-dry-run",
            user_message=msg,
            plan=plan,
            meta={
                "mode": "dry_run",
                "toolsExecuted": [],
                "slotContents": {sid: text for sid, text in blocks},
                "numericsAudit": {
                    "ok": True,
                    "warnings": [],
                    "allowedCount": 0,
                    "citedCount": 0,
                },
                "turnPhases": fsm_rec.as_names(),
                "corePhases": smoke.get("core_phases"),
            },
            mode="dry_run",
            harness_block_len=len(ledger or ""),
            action="plan_dry_run",
            slot_contents={sid: text for sid, text in blocks},
            tier0_integrity=integrity,
            turn_phases=fsm_rec.as_names(),
        )
        if report is None:
            print("FAIL: write_harness_report returned None (enable TAX_HARNESS_DEBUG=1)")
            failed += 1
            continue

        _print_builder_card(
            case_id,
            plan=plan,
            ledger_chars=len(ledger or ""),
            assemblies=list(assemblies or []),
            report=report,
            integrity=integrity,
        )
        pva = report.get("planVsActual")
        print(f"  planVsActual   : {pva}")

        if not getattr(plan, "profile", None):
            print("FAIL: empty profile")
            failed += 1
        if not getattr(plan, "slots_tier0", None):
            print("FAIL: empty slots_tier0")
            failed += 1
        if report.get("schema") != REPORT_SCHEMA:
            print("FAIL: schema mismatch", report.get("schema"), "!=", REPORT_SCHEMA)
            failed += 1
        if "planVsActual" not in report:
            print("FAIL: planVsActual field missing")
            failed += 1
        elif pva is None or not isinstance(pva, list):
            print("FAIL: planVsActual must be a list")
            failed += 1
        if "tier0Integrity" not in report:
            print("FAIL: tier0Integrity field missing")
            failed += 1
        elif not isinstance(report.get("tier0Integrity"), dict):
            print("FAIL: tier0Integrity must be a dict")
            failed += 1
        else:
            t0 = report["tier0Integrity"]
            if "slots" not in t0 or "assertions" not in t0:
                print("FAIL: tier0Integrity missing slots/assertions")
                failed += 1
            if t0.get("errors"):
                # Synthetic golden blocks should not leave protected slots empty
                print("FAIL: unexpected tier0Integrity.errors", t0.get("errors"))
                failed += 1
        if case_id == "T2_narrative":
            print(f"NOTE: T2 profile={getattr(plan, 'profile', None)!r} (catalog-dependent)")
            asserts = (report.get("tier0Integrity") or {}).get("assertions") or []
            if getattr(plan, "profile", None) == "filing_narrative":
                if "assert:no_llm_compute" not in asserts:
                    print("FAIL: filing_narrative missing assert:no_llm_compute")
                    failed += 1
                else:
                    print("PASS filing_narrative compliance assertions present")

    # Unit-style: tool allowlist violation must surface in planVsActual
    from tax_agent.harness_plan import FilingTurnPlan
    from tax_agent.harness_report import compute_plan_vs_actual, build_harness_report

    bad_plan = FilingTurnPlan(
        profile="general",
        focus="general",
        tax_year=2023,
        journey_phase="ready",
        slots_tier0=("TASK",),
        slots_tier1=(),
        forbidden=("LLM_COMPUTE",),
        tools_allowed=("reply_only",),
        task_text="x",
    )
    diffs = compute_plan_vs_actual(
        bad_plan,
        mode="llm_tools",
        tools_executed=["invent_fx"],
    )
    if "tool_not_allowed:invent_fx" not in diffs:
        print("FAIL: expected tool_not_allowed in planVsActual", diffs)
        failed += 1
    else:
        print("\nPASS planVsActual detects tool_not_allowed")

    core_diffs = plan_vs_actual_via_core(bad_plan, tools_executed=["invent_fx"])
    if "tool_not_allowed:invent_fx" not in core_diffs:
        print("FAIL: harness_core plan_vs_actual missing tool_not_allowed", core_diffs)
        failed += 1
    else:
        print("PASS harness_core plan_vs_actual via tax adapter")

    rep_bad = build_harness_report(
        session_id="golden-pva",
        user_message="probe",
        plan=bad_plan,
        meta={"toolsExecuted": ["invent_fx"], "mode": "llm_tools"},
        mode="llm_tools",
    )
    if "tool_not_allowed:invent_fx" not in (rep_bad.get("planVsActual") or []):
        print("FAIL: build_harness_report missing planVsActual code")
        failed += 1
    else:
        print("PASS build_harness_report embeds planVsActual")

    print(f"\nJSONL report: {report_path}")
    if failed:
        print(f"RESULT: FAIL ({failed} assertion(s))")
        return 1
    print("RESULT: PASS — tax harness planned and assembled Tier0 without calling an LLM.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
