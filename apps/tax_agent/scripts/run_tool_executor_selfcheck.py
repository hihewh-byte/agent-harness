#!/usr/bin/env python3
"""Deterministic tool executor checks (no Ollama)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.session_context import SessionContext
from tax_agent.tool_executor import apply_tool_call, apply_tool_calls


def main() -> int:
    ctx = SessionContext(
        dataset_id="ds-1",
        last_run_id="run-9",
        tax_year=2024,
    )
    t = apply_tool_call("compute_tax", {"tax_year": 2024}, ctx)
    assert t.action == "compute"
    assert t.compute_params["taxYear"] == 2024
    assert t.compute_params["filingScope"] == "foreign_only"
    print("PASS compute_tax")

    ctx_dom = SessionContext(
        dataset_id="ds-1",
        tax_year=2024,
        filing_scope="includes_domestic",
        domestic_income_provided=False,
    )
    t_dom = apply_tool_call(
        "compute_tax",
        {"tax_year": 2024, "filing_scope": "includes_domestic"},
        ctx_dom,
    )
    assert t_dom.compute_params["filingScope"] == "includes_domestic"
    assert "R008" in t_dom.reply
    print("PASS compute_tax includes_domestic R008 hint")

    empty = SessionContext()
    t2 = apply_tool_call("compute_tax", {"tax_year": 2023}, empty)
    assert t2.action == "need_upload"
    print("PASS compute_tax blocked without dataset")

    t3, ex = apply_tool_calls(
        [
            {
                "function": {
                    "name": "reply_only",
                    "arguments": {"reply": "说明"},
                }
            },
            {
                "function": {
                    "name": "compute_tax",
                    "arguments": {"tax_year": 2024},
                }
            },
        ],
        ctx,
    )
    assert ex == ["reply_only", "compute_tax"]
    assert t3 and t3.action == "compute"
    print("PASS tool priority")

    t4 = apply_tool_call("show_report", {}, ctx)
    assert t4.action == "show_report"
    assert t4.compute_params["runId"] == "run-9"
    print("PASS show_report default runId")

    from tax_agent.coverage_check import build_coverage_report

    ctx_cov = SessionContext(
        dataset_id="ds-1",
        data_quality={
            "futuTaxPackages": [
                {"taxYear": 2022, "tradeLegs": []},
                {"taxYear": 2023, "tradeLegs": []},
            ]
        },
    )
    t5 = apply_tool_call("check_coverage", {}, ctx_cov)
    assert t5.action == "none"
    assert "材料覆盖" in t5.reply
    rep = build_coverage_report(data_quality=ctx_cov.data_quality)
    assert 2022 in rep["uploadedYears"]
    print("PASS check_coverage")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
