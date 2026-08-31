#!/usr/bin/env python3
"""Build unknown_generic.xlsx fixture (same data as unknown_generic.csv)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "tests" / "fixtures" / "broker" / "unknown_generic.csv"
OUT = ROOT / "tests" / "fixtures" / "broker" / "unknown_generic.xlsx"


def main() -> int:
    try:
        import openpyxl
    except ImportError:
        print("SKIP: openpyxl not installed", file=sys.stderr)
        return 0

    if not CSV.exists():
        print(f"FAIL: missing {CSV}", file=sys.stderr)
        return 1

    lines = CSV.read_text(encoding="utf-8").strip().splitlines()
    rows = [line.split(",") for line in lines]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transactions"
    for r in rows:
        ws.append(r)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
