#!/usr/bin/env python3
"""TaxTurnResolver + EpisodicState 黄金多轮用例 M1–M4（agent-consensus v1.6）。"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.fx_rates import FxRateProvider
from tax_agent.session_context import SessionContext
from tax_agent.session_turn_focus import (
    get_tax_session_focus,
    record_turn_focus,
    revive_tax_session_focus,
)
from tax_agent.tax_provenance import try_provenance_fast_turn
from tax_agent.tax_turn_resolver import resolve_turn_scope, try_clarify_turn


SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def _fx_provider() -> FxRateProvider:
    p = FxRateProvider.from_snapshot_dir(SNAP)
    assert p and p.available, "fx provider required"
    return p


def _dq(years: list[int]) -> dict:
    return {"futuTaxPackages": [{"taxYear": y} for y in years], "yearsPresent": years}


def main() -> int:
    provider = _fx_provider()
    fx_years = provider.list_supplemental_tax_years()
    assert fx_years, "fx dataset years empty"
    assert 2022 in fx_years and 2023 in fx_years

    scope1 = resolve_turn_scope(
        "22年的补申报的汇率是如何确定的",
        2025,
        data_quality=_dq([2021, 2022, 2023]),
        fx_provider=provider,
    )
    assert scope1.tax_years == [2022], scope1
    assert scope1.year_source == "explicit"
    print("PASS M1a explicit 22年 → 2022")

    with tempfile.TemporaryDirectory() as td:
        os.environ["TAX_AGENT_DB"] = str(Path(td) / "t.db")
        sid = "m1-session"
        ctx = SessionContext(
            session_id=sid,
            tax_year=2025,
            fx_provider=provider,
            fx_policy="cn_supplemental",
            data_quality=_dq([2021, 2022, 2023]),
        )
        turn1 = try_provenance_fast_turn("22年的补申报的汇率是如何确定的", ctx)
        assert turn1 and "6.3757" in turn1.reply and "## 2022" in turn1.reply
        record_turn_focus(
            sid,
            tax_year=2022,
            tax_years=[2022],
            profile="policy_explain",
            user_message="22年的补申报的汇率是如何确定的",
            assistant_reply=turn1.reply,
            mode="provenance_fast",
        )
        scope2 = resolve_turn_scope(
            "那23年呢",
            2025,
            data_quality=ctx.data_quality,
            fx_provider=provider,
            episodic=get_tax_session_focus(sid),
        )
        assert scope2.tax_years == [2023], scope2
        ctx.tax_year = 2023
        turn2 = try_provenance_fast_turn("那23年呢", ctx)
        assert turn2 and "6.9646" in turn2.reply and "## 2023" in turn2.reply
        assert "## 2025" not in turn2.reply
    print("PASS M1 22年 → 那23年呢 → 6.9646")

    scope_multi = resolve_turn_scope(
        "每个年度的汇率是如何确定的",
        2025,
        data_quality=_dq([2021, 2022, 2023]),
        fx_provider=provider,
    )
    assert scope_multi.tax_years == [2021, 2022, 2023]
    assert scope_multi.year_source == "uploaded_all"
    assert not scope_multi.needs_clarification
    ctx2 = SessionContext(tax_year=2025, fx_provider=provider, data_quality=_dq([2021, 2022, 2023]))
    turn3 = try_provenance_fast_turn("每个年度的汇率是如何确定的", ctx2)
    assert turn3 and "2021" in turn3.reply and "2023" in turn3.reply
    assert "2025 年度" not in turn3.reply
    print("PASS M2 每个年度 → uploaded 2021-2023")

    with tempfile.TemporaryDirectory() as td2:
        os.environ["TAX_AGENT_DB"] = str(Path(td2) / "t2.db")
        sid2 = "m3-session"
        record_turn_focus(
            sid2,
            tax_year=2022,
            tax_years=[2022],
            profile="policy_explain",
            user_message="22年汇率",
            assistant_reply="## 2022 年度汇率依据",
            mode="provenance_fast",
        )
        f = get_tax_session_focus(sid2)
        assert f and f.turns_remaining == 8
        revived3 = revive_tax_session_focus(sid2, "继续")
        scope3 = resolve_turn_scope(
            "继续",
            2025,
            data_quality=_dq([2022]),
            fx_provider=provider,
            episodic=revived3,
        )
        assert scope3.year_source == "focus"
        assert scope3.tax_years == [2022]
    print("PASS M3 快车道后「继续」→ focus")

    scope4 = resolve_turn_scope(
        "补缴汇率是多少",
        2025,
        data_quality=_dq([2021, 2022, 2023]),
        fx_provider=provider,
    )
    assert scope4.needs_clarification
    clarify = try_clarify_turn(scope4)
    assert clarify and clarify.action == "clarify"
    assert "2021" in clarify.reply and "2023" in clarify.reply
    print("PASS M4 无年份多年上传 → clarify")

    scope_fx_only = resolve_turn_scope(
        "每个年度的汇率是如何确定的",
        2025,
        fx_provider=provider,
    )
    assert scope_fx_only.year_source == "fx_dataset"
    assert scope_fx_only.tax_years == fx_years
    assert 2021 not in scope_fx_only.tax_years or 2021 in fx_years
    print("PASS fx_dataset years (no hardcoded 2021-2025)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
