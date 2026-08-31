#!/usr/bin/env python3
"""Generate fx_rates.yaml for each snapshot from curated PBOC middle-rate data."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = REPO_ROOT / "data" / "pboc_usd_cny_middle.yaml"


def _yearly_averages(monthly: dict[str, str]) -> dict[str, str]:
    buckets: dict[str, list[Decimal]] = defaultdict(list)
    for key, val in monthly.items():
        year = key.split("-")[0]
        buckets[year].append(Decimal(str(val)))
    return {
        year: str((sum(vals) / len(vals)).quantize(Decimal("0.0001")))
        for year, vals in sorted(buckets.items())
    }


def build_fx_rates(src: Path, *, version: str) -> dict:
    data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    monthly = data.get("monthly") or {}
    if not monthly:
        raise ValueError(f"no monthly rates in {src}")
    return {
        "version": version,
        "base": "USD",
        "quote": "CNY",
        "source": str(data.get("source") or "pboc_middle_rate_curated"),
        "sourceLabelZh": str(
            data.get("sourceLabelZh") or "中国人民银行美元对人民币汇率中间价"
        ),
        "monthly": {k: str(v) for k, v in sorted(monthly.items())},
        "yearlyAverage": _yearly_averages(monthly),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Build fx_rates.yaml for all snapshots")
    p.add_argument("--src", type=Path, default=DEFAULT_SRC)
    p.add_argument("--snapshots-dir", type=Path, default=REPO_ROOT / "snapshots")
    args = p.parse_args()
    src = args.src.resolve()
    if not src.is_file():
        print(f"missing {src}", file=sys.stderr)
        return 1

    count = 0
    for snap_dir in sorted(args.snapshots_dir.iterdir()):
        if not snap_dir.is_dir():
            continue
        version = snap_dir.name
        out = build_fx_rates(src, version=version)
        dest = snap_dir / "fx_rates.yaml"
        dest.write_text(
            yaml.dump(out, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        count += 1
        print(f"wrote {dest} ({len(out['monthly'])} months)")
    if count == 0:
        print("no snapshot directories found", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
