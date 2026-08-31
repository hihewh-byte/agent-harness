#!/usr/bin/env python3
"""Self-check: template_unknown -> apply column mapping -> events -> compute."""

from __future__ import annotations

import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.fx import apply_fx_to_events
from tax_agent.models import EventType, ResidentStatus
from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.parser.template_mapper import suggest_column_mapping
from tax_agent.store_base import InMemoryDatasetStore
from tax_agent.storage.sqlite_store import SqliteDatasetStore

UNKNOWN_CSV = ROOT / "tests" / "fixtures" / "broker" / "unknown_generic.csv"
UNKNOWN_XLSX = ROOT / "tests" / "fixtures" / "broker" / "unknown_generic.xlsx"


def _column_mapping_from_hints(hints: dict) -> dict[str, str]:
    return {
        field: meta["header"]
        for field, meta in (hints.get("suggestedMapping") or {}).items()
        if meta.get("header")
    }


def _exercise_file(store, path: Path, label: str) -> list[str]:
    failures: list[str] = []
    parse = BrokerParser().parse_path(path)
    if parse.broker_template_id != "template_unknown":
        failures.append(f"{label}: expected template_unknown")
        return failures

    stored = store.save_parse(parse)
    raw = (stored.data_quality or {}).get("_rawRows")
    if not raw:
        failures.append(f"{label}: missing _rawRows")

    hints = suggest_column_mapping(parse.detected_headers)
    mapping = _column_mapping_from_hints(hints)
    if "tradeDate" not in mapping or "grossAmount" not in mapping:
        failures.append(f"{label}: incomplete suggested mapping")

    applied = store.apply_column_mapping(stored.dataset_id, mapping)
    if not applied:
        failures.append(f"{label}: apply_column_mapping returned None")
        return failures

    if applied.broker_template_id != "broker_generic_mapped_v1":
        failures.append(f"{label}: broker_template_id={applied.broker_template_id}")
    if len(applied.events) < 2:
        failures.append(f"{label}: expected >=2 events, got {len(applied.events)}")

    counts = Counter(e.event_type for e in applied.events)
    if counts[EventType.CAPITAL_GAIN] < 1 or counts[EventType.DIVIDEND] < 1:
        failures.append(f"{label}: event mix unexpected: {dict(counts)}")

    events = apply_fx_to_events(list(applied.events))
    result = ComputeEngine().compute(
        ComputeRequest(
            events=events,
            tax_year=2024,
            resident_status=ResidentStatus.CN_TAX_RESIDENT,
            data_quality=applied.data_quality,
            broker_template_id=applied.broker_template_id,
        )
    )
    if result.status not in ("ok", "partial"):
        failures.append(f"{label}: compute status={result.status}")
    if "R005" not in result.triggered_risk_rules:
        failures.append(f"{label}: expected R005 for mapped template")

    return failures


def _exercise(store, label: str) -> list[str]:
    return _exercise_file(store, UNKNOWN_CSV, label)


def main() -> int:
    failures = _exercise(InMemoryDatasetStore(), "memory")
    with tempfile.TemporaryDirectory() as d:
        failures += _exercise(SqliteDatasetStore(Path(d) / "t.db"), "sqlite")

    import subprocess

    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_unknown_generic_xlsx.py")], check=False)
    if UNKNOWN_XLSX.exists():
        try:
            failures += _exercise_file(InMemoryDatasetStore(), UNKNOWN_XLSX, "memory-xlsx")
        except ImportError as e:
            print("SKIP xlsx:", e)
    else:
        print("SKIP xlsx: fixture not built (openpyxl missing?)")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: generic mapped parser apply + compute ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
