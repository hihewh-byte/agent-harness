#!/usr/bin/env python3
"""Verify SQLite store survives reload and chat history."""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.storage.sqlite_store import SqliteDatasetStore
from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.fx import apply_fx_to_events
from tax_agent.models import ResidentStatus

XLSX = ROOT / "tests" / "fixtures" / "broker" / "ibkr_mini.xlsx"


def main() -> int:
    if not XLSX.exists():
        import subprocess

        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_ibkr_sample_xlsx.py")], check=True)

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "test.db"
        s1 = SqliteDatasetStore(db)
        parse = BrokerParser(template_id="broker_ibkr_v1").parse_path(XLSX)
        stored = s1.save_parse(parse)
        s1.append_chat(stored.session_id, "user", "按 2024 年测算")

        s2 = SqliteDatasetStore(db)
        loaded = s2.get(stored.dataset_id)
        assert loaded and len(loaded.events) == len(stored.events)
        hist = s2.list_chat(stored.session_id)
        assert len(hist) == 1

        events = apply_fx_to_events(loaded.events)
        result = ComputeEngine().compute(
            ComputeRequest(
                events=events,
                tax_year=2024,
                resident_status=ResidentStatus.CN_TAX_RESIDENT,
                data_quality=loaded.data_quality,
                broker_template_id=loaded.broker_template_id,
            )
        )
        s2.save_report(result.run_id, stored.dataset_id, "# test", result)
        s3 = SqliteDatasetStore(db)
        rep = s3.get_report(result.run_id)
        assert rep is not None
        print("PASS sqlite persistence:", db, "events=", len(loaded.events), "run=", result.run_id[:8])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
