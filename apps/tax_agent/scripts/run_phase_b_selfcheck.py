#!/usr/bin/env python3
"""Phase B: insight/narrative FactBundle, harnessReport v2, NBA L4."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.fact_bundle import (
    build_filing_narrative_fact_bundle,
    build_insight_fact_bundle,
)
from tax_agent.filing_journey_coach import enrich_outcome_with_nba, resolve_turn_nba
from tax_agent.filing_session_state import FilingSessionState
from tax_agent.harness_plan import build_filing_turn_plan
from tax_agent.harness_report import build_harness_report
from tax_agent.tax_insight import build_tax_insight, format_insight_reply_zh, try_insight_fast_turn
from tax_agent.session_context import SessionContext


def main() -> int:
    insight = {
        "taxYear": 2023,
        "focus": "realized_vs_deferred",
        "fx": {"rate": "7.10", "policy": "cn_supplemental", "tier": "T0"},
        "filingTable": {
            "taxableIncomeCny": "1046912",
            "taxDueCny": "209382.4",
            "tier": "T0",
        },
        "unrealizedSummary": {"unrealizedLossCny": "50000", "tier": "T1"},
    }
    fb = build_insight_fact_bundle(
        insight,
        fallback_markdown=format_insight_reply_zh(insight),
        has_dataset=True,
    )
    assert fb.profile == "insight_fast"
    assert "1046912" in fb.merged_numerics()
    print("PASS build_insight_fact_bundle")

    row = {
        "grossProceedsCny": "100",
        "taxableIncomeCny": "19",
        "taxDueCny": "3.8",
        "fxRate": "7.1",
    }
    narr_fb = build_filing_narrative_fact_bundle(
        row,
        tax_year=2023,
        fallback_markdown="申报说明模板",
        has_dataset=True,
    )
    assert narr_fb.profile == "filing_narrative"
    assert "3.8" in narr_fb.merged_numerics()
    print("PASS build_filing_narrative_fact_bundle")

    snap = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"
    pkg_path = snap / "futu_tax_packages" / "2023.json"
    if pkg_path.is_file():
        import json

        dq = {"futuTaxPackages": [json.loads(pkg_path.read_text(encoding="utf-8"))]}
        ctx = SessionContext(session_id="b-insight", dataset_id="ds1", tax_year=2023)
        ctx.data_quality = dq
        fast = try_insight_fast_turn("为什么盈利偏高", ctx)
        assert fast and fast.fact_bundle and fast.fact_bundle.profile == "insight_fast"
        print("PASS try_insight_fast_turn fact_bundle")
    else:
        print("SKIP try_insight_fast_turn (no snapshot pkg)")

    state = FilingSessionState(
        dataset_id="ds-gap",
        data_quality={"futuTaxPackages": [{"taxYear": 2023}]},
        focus_tax_year=2023,
        uploaded_years=[2023],
    )
    nba = resolve_turn_nba(state, "coverage_check")
    assert nba
    body = "正文不含 NBA"
    reply, attached = enrich_outcome_with_nba(reply=body, state=state, profile="coverage_check")
    assert reply == body and attached == nba
    assert "下一步建议" not in reply
    print("PASS NBA not appended to reply")

    plan = build_filing_turn_plan("汇率", default_tax_year=2023, has_dataset=True)
    rep = build_harness_report(
        session_id="b1",
        user_message="汇率",
        plan=plan,
        meta={
            "mode": "provenance_fast",
            "runtime": {
                "composer": {
                    "profile": "policy_explain",
                    "narrated": True,
                    "fallbackReason": "none",
                    "auditMs": 42,
                }
            },
        },
        mode="provenance_fast",
    )
    assert rep["schema"] == "tax.harness_report/v2"
    comp = (rep.get("runtime") or {}).get("composer") or {}
    assert comp.get("narrated") is True and comp.get("auditMs") == 42
    print("PASS harnessReport v2 composer node")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
