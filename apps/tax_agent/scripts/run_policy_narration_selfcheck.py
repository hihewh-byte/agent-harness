#!/usr/bin/env python3
"""Phase C3: policy_qa citation narration stability."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.answer_composer import _ensure_policy_citations, compose_grounded_reply
from tax_agent.citation_audit import audit_policy_citations
from tax_agent.policy_kb import try_policy_qa_fast_turn
from tax_agent.session_context import SessionContext


def _mock_no_cite(bundle, **kwargs):
    return "境外股票所得需要依法申报，适用税法相关规定。", ""


def _mock_book_title(bundle, **kwargs):
    return "需要申报。依据《个人所得税法》第一条相关规定。", ""


def main() -> int:
    cites = [{"id": "kb:cn-iit-art1", "label": "个人所得税法第一条"}]
    assert audit_policy_citations("依据《个人所得税法》第一条", cites).ok
    assert audit_policy_citations("依据【个人所得税法第一条】", cites).ok
    print("PASS C3-1 citation_audit normalized match")

    turn = try_policy_qa_fast_turn("境外股票赚的钱要交税吗", SessionContext(dataset_id=None, tax_year=2024))
    assert turn and turn.fact_bundle
    patched = _ensure_policy_citations(_mock_no_cite(turn.fact_bundle)[0], turn.fact_bundle)
    assert "依据【" in patched
    assert audit_policy_citations(patched, turn.fact_bundle.citations_dicts()).ok
    print("PASS C3-2 ensure_policy_citations T0 suffix")

    composed = compose_grounded_reply(
        turn.fact_bundle,
        user_message="境外股票赚的钱要交税吗",
        llm_on=True,
        narrate_fn=_mock_no_cite,
    )
    assert composed.narrated
    assert composed.fallback_reason in (None, "none") or composed.narrated
    assert "依据【" in composed.reply
    assert composed.composer_meta.get("citationAudit", {}).get("ok") is True
    print("PASS C3-3 compose policy narrated + citation audit")

    composed2 = compose_grounded_reply(
        turn.fact_bundle,
        user_message="境外股票赚的钱要交税吗",
        llm_on=True,
        narrate_fn=_mock_book_title,
    )
    assert composed2.narrated
    assert audit_policy_citations(composed2.reply, turn.fact_bundle.citations_dicts()).ok
    print("PASS C3-4 book-title style passes audit")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
