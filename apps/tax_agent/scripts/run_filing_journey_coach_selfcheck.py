#!/usr/bin/env python3
"""Filing journey coach + guided_filing selfcheck (Tax Chat Experience v2 · C4)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.chat_turn_service import ChatTurnRequest, resolve_chat_turn
from tax_agent.coverage_check import build_coverage_report
from tax_agent.filing_journey_coach import (
    build_next_best_action,
    effective_guided_step,
    try_guided_filing_fast_turn,
)
from tax_agent.filing_session_state import FilingSessionState
from tax_agent.harness_plan import build_filing_turn_plan
from tax_agent.session_context import SessionContext
from tax_agent.tax_guided_session import clear_tax_guided_session, get_tax_guided_session
from tax_agent.tax_intent_catalog import resolve_profile_from_catalog
from tax_agent.tax_provenance import try_provenance_fast_turn
from tax_agent.fx_rates import FxRateProvider

SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def main() -> int:
    sid = "c4-selfcheck-session"
    clear_tax_guided_session(sid)

    dq_gap = {
        "futuTaxPackages": [
            {"taxYear": 2023, "openingPositions": [{"symbol": "AAPL", "qty": 1}]},
        ],
    }
    state_gap = FilingSessionState(
        dataset_id="ds-gap",
        data_quality=dq_gap,
        focus_tax_year=2023,
        uploaded_years=[2023],
        journey_phase="collecting",
    )
    nba = build_next_best_action(state_gap)
    assert nba and ("补传" in nba or "缺口" in nba), nba
    print("PASS C4-1 NBA missing-year hint")

    cov = build_coverage_report(data_quality=dq_gap, focus_tax_year=2023)
    assert cov.get("missingYears"), cov
    print("PASS coverage missing years detected")

    profile, score, _ = resolve_profile_from_catalog("带我申报", has_dataset=False)
    assert profile == "guided_filing", (profile, score)
    print("PASS intent → guided_filing")

    ctx = SessionContext(session_id=sid, dataset_id=None, tax_year=2024)
    turn1 = try_guided_filing_fast_turn("带我申报", ctx)
    assert turn1 and "第 1/5" in turn1.reply and "上传" in turn1.reply
    gs = get_tax_guided_session(sid)
    assert gs and gs.wizard_active
    print("PASS guided step 1 collecting")

    provider = FxRateProvider.from_snapshot_dir(SNAP)
    ctx2 = SessionContext(
        session_id=sid,
        dataset_id=None,
        tax_year=2025,
        fx_policy="cn_supplemental",
        fx_provider=provider,
    )
    interrupt = try_provenance_fast_turn("22年的汇率是多少", ctx2)
    assert interrupt and interrupt.fact_bundle
    gs2 = get_tax_guided_session(sid)
    assert gs2 and gs2.wizard_active, "wizard must survive interrupt"
    print("PASS guided wizard survives interrupt")

    turn_resume = try_guided_filing_fast_turn("继续申报", ctx)
    assert turn_resume and "申报向导" in turn_resume.reply
    step = effective_guided_step(sid, FilingSessionState.from_session_context(ctx))
    assert step in ("collecting", "ready", "computed", "reviewing", "export")
    print("PASS C4-2 resume guided after interrupt")

    plan = build_filing_turn_plan(
        "带我申报",
        default_tax_year=2024,
        has_dataset=False,
        has_compute=False,
    )
    assert plan.profile == "guided_filing"
    assert "guided_filing" in plan.tools_allowed or "check_coverage" in plan.tools_allowed
    print("PASS harness guided_filing plan")

    req = ChatTurnRequest(
        session_id="c4-nba-sync",
        message="材料覆盖",
        dataset_id="ds-gap",
        tax_year=2023,
        llm_model="__off__",
    )
    ctx3 = SessionContext(session_id=req.session_id, dataset_id=req.dataset_id, tax_year=2023)
    ctx3.data_quality = dq_gap
    outcome = resolve_chat_turn(req, ctx3, apply_composer=False)
    assert outcome.nba or "缺口" in outcome.reply or "缺" in outcome.reply
    print("PASS NBA wired in chat_turn_service")

    clear_tax_guided_session(sid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
