#!/usr/bin/env python3
"""
Parse Futu multi-year tax statement (xlsx) and compute CN resident US equity tax per year.

Usage:
  python scripts/build_futu_multiyear_xlsx.py
  python scripts/run_futu_multiyear_compute.py
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.compute_engine import ComputeEngine, ComputeRequest
from tax_agent.fx import apply_fx_to_events
from tax_agent.models import ResidentStatus
from tax_agent.parser.broker_parser import BrokerParser

XLSX = ROOT / "tests" / "fixtures" / "broker" / "futu_multiyear_tax_statement.xlsx"
YEARS = (2022, 2023, 2024)


def main() -> int:
    if not XLSX.is_file():
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_futu_multiyear_xlsx.py")],
            check=False,
            cwd=str(ROOT),
        )
    if not XLSX.is_file():
        print("FAIL: missing futu_multiyear_tax_statement.xlsx (install openpyxl)")
        return 1

    parsed = BrokerParser(template_id="broker_futu_v1").parse_path(XLSX)
    if parsed.broker_template_id != "broker_futu_v1":
        print(f"FAIL: template {parsed.broker_template_id}")
        return 1
    if not parsed.events:
        print("FAIL: no events parsed from xlsx", parsed.warnings, parsed.errors)
        return 1

    fx_events = apply_fx_to_events(
        parsed.events,
        policy="safe_harbor_monthly",
    )
    engine = ComputeEngine()

    print("=== 富途年度账单 · 中国税务居民 · 美股境外所得（多年测算）===")
    print(f"文件: {XLSX.name}")
    print(f"解析: {len(fx_events)} 条事件 | 模板: {parsed.broker_template_id}")
    if parsed.warnings:
        print("解析提示:", "; ".join(parsed.warnings[:3]))
    print()

    by_year = Counter(e.trade_date[:4] for e in fx_events)
    print("事件分布:", dict(sorted(by_year.items())))
    print()
    print(f"{'年度':<6} {'风险':<8} {'应税(CNY)':>12} {'应纳税':>10} {'可抵免':>10} {'应补':>10} {'状态':<8}")
    print("-" * 72)

    total_net = Decimal("0")
    for year in YEARS:
        year_events = [e for e in fx_events if e.trade_date.startswith(str(year))]
        if not year_events:
            print(f"{year:<6} {'—':<8} {'(无事件)':>12}")
            continue
        result = engine.compute(
            ComputeRequest(
                events=year_events,
                tax_year=year,
                resident_status=ResidentStatus.CN_TAX_RESIDENT,
                fx_policy="safe_harbor_monthly",
                broker_template_id="broker_futu_v1",
                data_quality=parsed.data_quality,
            )
        )
        s = result.summary
        net = Decimal(s.get("netTaxDueCny", "0"))
        total_net += net
        print(
            f"{year:<6} {result.risk_level.value:<8} "
            f"{s.get('taxableIncomeCny', '0'):>12} "
            f"{s.get('taxDueCny', '0'):>10} "
            f"{s.get('creditAllowedCny', '0'):>10} "
            f"{s.get('netTaxDueCny', '0'):>10} "
            f"{result.status:<8}"
        )
        if result.triggered_risk_rules:
            print(f"       风险: {', '.join(result.triggered_risk_rules)}")
        if result.notes:
            print(f"       备注: {result.notes[0][:80]}")

    print("-" * 72)
    print(f"三年应补合计（参考）: {total_net.quantize(Decimal('0.01'))} 元")
    print()
    print("说明:")
    print("- 富途 Trade 行金额为成交/盈亏近似，正式申报建议核对已实现损益。")
    print("- 每年需在中国个税 App 按纳税年度分别办理境外所得申报/汇算。")
    print("- 本工具不代申报；中等风险时可能仅给出区间估算。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
