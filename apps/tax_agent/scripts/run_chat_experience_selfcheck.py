#!/usr/bin/env python3
"""Tax Chat Experience v2 · C1 GroundedAnswerComposer selfcheck."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.answer_composer import (
    build_follow_ups,
    compose_grounded_reply,
    finalize_turn_with_composer,
)
from tax_agent.chat_orchestrator import ChatTurnResult
from tax_agent.fx_rates import FxRateProvider
from tax_agent.session_context import SessionContext
from tax_agent.tax_provenance import try_provenance_fast_turn

SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def _mock_good_narrator(bundle, **kwargs):
    facts = bundle.facts
    rate = facts.get("rate") if isinstance(facts, dict) else None
    if not rate and isinstance(facts, dict):
        rows = (facts.get("rows") or [])
        if rows:
            rate = rows[0].get("rate")
    year = bundle.tax_year or (facts.get("taxYear") if isinstance(facts, dict) else "")
    text = (
        f"{year}年补缴申报使用的汇率是{rate}。"
        "这是因为取上一纳税年度末日中间价，依据【个人所得税法实施条例第三十二条】。"
    )
    return text, ""


def _mock_bad_narrator(bundle, **kwargs):
    return "2022年汇率是 9.9999，依据某虚构公告。", ""


def main() -> int:
    provider = FxRateProvider.from_snapshot_dir(SNAP)
    assert provider

    ctx = SessionContext(
        dataset_id=None,
        tax_year=2025,
        fx_policy="cn_supplemental",
        fx_provider=provider,
    )
    turn = try_provenance_fast_turn("22年的补申报的汇率是如何确定的", ctx)
    assert turn and turn.fact_bundle, "fast turn must attach FactBundle"
    assert "6.3757" in turn.reply
    print("PASS FactBundle attached to provenance fast turn")

    bundle = turn.fact_bundle
    composed = compose_grounded_reply(
        bundle,
        user_message="22年汇率怎么定",
        llm_on=True,
        narrate_fn=_mock_good_narrator,
    )
    assert composed.narrated, composed.composer_meta
    assert not composed.reply.startswith("##"), composed.reply[:80]
    assert "6.3757" in composed.reply
    assert "第三十二条" in composed.reply
    assert len(composed.follow_ups) == 3
    print("PASS C1-1 narrated reply (mock LLM)")

    fallback = compose_grounded_reply(
        bundle,
        user_message="22年汇率怎么定",
        llm_on=False,
    )
    assert not fallback.narrated
    assert fallback.reply.startswith("##"), fallback.reply[:40]
    assert "6.3757" in fallback.reply
    print("PASS C1-2 LLM off → v1 template fallback")

    blocked = compose_grounded_reply(
        bundle,
        user_message="22年汇率怎么定",
        llm_on=True,
        narrate_fn=_mock_bad_narrator,
    )
    assert not blocked.narrated
    assert blocked.reply == bundle.fallback_markdown
    assert blocked.fallback_reason == "audit_numerics"
    print("PASS C1-3 fake numerics → audit fallback")

    follow = build_follow_ups(bundle)
    assert len(follow) == 3
    assert all(isinstance(q, str) and q.strip() for q in follow)
    print("PASS C1-4 followUps ×3")

    finalized, meta = finalize_turn_with_composer(
        turn,
        user_message="22年汇率怎么定",
        llm_on=True,
        narrate_fn=_mock_good_narrator,
    )
    assert meta["composer"]["narrated"]
    assert finalized.follow_ups and len(finalized.follow_ups) == 3
    print("PASS finalize_turn_with_composer integration")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
