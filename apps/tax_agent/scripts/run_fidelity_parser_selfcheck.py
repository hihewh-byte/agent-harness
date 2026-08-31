#!/usr/bin/env python3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.models import EventType
from tax_agent.parser.broker_parser import BrokerParser
from tax_agent.parser.fidelity_parser import merge_fidelity_events, parse_fidelity_csv

FIX = ROOT / "tests" / "fixtures" / "broker" / "fidelity_activity_realistic.csv"
FIX_GL = ROOT / "tests" / "fixtures" / "broker" / "fidelity_gains_losses.csv"
FIX_XLSX = ROOT / "tests" / "fixtures" / "broker" / "fidelity_multi_sheet.xlsx"


def main() -> int:
    r = BrokerParser().parse_path(FIX)
    assert r.broker_template_id == "broker_fidelity_v1", r.broker_template_id
    c = Counter(e.event_type for e in r.events)
    assert c[EventType.DIVIDEND] >= 1
    assert c[EventType.INTEREST] >= 1
    assert c[EventType.WITHHOLDING_TAX] >= 1
    assert c[EventType.CAPITAL_GAIN] >= 1
    print("PASS fidelity history:", dict(c))

    gl_text = FIX_GL.read_text(encoding="utf-8")
    gl_events, _, _ = parse_fidelity_csv(gl_text, FIX_GL.name)
    assert len(gl_events) == 2
    assert all(":fgl:" in e.source_row_ref for e in gl_events)
    assert all(e.classification_status == "confirmed" for e in gl_events)

    merged = merge_fidelity_events([r.events, gl_events])
    cg = [e for e in merged if e.event_type == EventType.CAPITAL_GAIN]
    assert len(cg) == 2
    assert all(":fgl:" in e.source_row_ref for e in cg)
    print("PASS fidelity G/L merge:", len(merged), "events")

    if not FIX_XLSX.exists():
        import subprocess

        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_fidelity_sample_xlsx.py")],
            check=True,
        )
    rx = BrokerParser().parse_path(FIX_XLSX)
    assert rx.broker_template_id == "broker_fidelity_v1", rx.broker_template_id
    cg_x = [e for e in rx.events if e.event_type == EventType.CAPITAL_GAIN]
    assert len(cg_x) == 2, f"expected 2 confirmed CG from xlsx, got {len(cg_x)}"
    assert all(":fgl:" in e.source_row_ref for e in cg_x)
    print("PASS fidelity xlsx multi-sheet:", len(rx.events), "events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
