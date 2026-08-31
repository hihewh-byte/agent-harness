#!/usr/bin/env python3
"""Tax insight layer selfcheck (closing positions + FIFO unrealized + filing table)."""

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.chat_orchestrator import infer_tax_year
from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.session_context import SessionContext
from tax_agent.tax_insight import build_tax_insight, format_insight_reply_zh, try_insight_fast_turn
from tax_agent.tax_intent_router import resolve_tax_intent
from tax_agent.tool_executor import apply_tool_call

FIXTURE_2022 = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_annual.xlsx"


def main() -> int:
    sample = FIXTURE_2022
    if not sample.is_file():
        print("SKIP: futu_tax_2022_annual fixture missing")
        return 0

    pr = BrokerParser(template_id="broker_futu_v1").parse_path(sample, session_id="insight-sc")
    dq = pr.data_quality or {}
    pkgs = dq.get("futuTaxPackages") or ([dq["futuTaxPackage"]] if dq.get("futuTaxPackage") else [])
    assert pkgs, "expected futuTaxPackages"
    pkg = pkgs[0]
    closings = pkg.get("closingPositions") or []
    assert closings, f"expected closingPositions, got keys={pkg.keys()}"
    assert closings[0]["symbol"] == "AMZN"
    print("PASS closingPositions parsed")

    assert infer_tax_year("23年盈利高", 2024) == 2023
    print("PASS infer_tax_year 23年")

    insight = build_tax_insight(
        focus="realized_vs_deferred",
        tax_year=2022,
        data_quality=dq,
        events=pr.events,
        last_summary={
            "taxableIncomeCny": "0.00",
            "taxDueCny": "0.00",
            "netTaxDueCny": "0.00",
        },
    )
    assert insight.get("filingTable"), insight
    assert insight.get("fx", {}).get("rate")
    assert "deferredUnrealized" in insight
    reply = format_insight_reply_zh(insight)
    assert "申报口径" in reply or "T0" in reply
    assert "AMZN" in reply or insight.get("closingPositions")
    print("PASS build_tax_insight extended")

    q = "2023年盈利高的原因是否因亏损股持有到下一年？期权到期为0作为成本的部分有多少？"
    plan = resolve_tax_intent(q, default_tax_year=2023)
    assert plan.profile == "compound_deferral_options"
    assert plan.tax_year == 2023
    print("PASS resolve_tax_intent compound")

    ctx = SessionContext(
        dataset_id="ds-x",
        tax_year=2023,
        data_quality=dq,
        events=pr.events,
        last_summary={"taxableIncomeCny": "0.00"},
        tax_insight=insight,
    )
    turn = apply_tool_call("get_tax_insight", {"tax_year": 2022, "focus": "realized_vs_deferred"}, ctx)
    assert turn.action == "none"
    assert "汇率" in turn.reply or "申报" in turn.reply
    print("PASS get_tax_insight tool")

    fast = try_insight_fast_turn(q, ctx)
    assert fast and fast.action == "none"
    assert fast.fact_bundle and fast.fact_bundle.profile == "insight_fast"
    print("PASS insight fast path + FactBundle")

    # Classified income in insight + numerics (PR-D)
    inc = ROOT / "tests" / "fixtures" / "broker" / "futu_classified_income_usd.xlsx"
    if inc.is_file():
        from tax_agent.futu_session_fifo import finalize_futu_session_dataset
        from tax_agent.filing_session_state import FilingSessionState
        from tax_agent.harness_plan import FilingTurnPlan
        from tax_agent.numerics_audit import build_numerics_manifest

        ev2 = list(pr.events)
        pr_inc = BrokerParser(template_id="broker_futu_v1").parse_path(inc)
        ev2.extend(pr_inc.events)
        ev2, _ = finalize_futu_session_dataset(ev2, dq)
        ins2 = build_tax_insight(
            focus="realized_vs_deferred",
            tax_year=2022,
            data_quality=dq,
            events=ev2,
            last_summary={"taxableIncomeCny": "1056.77", "netTaxDueCny": "96.08"},
        )
        assert ins2.get("classifiedIncome"), ins2.keys()
        assert ins2.get("grandTotal"), ins2.keys()
        reply2 = format_insight_reply_zh(ins2)
        assert "股息" in reply2 or "利息" in reply2
        st = FilingSessionState(data_quality=dq, events=ev2, focus_tax_year=2022)
        pl = FilingTurnPlan(
            profile="insight_fast",
            focus="insight",
            tax_year=2022,
            journey_phase="computed",
            slots_tier0=(),
            slots_tier1=(),
            forbidden=(),
            tools_allowed=(),
            task_text="",
        )
        man = build_numerics_manifest(st, pl)
        from tax_agent.numerics_audit import _normalize_decimal_token

        net = ins2["grandTotal"]["netTaxDueCny"]
        assert _normalize_decimal_token(net) in man, f"{net} not in manifest"
        fb = ins2["classifiedIncome"]["dividend"]["netTaxDueCny"]
        assert _normalize_decimal_token(fb) in man
        print("PASS insight classified income + numerics manifest")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
