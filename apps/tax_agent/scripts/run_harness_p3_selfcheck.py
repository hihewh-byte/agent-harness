#!/usr/bin/env python3
"""Harness P3: report schema, placeholder polish, coach APIs."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.harness_plan import build_filing_turn_plan
from tax_agent.harness_report import build_harness_report, format_harness_summary_zh
from tax_agent.numerics_audit import (
    audit_response_numerics,
    freeze_numerics_placeholders,
    placeholders_intact,
    restore_numerics_placeholders,
)
from tax_agent.filing_narrative import should_polish_narrative, compose_filing_narrative_text


def main() -> int:
    manifest = {"1046912", "209382.4"}
    base = "应纳税所得额 1046912 元，税额 209382.4 元。"
    frozen, mapping = freeze_numerics_placeholders(base, manifest)
    assert "{{NUM_" in frozen and len(mapping) >= 2
    restored = restore_numerics_placeholders(frozen, mapping)
    assert "1046912" in restored
    assert placeholders_intact(frozen, mapping)
    bad = frozen.replace(list(mapping.keys())[0], "999")
    assert not placeholders_intact(bad, mapping)
    audit = audit_response_numerics(restored, manifest, strict=True)
    assert audit.ok, audit.unknown
    print("PASS numerics placeholders")

    row = {
        "taxYear": 2023,
        "grossProceedsCny": "100",
        "grossProceedsUsd": "10",
        "costBasisCny": "80",
        "costBasisUsd": "8",
        "reasonableFeeCny": "1",
        "reasonableFeeUsd": "0.1",
        "taxableIncomeCny": "19",
        "netGainCny": "19",
        "taxDueCny": "3.8",
        "fxRate": "7.1",
        "fxPolicy": "cn_supplemental",
        "fxNote": "",
    }
    text = compose_filing_narrative_text(row, tax_year=2023)
    f2, m2 = freeze_numerics_placeholders(text, {"100", "19", "3.8", "7.1"})
    assert m2
    print("PASS narrative freeze")

    assert should_polish_narrative("润色申报说明", llm_on=True)
    assert not should_polish_narrative("润色申报说明", llm_on=False)
    assert not should_polish_narrative("不润色说明", llm_on=True)
    print("PASS polish gate")

    plan = build_filing_turn_plan("申报说明", default_tax_year=2023, has_dataset=True)
    rep = build_harness_report(
        session_id="s1",
        user_message="申报说明",
        plan=plan,
        meta={"mode": "narrative_fast", "narrativePolished": True},
        mode="narrative_fast",
        action="none",
    )
    summary = format_harness_summary_zh(rep)
    assert "filing_narrative" in summary and "polish=1" in summary
    assert rep["schema"] == "tax.harness_report/v2"
    assert "composer" in (rep.get("runtime") or {})
    print("PASS harness report")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
