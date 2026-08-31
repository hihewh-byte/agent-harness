#!/usr/bin/env python3
"""Tax provenance / policy_explain lane selfcheck."""

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.fx_rates import FxRateProvider
from tax_agent.session_context import SessionContext
from tax_agent.tax_intent_router import resolve_tax_intent
from tax_agent.tax_provenance import (
    build_fx_provenance,
    format_fx_provenance_reply_zh,
    infer_provenance_years,
    try_provenance_fast_turn,
)
from tax_agent.tax_turn_resolver import resolve_turn_scope

SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def main() -> int:
    provider = FxRateProvider.from_snapshot_dir(SNAP)
    assert provider

    prov = build_fx_provenance(
        tax_year=2021,
        fx_policy="cn_supplemental",
        filing_date="2026-04-15",
        provider=provider,
    )
    assert prov["monthKey"] == "2020-12", prov
    assert prov["rate"] == "6.5249", prov
    assert "2020-12-31" in prov["ruleLabel"]
    reply = format_fx_provenance_reply_zh(prov)
    assert "6.5249" in reply
    assert "实施条例" in reply
    print("PASS build_fx_provenance 2021 → 2020-12")

    plan = resolve_tax_intent("这里的汇率是如何计算的？依据是什么？", default_tax_year=2021)
    assert plan.profile == "policy_explain"
    print("PASS resolve_tax_intent policy_explain")

    ctx = SessionContext(
        dataset_id=None,
        tax_year=2021,
        fx_policy="cn_supplemental",
        fx_provider=provider,
    )
    turn = try_provenance_fast_turn("汇率依据是什么", ctx)
    assert turn and "6.5249" in turn.reply
    print("PASS provenance fast path")

    ctx2 = SessionContext(
        dataset_id=None,
        tax_year=2025,
        fx_policy="cn_supplemental",
        fx_provider=provider,
    )
    turn2 = try_provenance_fast_turn("22年到24年的汇率的使用是否正确？", ctx2)
    assert turn2 and "2022" in turn2.reply and "2024" in turn2.reply
    assert "6.3757" in turn2.reply and "6.9646" in turn2.reply and "7.0827" in turn2.reply
    assert "2025 年度" not in turn2.reply
    print("PASS multi-year provenance 2022-2024")

    turn3 = try_provenance_fast_turn("22年的补申报的汇率是如何确定的", ctx2)
    assert turn3 and "## 2022 年度" in turn3.reply, turn3.reply[:200] if turn3 else ""
    assert "6.3757" in turn3.reply
    assert "## 2025 年度" not in turn3.reply
    print("PASS 22年 → 2022 supplemental FX")

    dq = {"futuTaxPackages": [{"taxYear": y} for y in (2021, 2022, 2023)]}
    all_years = infer_provenance_years(
        "每个年度的汇率是如何确定的",
        2025,
        data_quality=dq,
        fx_provider=provider,
    )
    assert all_years == [2021, 2022, 2023]
    scope = resolve_turn_scope(
        "每个年度的汇率是如何确定的",
        2025,
        data_quality=dq,
        fx_provider=provider,
    )
    assert scope.year_source == "uploaded_all"
    print("PASS 每个年度 → uploaded years")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
