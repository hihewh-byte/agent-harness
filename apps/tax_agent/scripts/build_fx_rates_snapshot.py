#!/usr/bin/env python3
"""Generate fx_rates.yaml for a rule snapshot from curated PBOC middle-rate data."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "data" / "pboc_usd_cny_middle.yaml"
DEFAULT_SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def _yearly_averages(monthly: dict[str, str]) -> dict[str, str]:
    buckets: dict[str, list[Decimal]] = defaultdict(list)
    for key, val in monthly.items():
        year = key.split("-")[0]
        buckets[year].append(Decimal(str(val)))
    return {
        year: str((sum(vals) / len(vals)).quantize(Decimal("0.0001")))
        for year, vals in sorted(buckets.items())
    }


def build_fx_rates(src: Path, *, version: str | None = None) -> dict:
    data = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    monthly = data.get("monthly") or {}
    if not monthly:
        raise ValueError(f"no monthly rates in {src}")
    ver = version or str(data.get("version") or "2026.06.01")
    return {
        "version": ver,
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
    p = argparse.ArgumentParser(description="Build fx_rates.yaml for rule snapshot")
    p.add_argument("--src", type=Path, default=DEFAULT_SRC)
    p.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAP)
    p.add_argument("--version", type=str, default=None)
    args = p.parse_args()
    out = build_fx_rates(args.src.resolve(), version=args.version)
    dest = args.snapshot_dir / "fx_rates.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        yaml.dump(out, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"wrote {dest} ({len(out['monthly'])} months, {len(out['yearlyAverage'])} years)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
