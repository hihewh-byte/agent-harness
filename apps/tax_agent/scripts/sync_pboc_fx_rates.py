#!/usr/bin/env python3
"""Fetch recent PBOC USD/CNY month-end rates, update dataset, rebuild snapshot fx_rates.yaml."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.pboc_fetcher import DEFAULT_DATA, sync_recent_months  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Sync PBOC middle rates into rule snapshot")
    p.add_argument("--months", type=int, default=3, help="how many recent months to fetch")
    p.add_argument("--data", type=Path, default=DEFAULT_DATA)
    p.add_argument(
        "--snapshot-dir",
        type=Path,
        default=ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01",
    )
    p.add_argument("--skip-fetch", action="store_true", help="only rebuild fx_rates.yaml from local data")
    args = p.parse_args()

    if not args.skip_fetch:
        try:
            merged = sync_recent_months(months_back=args.months, path=args.data)
            changed = merged.get("_changedMonths") or []
            errs = merged.get("_errors") or []
            if changed:
                print(f"updated months: {', '.join(changed)}")
            else:
                print("no month changes (rates unchanged or fetch empty)")
            if errs:
                print("fetch warnings:", "; ".join(errs))
        except Exception as exc:  # noqa: BLE001
            print(f"fetch failed: {exc}", file=sys.stderr)
            return 1

    build = ROOT / "scripts" / "build_fx_rates_snapshot.py"
    r = subprocess.run(
        [sys.executable, str(build), "--src", str(args.data), "--snapshot-dir", str(args.snapshot_dir)],
        cwd=str(ROOT),
    )
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
