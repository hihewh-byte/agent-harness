#!/usr/bin/env python3
"""Harness P2: session_turn_focus, chat_context, filing_narrative."""

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.chat_context import build_chat_recall_block, extract_tax_keywords
from tax_agent.filing_narrative import compose_filing_narrative_text
from tax_agent.harness_plan import build_filing_turn_plan
from tax_agent.numerics_audit import audit_response_numerics, build_numerics_manifest
from tax_agent.session_turn_focus import (
    get_tax_session_focus,
    record_turn_focus,
    resolve_focus_tax_year,
    revive_tax_session_focus,
    save_tax_session_focus,
    TaxSessionTurnFocus,
)
from tax_agent.filing_session_state import FilingSessionState
from tax_agent.harness_plan import FilingTurnPlan


def main() -> int:
    kws = extract_tax_keywords("2023年合理费用和汇率怎么算")
    assert "2023" in kws and "合理费用" in kws
    block = build_chat_recall_block(
        "继续问汇率",
        chat_history=[
            {"role": "user", "content": "2023年税额"},
            {"role": "assistant", "content": "应纳税所得额 1046912 元"},
        ],
        focus_block="【焦点】2023",
    )
    assert "最近对话" in block
    print("PASS chat_context")

    row = {
        "taxYear": 2023,
        "grossProceedsCny": "7076112.00",
        "grossProceedsUsd": "1016011.00",
        "costBasisCny": "6008347.00",
        "costBasisUsd": "862698.00",
        "reasonableFeeCny": "20854.00",
        "reasonableFeeUsd": "2994.25",
        "taxableIncomeCny": "1046912.00",
        "netGainCny": "1046912.00",
        "taxDueCny": "209382.40",
        "fxRate": "6.9646",
        "fxPolicy": "cn_supplemental",
        "fxNote": "test",
    }
    text = compose_filing_narrative_text(row, tax_year=2023)
    assert "1046912" in text and "209382" in text
    print("PASS filing_narrative")

    with tempfile.TemporaryDirectory() as td:
        import os

        os.environ["TAX_AGENT_DB"] = str(Path(td) / "t.db")
        sid = "sess-p2-test"
        save_tax_session_focus(sid, focus_tax_year=2023, focus_profile="filing_coach")
        f = get_tax_session_focus(sid)
        assert f and f.active and f.focus_tax_year == 2023
        stub = TaxSessionTurnFocus(
            session_id=sid,
            focus_tax_year=2023,
            focus_profile="filing_coach",
            focus_summary="",
            focus_tokens=["2023"],
            turns_remaining=2,
        )
        y = resolve_focus_tax_year("那年合理费用呢", 2024, stub)
        assert y == 2023
        record_turn_focus(sid, tax_year=2023, profile="filing_coach", user_message="2023年")
        revived = revive_tax_session_focus(sid, "继续")
        assert revived and revived.focus_tax_year == 2023
    print("PASS session_turn_focus")

    state = FilingSessionState(
        data_quality={"futuTaxPackages": []},
        focus_tax_year=2023,
    )
    plan = FilingTurnPlan(
        profile="filing_narrative",
        focus="narrative",
        tax_year=2023,
        journey_phase="reviewing",
        slots_tier0=(),
        slots_tier1=(),
        forbidden=(),
        tools_allowed=(),
        task_text="",
    )
    manifest = build_numerics_manifest(state, plan)
    manifest.update({"1046912", "209382"})
    bad = audit_response_numerics("税额 9999999 元", manifest, strict=True)
    assert not bad.ok
    print("PASS numerics strict")

    p = build_filing_turn_plan(
        "帮我写申报说明",
        default_tax_year=2024,
        has_dataset=True,
        has_compute=True,
        focus_tax_year=2023,
    )
    assert p.profile == "filing_narrative"
    print("PASS harness narrative profile")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
