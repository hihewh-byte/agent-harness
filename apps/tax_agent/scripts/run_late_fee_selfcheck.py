#!/usr/bin/env python3
"""Late fee (滞纳金) self-check."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.late_fee import compute_late_fee, overdue_days, penalty_start_date

Q = Decimal("0.01")


def main() -> int:
    failures: list[str] = []

    if overdue_days(2023, __import__("datetime").date(2024, 6, 30)) != 0:
        failures.append("on deadline should be 0 overdue")
    if overdue_days(2023, __import__("datetime").date(2024, 7, 1)) != 0:
        failures.append("on penalty start day should be 0 overdue")
    days = overdue_days(2023, __import__("datetime").date(2026, 4, 15))
    if days != ( __import__("datetime").date(2026, 4, 15) - penalty_start_date(2023) ).days:
        failures.append(f"overdue days mismatch: {days}")

    lf = compute_late_fee(
        Decimal("215584.54"),
        tax_year=2023,
        filing_date="2026-04-15",
        policy="cn_supplemental",
    )
    if not lf or not lf.get("applicable"):
        failures.append("expected applicable late fee")
    else:
        expected_fee = (Decimal("215584.54") * Decimal("0.0005") * days).quantize(Q)
        if Decimal(lf["lateFeeCny"]) != expected_fee:
            failures.append(f"late fee expected {expected_fee} got {lf['lateFeeCny']}")
        total = (Decimal("215584.54") + expected_fee).quantize(Q)
        if Decimal(lf["totalPayableCny"]) != total:
            failures.append(f"total expected {total} got {lf['totalPayableCny']}")

    zero = compute_late_fee("0", tax_year=2023, filing_date="2026-04-15")
    if zero is not None:
        failures.append("zero tax should return None")

    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print("PASS: late fee selfcheck ok")
    print(f"  2023 tax @ 2026-04-15: overdue {days}d fee {lf['lateFeeCny']} total {lf['totalPayableCny']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
