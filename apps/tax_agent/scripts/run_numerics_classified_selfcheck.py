#!/usr/bin/env python3
"""PR-D: numerics manifest includes classified income amounts (§2.4)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.filing_session_state import FilingSessionState, build_authoritative_filing_report
from tax_agent.futu_session_fifo import finalize_futu_session_dataset
from tax_agent.harness_plan import FilingTurnPlan
from tax_agent.numerics_audit import audit_response_numerics, build_numerics_manifest, _normalize_decimal_token
from tax_agent.parser.broker_parser import BrokerParser

ANNUAL = ROOT / "tests" / "fixtures" / "broker" / "futu_tax_2022_annual.xlsx"
INCOME = ROOT / "tests" / "fixtures" / "broker" / "futu_classified_income_usd.xlsx"


def main() -> int:
    if not ANNUAL.is_file() or not INCOME.is_file():
        import subprocess

        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_futu_classified_income_fixture.py")],
            check=False,
        )
    if not ANNUAL.is_file() or not INCOME.is_file():
        print("SKIP: need futu fixtures")
        return 0

    events_all: list = []
    pkgs: list = []
    for p in (ANNUAL, INCOME):
        pr = BrokerParser(template_id="broker_futu_v1").parse_path(p)
        pkg = (pr.data_quality or {}).get("futuTaxPackage")
        if pkg:
            pkgs.append(pkg)
        events_all.extend(pr.events)

    dq = {"futuTaxPackages": pkgs}
    events, _ = finalize_futu_session_dataset(events_all, dq)
    state = FilingSessionState(
        data_quality=dq,
        events=events,
        focus_tax_year=2022,
    )
    plan = FilingTurnPlan(
        profile="insight_fast",
        focus="insight",
        tax_year=2022,
        journey_phase="computed",
        slots_tier0=(),
        slots_tier1=(),
        forbidden=(),
        tools_allowed=(),
        task_text="",
    )
    manifest = build_numerics_manifest(state, plan)
    rep = build_authoritative_filing_report(state, years=[2022])
    combined = next((r for r in rep.get("combinedRows") or [] if int(r["taxYear"]) == 2022), None)
    assert combined, "missing combined row"
    div_net = combined["classifiedIncome"]["dividend"]["netTaxDueCny"]
    grand_net = combined["grandTotal"]["netTaxDueCny"]
    div_tok = _normalize_decimal_token(div_net)
    grand_tok = _normalize_decimal_token(grand_net)

    failures: list[str] = []
    if div_tok not in manifest:
        failures.append(f"dividend netTaxDueCny {div_net} not in manifest")
    if grand_tok not in manifest:
        failures.append(f"grandTotal netTaxDueCny {grand_net} not in manifest")

    ok_reply = (
        f"2022 年股息应补 {div_net} 元，全税目应补合计 {grand_net} 元。"
    )
    audit_ok = audit_response_numerics(ok_reply, manifest, strict=True)
    if not audit_ok.ok:
        failures.append(f"strict audit failed: {audit_ok.unknown}")

    bad = audit_response_numerics("应补 9999999.99 元", manifest, strict=True)
    if bad.ok:
        failures.append("expected strict audit to fail on fake amount")

    if failures:
        for f in failures:
            print("FAIL", f)
        return 1

    print("PASS numerics manifest includes classified income + grand total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
