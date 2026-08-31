from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from tax_agent.fx_rates import DEFAULT_FX, FxRateProvider, FxResolution
from tax_agent.models import TaxEvent

Q = Decimal("0.01")


def apply_fx_to_events(
    events: Iterable[TaxEvent],
    fx_rate: Decimal | None = None,
    *,
    provider: FxRateProvider | None = None,
    policy: str = "safe_harbor_monthly",
    override_rate: Decimal | None = None,
    fallback_rate: Decimal | None = None,
    filing_date: str | None = None,
    tax_year: int | None = None,
) -> list[TaxEvent]:
    """Resolve CNY amounts for events.

    优先级：
    1. 事件已带 amountCny+fxRateUsed（解析阶段已折算）→ 保持不变（幂等）。
    2. override_rate（用户上传/显式指定汇率）→ 全量套用。
    3. cn_annual_filing / cn_supplemental → 全事件统一合规申报汇率（见 fx_filing_rules）。
    4. provider（按交易日解析月度/年度中间价，Feed 下发）。
    5. fallback_rate / fx_rate / DEFAULT_FX 兜底。
    """
    from tax_agent.fx_filing_rules import COMPLIANCE_FX_POLICIES

    fixed_rate = override_rate or fx_rate
    fb = fallback_rate if fallback_rate is not None else (fx_rate or DEFAULT_FX)

    unified: FxResolution | None = None
    if (
        policy in COMPLIANCE_FX_POLICIES
        and provider is not None
        and provider.available
        and filing_date
    ):
        unified = provider.resolve_filing(policy, filing_date, tax_year=tax_year)

    out: list[TaxEvent] = []
    for ev in events:
        if ev.amount_cny is not None and ev.fx_rate_used is not None:
            out.append(ev)
            continue
        if not ev.gross_amount:
            out.append(ev)
            continue

        if fixed_rate is not None and override_rate is not None:
            rate = override_rate
            source = "user_override"
        elif unified is not None:
            rate = unified.rate
            source = unified.note
        elif provider is not None and provider.available:
            res = provider.resolve(ev.trade_date, policy, filing_date=filing_date)
            rate = res.rate
            source = res.note
        elif fixed_rate is not None:
            rate = fixed_rate
            source = "explicit_rate"
        else:
            rate = fb
            source = "default_fallback"

        ev.amount_cny = (ev.gross_amount.amount * rate).quantize(Q)
        ev.fx_rate_used = rate
        ev.fx_rate_source = source
        out.append(ev)
    return out
