#!/usr/bin/env python3
"""Self-check for template_unknown column mapping hints."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.parser.template_mapper import suggest_column_mapping

UNKNOWN_CSV = ROOT / "tests" / "fixtures" / "broker" / "unknown_generic.csv"


def main() -> int:
    failures: list[str] = []

    headers = ["Trade Date", "Ticker", "Txn Type", "Net Amount", "Withholding Tax", "Commission"]
    hints = suggest_column_mapping(headers)
    mapping = hints.get("suggestedMapping") or {}
    if "tradeDate" not in mapping:
        failures.append("tradeDate not suggested for Trade Date header")
    if "grossAmount" not in mapping:
        failures.append("grossAmount not suggested for Net Amount header")
    if not hints.get("nextSteps"):
        failures.append("nextSteps empty")

    assert UNKNOWN_CSV.exists(), f"missing fixture {UNKNOWN_CSV}"
    parse = BrokerParser().parse_path(UNKNOWN_CSV)
    if parse.broker_template_id != "template_unknown":
        failures.append(f"expected template_unknown, got {parse.broker_template_id}")
    if not parse.mapping_hints:
        failures.append("broker_parser did not attach mapping_hints")
    if parse.events:
        failures.append("template_unknown should not emit events")
    if not any("mappingHints" in w or "mapping" in w.lower() for w in parse.warnings):
        failures.append("expected mapping warning in parse.warnings")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print(
        "PASS template_mapper:",
        f"fields={list(mapping.keys())}",
        f"guessed={hints.get('guessedTemplateId')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
