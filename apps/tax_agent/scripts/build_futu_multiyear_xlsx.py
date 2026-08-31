#!/usr/bin/env python3
"""Build Futu multi-year tax statement xlsx (2022–2024 synthetic anonymized)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "fixtures" / "broker" / "futu_multiyear_tax_statement.xlsx"

ROWS = [
    ["富途证券 Futu Securities", "年度账单 / Tax Statement", "USD 美股子账户"],
    ["Date", "Type", "Symbol", "Description", "Amount", "Tax"],
    # 2022
    ["2022-03-10", "Dividend", "MSFT", "Ordinary Dividend", 80.00, 12.00],
    ["2022-06-20", "Trade", "TSLA", "Sell 5 shares (realized P/L approx)", 150.00, ""],
    ["2022-12-31", "Interest", "", "USD cash interest", 3.00, ""],
    # 2023
    ["2023-02-14", "Dividend", "AAPL", "Ordinary Dividend", 60.00, 9.00],
    ["2023-05-08", "Trade", "AAPL", "Sell 8 shares", 100.00, ""],
    ["2023-09-15", "Dividend", "MSFT", "Ordinary Dividend", 40.00, 6.00],
    ["2023-11-01", "Interest", "", "USD cash interest", 4.50, ""],
    # 2024 (aligned with single-year fixture)
    ["2024-03-01", "Dividend", "AAPL", "Ordinary Dividend", 50.00, 7.50],
    ["2024-07-15", "Trade", "AAPL", "Sell 10 shares", 200.00, ""],
    ["2024-08-01", "Interest", "", "USD cash interest", 5.00, ""],
    ["2024-09-01", "Tax", "", "Withholding adjustment", -7.50, ""],
]


def main() -> int:
    try:
        import openpyxl
    except ImportError:
        print("SKIP: openpyxl not installed", flush=True)
        return 0

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transaction History"
    for row in ROWS:
        ws.append(row)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
