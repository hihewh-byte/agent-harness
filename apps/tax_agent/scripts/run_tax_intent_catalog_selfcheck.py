#!/usr/bin/env python3
"""P3/P4: tax_intent_catalog + chat_message_stack selfcheck."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.chat_message_stack import FILING_LEDGER_PREAMBLE, build_tax_chat_message_stack
from tax_agent.harness_plan import build_filing_turn_plan
from tax_agent.tax_intent_catalog import (
    matches_multi_scope,
    resolve_profile_from_catalog,
)


def main() -> int:
    p, _s, _all = resolve_profile_from_catalog("这里的汇率是如何计算的？依据是什么？")
    assert p == "policy_explain", p
    print("PASS catalog policy_explain")

    p2, _, _ = resolve_profile_from_catalog("你好")
    assert p2 == "casual"
    print("PASS catalog casual")

    p3, _, _ = resolve_profile_from_catalog(
        "继续",
        episodic_profile="policy_explain",
    )
    assert p3 == "policy_explain", p3
    print("PASS catalog episodic_continue")

    p4, _, _ = resolve_profile_from_catalog(
        "那23年呢",
        episodic_profile="policy_explain",
    )
    assert p4 == "policy_explain", p4
    print("PASS catalog episodic 那23年呢")

    p5, sc5, _ = resolve_profile_from_catalog(
        "2022年股息利息一共多少",
        has_dataset=True,
    )
    assert p5 == "classified_income", (p5, sc5)
    p6, _, _ = resolve_profile_from_catalog("我有多少股息要报", has_dataset=False)
    assert p6 == "policy_qa", p6
    print("PASS catalog classified_income (dataset-gated)")

    assert matches_multi_scope("每个年度的汇率")
    print("PASS catalog multi_scope")

    plan = build_filing_turn_plan(
        "22年到24年的汇率的使用是否正确？",
        default_tax_year=2025,
        has_dataset=True,
        has_compute=False,
    )
    assert plan.profile == "policy_explain"
    assert plan.intent_score > 0
    print("PASS harness_plan via catalog")

    msgs = build_tax_chat_message_stack(
        system_soul="你是报税助手",
        task_text="解读汇率",
        filing_ledger="【报税助手 · 会话锚点】\n- 关注年度: 2023",
        episodic_block="【上轮对话摘要】\n- 用户：22年汇率",
        raw_user_message="那23年呢",
    )
    assert msgs[0]["role"] == "system"
    assert "解读汇率" in msgs[0]["content"]
    assert msgs[-1]["content"] == "那23年呢"
    ledger_msgs = [m for m in msgs if FILING_LEDGER_PREAMBLE in m.get("content", "")]
    assert len(ledger_msgs) == 1
    assert msgs.index(ledger_msgs[0]) < msgs.index(msgs[-1])
    print("PASS chat_message_stack recency layout")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
