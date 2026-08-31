from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from tax_agent.models import RiskLevel, TaxEvent


@dataclass
class RiskContext:
    resident_status: str
    data_quality: dict[str, Any]
    broker_template_id: str
    filing_scope: str
    events: list[TaxEvent]
    confidence_base: float
    declared_account_count: int | None = None
    parsed_account_count: int = 1
    rule_snapshot_status: str = "stable"
    has_stock_compensation: bool = False
    domestic_income_provided: bool = False


@dataclass
class RiskAssessment:
    level: RiskLevel
    confidence_score: float
    triggered_rules: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


def _load_risk_rules() -> list[dict[str, Any]]:
    path = Path(__file__).resolve().parent.parent / "rules" / "risk_rules_v1.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("rules") or []


def assess_risk(ctx: RiskContext) -> RiskAssessment:
    triggered: list[str] = []
    messages: list[str] = []
    level = RiskLevel.LOW

    def bump(new: RiskLevel, rule_id: str, msg: str = "") -> None:
        nonlocal level
        triggered.append(rule_id)
        if msg:
            messages.append(msg)
        order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
        if order[new] > order[level]:
            level = new

    if ctx.resident_status == "uncertain":
        bump(RiskLevel.HIGH, "R001", "税务居民身份未确认")
    if ctx.resident_status == "non_resident":
        bump(RiskLevel.HIGH, "R002", "非中国税务居民")

    amb_amount = Decimal("0")
    amb_count = 0
    for e in ctx.events:
        if e.classification_status == "ambiguous":
            amb_count += 1
            try:
                amb_amount += e.resolved_amount_cny()
            except ValueError:
                pass
    if amb_count > 0 and amb_amount > 1000:
        bump(
            RiskLevel.MEDIUM,
            "R003",
            f"存在 {amb_count} 笔成本基础不完整交易（约 {amb_amount.quantize(Decimal('0.01'))} 元），"
            "请上传买入年度税表后重算",
        )

    wh_cov = float((ctx.data_quality.get("coverage") or {}).get("withholding", 1.0))
    if wh_cov < 0.8:
        bump(RiskLevel.MEDIUM, "R004", "预扣税数据不完整")

    if ctx.broker_template_id == "template_unknown":
        bump(RiskLevel.MEDIUM, "R005", "未识别券商模板")
    elif ctx.broker_template_id == "broker_generic_mapped_v1":
        bump(RiskLevel.MEDIUM, "R005", "用户确认列映射，建议抽查原始对账单")

    confidence = ctx.confidence_base
    if confidence < 0.85:
        bump(RiskLevel.MEDIUM, "R006", "整体置信度偏低")

    if ctx.has_stock_compensation:
        bump(RiskLevel.HIGH, "R007", "股权激励需专家复核")

    if ctx.filing_scope == "includes_domestic" and not ctx.domestic_income_provided:
        bump(RiskLevel.MEDIUM, "R008", "已选含境内综合所得但未提供境内收入，结果仅含境外部分")

    if (
        ctx.declared_account_count is not None
        and ctx.declared_account_count != ctx.parsed_account_count
    ):
        bump(RiskLevel.HIGH, "R009", "CRS 账户数不一致")

    if ctx.rule_snapshot_status == "deprecated":
        bump(RiskLevel.MEDIUM, "R010", "规则快照已弃用")

    return RiskAssessment(level=level, confidence_score=confidence, triggered_rules=triggered, messages=messages)
