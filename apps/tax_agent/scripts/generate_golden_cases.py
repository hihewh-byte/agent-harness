#!/usr/bin/env python3
"""Generate golden fixture JSON files (43 cases) for tax_agent v1."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "golden"
FX = Decimal("7.10")


def _money(amount: str, currency: str = "USD") -> dict:
    return {"amount": amount, "currency": currency}


def _event(
    event_type: str,
    date: str,
    gross: str,
    wh: str | None = None,
    cny: str | None = None,
    status: str = "confirmed",
) -> dict:
    fx = FX
    gross_d = Decimal(gross)
    cny_val = cny or str((gross_d * fx).quantize(Decimal("0.01")))
    ev: dict = {
        "eventType": event_type,
        "tradeDate": date,
        "grossAmount": _money(gross),
        "amountCny": cny_val,
        "fxRateUsed": float(fx),
        "classificationStatus": status,
    }
    if wh:
        ev["withholdingTax"] = _money(wh)
    return ev


def _write(path: Path, case: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _base_params(**kw) -> dict:
    p = {
        "taxYear": 2024,
        "residentStatus": "cn_tax_resident",
        "fxPolicy": "safe_harbor_monthly",
        "ruleSnapshotId": "cn_resident_us_equity@2026.06.01",
    }
    p.update(kw)
    return p


def gen_deterministic() -> None:
    """20 deterministic cases — scaled dividends/gains."""
    for i in range(1, 21):
        div = 500 + i * 50
        gain = 200 + i * 25
        wh = int(div * Decimal("0.30"))
        div_cny = str((Decimal(div) * FX).quantize(Decimal("0.01")))
        gain_cny = str((Decimal(gain) * FX).quantize(Decimal("0.01")))
        tax_div = (Decimal(div_cny) * Decimal("0.20")).quantize(Decimal("0.01"))
        tax_gain = (Decimal(gain_cny) * Decimal("0.20")).quantize(Decimal("0.01"))
        wh_cny = (Decimal(wh) * FX).quantize(Decimal("0.01"))
        credit = min(wh_cny, tax_div)
        net = (tax_div + tax_gain - credit).quantize(Decimal("0.01"))
        case = {
            "caseId": f"det_{i:03d}",
            "description": f"generated deterministic #{i}",
            "input": {
                "events": [
                    _event("DIVIDEND", f"2024-03-{min(i, 28):02d}", str(div), str(wh)),
                    _event("CAPITAL_GAIN", f"2024-07-{min(i, 28):02d}", str(gain)),
                ]
            },
            "parameters": _base_params(),
            "expected": {
                "summary": {
                    "taxDueCny": str((tax_div + tax_gain).quantize(Decimal("0.01"))),
                    "creditAllowedCny": str(credit),
                    "netTaxDueCny": str(net),
                },
                "riskLevel": "low",
                "confidenceScoreMin": 0.85,
            },
        }
        _write(ROOT / "deterministic" / f"case_{case['caseId']}.json", case)


def gen_missing_data() -> None:
    for i in range(1, 11):
        case = {
            "caseId": f"missing_{i:03d}",
            "description": f"low withholding coverage case #{i}",
            "input": {
                "events": [
                    _event("DIVIDEND", f"2024-04-{i:02d}", "800"),
                    _event("CAPITAL_GAIN", f"2024-09-{i:02d}", "400"),
                ]
            },
            "parameters": _base_params(),
            "dataQuality": {"coverage": {"withholding": 0.5 + i * 0.03}},
            "expected": {
                "riskLevel": "medium",
                "allowPartial": True,
            },
        }
        _write(ROOT / "missing_data" / f"case_{case['caseId']}.json", case)


def gen_ambiguous() -> None:
    for i in range(1, 6):
        case = {
            "caseId": f"amb_{i:03d}",
            "description": f"ambiguous classification #{i}",
            "input": {
                "events": [
                    _event(
                        "CAPITAL_GAIN",
                        f"2024-05-{i:02d}",
                        str(2000 + i * 500),
                        status="ambiguous",
                    ),
                ]
            },
            "parameters": _base_params(),
            "expected": {"riskLevel": "high"},
        }
        _write(ROOT / "ambiguous" / f"case_{case['caseId']}.json", case)


def gen_credit_edge() -> None:
    specs: list[tuple[str, str, list]] = [
        (
            "credit_001",
            "预扣超过应纳税",
            [_event("DIVIDEND", "2024-06-01", "1000", "500")],
        ),
        (
            "credit_002",
            "无预扣",
            [_event("DIVIDEND", "2024-06-01", "500")],
        ),
        (
            "credit_003",
            "标准30%预扣",
            [_event("DIVIDEND", "2024-06-01", "2000", "600")],
        ),
        (
            "credit_004",
            "小额全抵免",
            [_event("DIVIDEND", "2024-06-01", "100", "100")],
        ),
        (
            "credit_005",
            "大额分红",
            [_event("DIVIDEND", "2024-06-01", "5000", "2000")],
        ),
        (
            "credit_006",
            "仅资本利得",
            [_event("CAPITAL_GAIN", "2024-08-01", "500")],
        ),
        (
            "credit_007",
            "利息+分红",
            [
                _event("INTEREST", "2024-01-15", "300"),
                _event("DIVIDEND", "2024-06-01", "300", "90"),
            ],
        ),
        (
            "credit_008",
            "standalone WH event",
            [
                _event("DIVIDEND", "2024-06-01", "1500"),
                {
                    "eventType": "WITHHOLDING_TAX",
                    "tradeDate": "2024-06-02",
                    "grossAmount": _money("450"),
                    "amountCny": str((Decimal("450") * FX).quantize(Decimal("0.01"))),
                    "fxRateUsed": float(FX),
                    "classificationStatus": "confirmed",
                },
            ],
        ),
    ]
    for cid, desc, events in specs:
        case = {
            "caseId": cid,
            "description": desc,
            "input": {"events": events},
            "parameters": _base_params(),
            "expected": {"riskLevel": "low", "computeOk": True},
        }
        _write(ROOT / "credit_edge" / f"case_{cid}.json", case)


def main() -> None:
    gen_deterministic()
    gen_missing_data()
    gen_ambiguous()
    gen_credit_edge()
    print("Generated golden cases under", ROOT)


if __name__ == "__main__":
    main()
