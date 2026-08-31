#!/usr/bin/env python3
"""PolicyKB + policy_qa profile selfcheck (Tax Chat Experience v2 · C2)."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.answer_composer import compose_grounded_reply
from tax_agent.harness_plan import build_filing_turn_plan
from tax_agent.policy_kb import (
    load_knowledge_cards,
    retrieve_top_cards,
    score_knowledge_cards,
    try_policy_qa_fast_turn,
)
from tax_agent.session_context import SessionContext
from tax_agent.tax_intent_catalog import resolve_profile_from_catalog


def _mock_policy_narrator(bundle, **kwargs):
    cards = (bundle.facts or {}).get("cards") or []
    if not cards:
        return "该问题超出知识库范围。", ""
    c0 = cards[0]
    cites = bundle.citations_dicts()
    cite = cites[0]["label"] if cites else ""
    text = f"{c0.get('answerT0', '')[:120]}… 依据【{cite}】。"
    return text, ""


def main() -> int:
    os.environ.pop("TAX_KB_ALLOW_DRAFT", None)
    load_knowledge_cards.cache_clear()

    reviewed = [c for c in load_knowledge_cards() if c.review_status == "reviewed"]
    assert len(reviewed) >= 12, f"expected ≥12 reviewed cards, got {len(reviewed)}"
    print(f"PASS reviewed cards count: {len(reviewed)}")

    profile, score, _ = resolve_profile_from_catalog(
        "境外股票赚的钱要交税吗",
        has_dataset=False,
    )
    assert profile == "policy_qa", (profile, score)
    print("PASS intent → policy_qa (C2-1 route)")

    ctx = SessionContext(dataset_id=None, tax_year=2024)
    turn = try_policy_qa_fast_turn("境外股票赚的钱要交税吗", ctx)
    assert turn and turn.fact_bundle
    assert turn.fact_bundle.profile == "policy_qa"
    assert "申报" in turn.reply or "财产转让" in turn.reply
    assert "个人所得税法" in turn.reply or "第一条" in turn.reply
    cards = retrieve_top_cards("境外股票赚的钱要交税吗")
    assert cards and cards[0].id == "kb:cn-overseas-filing-duty"
    print("PASS C2-1 policy_qa fast turn + citation")

    composed = compose_grounded_reply(
        turn.fact_bundle,
        user_message="境外股票赚的钱要交税吗",
        llm_on=True,
        narrate_fn=_mock_policy_narrator,
    )
    assert composed.narrated
    assert "依据【" in composed.reply
    print("PASS C2-1 composer narration")

    profile2, _, _ = resolve_profile_from_catalog("法国税怎么算", has_dataset=False)
    assert profile2 == "policy_qa"
    turn2 = try_policy_qa_fast_turn("法国税怎么算", ctx)
    assert turn2
    assert "超出" in turn2.reply or "知识库范围" in turn2.reply
    assert "法国" not in turn2.reply or "超出" in turn2.reply
    assert "draft" not in turn2.reply.lower()
    print("PASS C2-2 out-of-scope honest reply")

    score_draft, cards_draft = score_knowledge_cards("法国税怎么算")
    assert score_draft == 0.0
    assert not any(c.review_status == "draft" for c in cards_draft)
    print("PASS C2-3 draft card excluded in production")

    os.environ["TAX_KB_ALLOW_DRAFT"] = "1"
    load_knowledge_cards.cache_clear()
    _, cards_dev = score_knowledge_cards("法国税怎么算")
    assert any(c.id == "kb:draft-france-tax" for c in cards_dev)
    load_knowledge_cards.cache_clear()
    os.environ.pop("TAX_KB_ALLOW_DRAFT", None)
    print("PASS draft visible only with TAX_KB_ALLOW_DRAFT=1")

    plan = build_filing_turn_plan(
        "境外股票赚的钱要交税吗",
        default_tax_year=2024,
        has_dataset=False,
        has_compute=False,
    )
    assert plan.profile == "policy_qa"
    assert "INVENT_POLICY" in plan.forbidden
    assert "POLICY_CARDS" in plan.slots_tier0
    print("PASS harness plan policy_qa slots/forbidden")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
