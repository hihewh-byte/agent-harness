#!/usr/bin/env python3
"""Real Ollama narration smoke (Tax Chat Experience v2 · Phase A).

Set TAX_OLLAMA_SMOKE=1 to run against local Ollama; otherwise SKIP (non-blocking).
"""

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def _ollama_up() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def main() -> int:
    enabled = (os.environ.get("TAX_OLLAMA_SMOKE") or "").strip().lower() in ("1", "true", "yes")
    if not enabled:
        print("SKIP ollama smoke (set TAX_OLLAMA_SMOKE=1)")
        return 0
    if not _ollama_up():
        print("SKIP ollama not reachable at 127.0.0.1:11434")
        return 0

    from tax_agent.answer_composer import compose_grounded_reply
    from tax_agent.fx_rates import FxRateProvider
    from tax_agent.policy_kb import try_policy_qa_fast_turn
    from tax_agent.session_context import SessionContext
    from tax_agent.tax_provenance import try_provenance_fast_turn

    provider = FxRateProvider.from_snapshot_dir(SNAP)
    assert provider

    ctx = SessionContext(
        dataset_id=None,
        tax_year=2025,
        fx_policy="cn_supplemental",
        fx_provider=provider,
    )
    turn = try_provenance_fast_turn("22年的补申报的汇率是如何确定的", ctx)
    assert turn and turn.fact_bundle

    model = os.environ.get("TAX_OLLAMA_SMOKE_MODEL") or "qwen2.5:1.5b-instruct"
    narrated_hits = 0
    for attempt in range(2):
        composed = compose_grounded_reply(
            turn.fact_bundle,
            user_message="22年的补申报的汇率是如何确定的",
            llm_on=True,
            model_override=model,
        )
        fb = composed.fallback_reason or "none"
        has_rate = "6.3757" in composed.reply
        print(
            f"  provenance[{attempt}] narrated={composed.narrated} fallback={fb} "
            f"rate={has_rate} len={len(composed.reply)}"
        )
        if composed.narrated and not composed.reply.lstrip().startswith("##"):
            narrated_hits += 1
        elif not composed.narrated:
            assert has_rate, composed.reply[:200]
    assert narrated_hits >= 1, "expected ≥1 narrated provenance reply in 2 attempts"
    print("PASS A2-ollama provenance narrated (non-template)")

    pturn = try_policy_qa_fast_turn("境外股票赚的钱要交税吗", SessionContext(dataset_id=None, tax_year=2024))
    assert pturn and pturn.fact_bundle
    policy_hits = 0
    for attempt in range(2):
        pcomposed = compose_grounded_reply(
            pturn.fact_bundle,
            user_message="境外股票赚的钱要交税吗",
            llm_on=True,
            model_override=model,
        )
        assert "申报" in pcomposed.reply or "财产转让" in pcomposed.reply
        cite_ok = (pcomposed.composer_meta.get("citationAudit") or {}).get("ok")
        print(
            f"  policy[{attempt}] narrated={pcomposed.narrated} "
            f"fallback={pcomposed.fallback_reason} cite_ok={cite_ok}"
        )
        if pcomposed.narrated and cite_ok:
            policy_hits += 1
    assert policy_hits >= 1, "expected ≥1 policy narrated+citation pass in 2 attempts"
    print("PASS C3-ollama policy_qa narrated+citation")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
