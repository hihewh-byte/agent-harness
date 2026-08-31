"""Date-aware FX rate provider.

汇率数据通过规则快照/Feed 机制下发（`fx_rates.yaml` 与 `rules.yaml` 同目录），
因此与税率规则共享同一套版本化、可审计、可回退的发布流水线。

provider 按交易发生日解析当月（safe_harbor_monthly）或年度平均
（safe_harbor_yearly）中间价，并在结果中携带数据来源标识，便于审计区分
正式 PBOC 数据与占位样例数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

DEFAULT_FX = Decimal("7.10")


@dataclass
class FxResolution:
    rate: Decimal
    source: str
    note: str


def _month_key(trade_date: str) -> str | None:
    # ISO date YYYY-MM-DD -> YYYY-MM
    parts = trade_date.split("-")
    if len(parts) >= 2 and len(parts[0]) == 4:
        return f"{parts[0]}-{parts[1]}"
    return None


class FxRateProvider:
    def __init__(
        self,
        monthly: dict[str, Decimal] | None = None,
        yearly_average: dict[str, Decimal] | None = None,
        *,
        source: str = "unknown",
        source_label: str = "",
    ) -> None:
        self.monthly = monthly or {}
        self.yearly_average = yearly_average or {}
        self.source = source
        self.source_label = source_label

    @property
    def available(self) -> bool:
        return bool(self.monthly or self.yearly_average)

    def list_supplemental_tax_years(self) -> list[int]:
        """所得年度 Y 的补缴汇率锚定 (Y-1)-12 → 由 -12 月键反推 Y。"""
        out: set[int] = set()
        for mk in self.monthly:
            parts = str(mk).split("-")
            if len(parts) == 2 and parts[1] == "12" and parts[0].isdigit():
                out.add(int(parts[0]) + 1)
        return sorted(out)

    @classmethod
    def from_yaml(cls, path: Path) -> FxRateProvider:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        monthly = {k: Decimal(str(v)) for k, v in (data.get("monthly") or {}).items()}
        yearly = {k: Decimal(str(v)) for k, v in (data.get("yearlyAverage") or {}).items()}
        return cls(
            monthly,
            yearly,
            source=str(data.get("source") or "unknown"),
            source_label=str(data.get("sourceLabelZh") or ""),
        )

    @classmethod
    def from_snapshot_dir(cls, snapshot_dir: Path) -> FxRateProvider | None:
        path = snapshot_dir / "fx_rates.yaml"
        if not path.is_file():
            return None
        return cls.from_yaml(path)

    def _monthly_with_fallback(self, month_key: str) -> tuple[Decimal | None, str]:
        if month_key in self.monthly:
            return self.monthly[month_key], "exact"
        # nearest prior month within the same/earlier period
        candidates = sorted(k for k in self.monthly if k < month_key)
        if candidates:
            return self.monthly[candidates[-1]], f"fallback_prior:{candidates[-1]}"
        return None, "missing"

    def resolve_month(self, month_key: str) -> FxResolution:
        label = self.source_label or self.source
        rate, mode = self._monthly_with_fallback(month_key)
        if rate is not None:
            note = f"{label}·{month_key}"
            if mode != "exact":
                note += f"（{mode}）"
            return FxResolution(rate, self.source, note)
        return FxResolution(DEFAULT_FX, "default_fallback", f"默认汇率 {DEFAULT_FX}（无匹配月度数据）")

    def resolve_filing(
        self,
        policy: str,
        filing_date: str,
        *,
        tax_year: int | None = None,
    ) -> FxResolution:
        from tax_agent.fx_filing_rules import resolve_filing_month_key

        month_key, rule_label = resolve_filing_month_key(
            policy, filing_date, tax_year=tax_year
        )
        res = self.resolve_month(month_key)
        return FxResolution(res.rate, res.source, f"{rule_label}；{res.note}")

    def resolve(
        self,
        trade_date: str,
        policy: str,
        *,
        filing_date: str | None = None,
        tax_year: int | None = None,
    ) -> FxResolution:
        label = self.source_label or self.source
        if policy in ("cn_annual_filing", "cn_supplemental"):
            if not filing_date:
                return FxResolution(
                    DEFAULT_FX,
                    "default_fallback",
                    f"{policy} 需要 filingDate",
                )
            return self.resolve_filing(policy, filing_date, tax_year=tax_year)
        if policy == "safe_harbor_yearly":
            year = trade_date.split("-")[0] if trade_date else ""
            rate = self.yearly_average.get(year)
            if rate is not None:
                return FxResolution(rate, self.source, f"{label}·{year}年平均")
        # default: monthly by trade date
        month_key = _month_key(trade_date)
        if month_key:
            return self.resolve_month(month_key)
        return FxResolution(DEFAULT_FX, "default_fallback", f"默认汇率 {DEFAULT_FX}（无匹配月度数据）")
