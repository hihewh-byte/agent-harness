#!/usr/bin/env python3
"""LLM orchestrator self-check (requires Ollama + text model for full pass)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.chat_orchestrator import orchestrate_user_message
from tax_agent.llm_model_resolver import resolve_tax_agent_model, recommended_model_doc_zh
from tax_agent.llm_orchestrator import SessionContext, get_llm_status, llm_enabled, orchestrate_with_llm


def main() -> int:
    if not llm_enabled():
        turn = orchestrate_user_message("申报材料清单", dataset_id="fake-id", last_run_id=None)
        assert turn.action in ("none", "compute")
        print("SKIP llm: TAX_AGENT_LLM_ENABLED=0 — PASS rules fallback only")
        return 0

    print("=== Tax Agent LLM status ===")
    try:
        status = get_llm_status()
    except FileNotFoundError as e:
        print("SKIP: PHA not found:", e)
        return 0

    print("enabled:", status["enabled"])
    print("resolved:", status["resolvedModel"], status["resolutionReason"])
    print("recommended:", status["recommendedModel"])
    print(recommended_model_doc_zh()[:200], "...")

    # Rules always work
    turn = orchestrate_user_message("申报材料清单", dataset_id="fake-id", last_run_id=None)
    assert turn.action in ("none", "compute")
    print("PASS rules fallback")

    if not status["resolvedModel"]:
        print("SKIP llm chat: no model —", status["resolutionReason"])
        return 0

    ctx = SessionContext(
        dataset_id="00000000-0000-0000-0000-000000000099",
        tax_year=2024,
        event_count=5,
        broker_template_id="broker_schwab_v1",
        event_counts={"DIVIDEND": 2, "CAPITAL_GAIN": 1},
    )
    turn, meta = orchestrate_with_llm("按 2024 年帮我测算一下要补多少税", ctx)
    print("LLM meta:", meta)
    assert meta.get("mode") in ("llm", "llm_tools"), meta
    if meta.get("mode") == "llm_tools":
        assert meta.get("toolsExecuted"), meta
    assert turn.action in ("compute", "need_upload", "clarify", "none")
    assert len(turn.reply) > 10
    print("PASS llm orchestrate:", turn.action)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
