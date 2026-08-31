from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from tax_agent.domestic_income import (
    DomesticIncomeInput,
    build_domestic_line_item,
    merge_foreign_domestic_summaries,
)
from tax_agent.models import (
    EventType,
    FormulaStep,
    ResidentStatus,
    RiskLevel,
    TaxEvent,
    TaxLineItem,
)
from tax_agent.cost_basis import per_disposal_positive_gain_cny, sum_realized_gain_cny, taxable_gain_cny
from tax_agent.risk_engine import RiskAssessment, RiskContext, assess_risk
from tax_agent.rules_loader import RuleRepository, RuleSnapshot
from tax_agent.stock_compensation import (
    build_stock_compensation_line,
    is_stock_compensation_event,
    partition_events,
)


Q = Decimal("0.01")
RULE_PACK_DEFAULT = "cn_resident_us_equity"
_BLOCKING_HIGH_RULES = frozenset({"R001", "R002", "R009"})


@dataclass
class ComputeRequest:
    events: list[TaxEvent]
    tax_year: int
    resident_status: ResidentStatus
    rule_snapshot_id: str = "latest_stable"
    fx_policy: str = "cn_annual_filing"
    filing_date: str | None = None
    filing_scope: str = "foreign_only"
    domestic_income: DomesticIncomeInput | None = None
    data_quality: dict[str, Any] = field(default_factory=dict)
    broker_template_id: str = "broker_ibkr_v1"
    declared_account_count: int | None = None
    parsed_account_count: int = 1
    input_file_hashes: list[str] = field(default_factory=list)


@dataclass
class ComputeResult:
    run_id: str
    rule_snapshot_id: str
    status: str
    risk_level: RiskLevel
    confidence_score: float
    summary: dict[str, str]
    line_items: list[TaxLineItem]
    audit_bundle: dict[str, Any]
    disclaimers: list[dict[str, str]]
    triggered_risk_rules: list[str]
    net_tax_due_range_cny: dict[str, str] | None = None
    notes: list[str] = field(default_factory=list)
    fx_comparison: dict[str, Any] | None = None
    late_fee: dict[str, Any] | None = None
    filing_recommendation: dict[str, Any] | None = None


class ComputeEngine:
    def __init__(self, repo: RuleRepository | None = None) -> None:
        self.repo = repo or RuleRepository()

    def compute(self, req: ComputeRequest) -> ComputeResult:
        snapshot_id = self.repo.resolve_snapshot_id(RULE_PACK_DEFAULT, req.rule_snapshot_id)
        snapshot = self.repo.load_snapshot(snapshot_id)

        gate = snapshot.resident_gate
        if req.resident_status == ResidentStatus.UNCERTAIN:
            return self._blocked_result(req, snapshot, "resident_uncertain")

        if gate.get("requiredStatus") == "cn_tax_resident" and req.resident_status != ResidentStatus.CN_TAX_RESIDENT:
            return self._blocked_result(req, snapshot, "non_resident")

        year_events = [e for e in req.events if e.trade_date.startswith(str(req.tax_year))]
        risk_ctx = RiskContext(
            resident_status=req.resident_status.value,
            data_quality=req.data_quality,
            broker_template_id=req.broker_template_id,
            filing_scope=req.filing_scope,
            events=year_events,
            confidence_base=self._confidence_base(year_events, req.data_quality),
            declared_account_count=req.declared_account_count,
            parsed_account_count=req.parsed_account_count,
            rule_snapshot_status=snapshot.status,
            has_stock_compensation=any(is_stock_compensation_event(e) for e in year_events),
            domestic_income_provided=bool(
                req.domestic_income and not req.domestic_income.is_empty()
            ),
        )
        risk = assess_risk(risk_ctx)

        if self._is_blocking_high(risk):
            return self._high_risk_shell(req, snapshot, risk)

        lines, notes = self._build_line_items(year_events, snapshot)
        amb_n = sum(1 for e in year_events if e.classification_status == "ambiguous")
        if amb_n:
            notes.insert(
                0,
                f"警告：{amb_n} 笔卖出缺少买入成本（多为未上传更早年度税表）；"
                "以下为按已有流水计算的参考税额，申报前请补全各年 Annual_Statement。",
            )
        rematch_warn = (req.data_quality or {}).get("_futuRematchWarnings") or []
        for w in rematch_warn:
            if "期初持仓" in w or "跨年度" in w:
                notes.append(w)
        if risk.level == RiskLevel.HIGH and "R007" in risk.triggered_rules:
            notes.insert(
                0,
                "股权激励（R007）草稿税额如下，须税务专家复核后方可作为申报依据。",
            )
        fx_sources = {e.fx_rate_source for e in year_events if e.fx_rate_source}
        if any(("样例" in s) or s.startswith("default_fallback") or ("默认汇率" in s) for s in fx_sources):
            notes.append(
                "部分交易使用了样例或兜底汇率，正式申报前请通过 PBOC 中间价 Feed 更新汇率数据后重算。"
            )
        if req.fx_policy == "cn_supplemental":
            notes.append(
                "以前年度补缴：境外所得按所得所属纳税年度的上一纳税年度末日汇率统一折算（实施条例第32条）；"
                "详见报告「多口径对照」与「滞纳金估算」。"
            )
        elif req.fx_policy == "cn_annual_filing":
            notes.append(
                "正常年度汇算：境外所得按办理申报当月上一月末中间价统一折算。"
            )
        summary = self._summarize(lines)
        domestic_detail: dict[str, str] | None = None
        if req.filing_scope == "includes_domestic" and req.domestic_income:
            if not req.domestic_income.is_empty():
                dom_line, dom_notes, domestic_detail = build_domestic_line_item(req.domestic_income)
                lines.append(dom_line)
                notes.extend(dom_notes)
                summary = merge_foreign_domestic_summaries(summary, domestic_detail)
            else:
                notes.append("已选择含境内综合所得，但未填写境内收入数据，仅计算境外部分。")

        if risk.level == RiskLevel.MEDIUM:
            net = Decimal(summary["netTaxDueCny"])
            summary["netTaxDueRangeCny"] = {
                "low": str((net * Decimal("0.95")).quantize(Q)),
                "high": str((net * Decimal("1.10")).quantize(Q)),
            }

        audit = self._audit_bundle(req, snapshot_id, summary, lines, domestic_detail)
        return ComputeResult(
            run_id=str(uuid4()),
            rule_snapshot_id=snapshot_id,
            status="success" if risk.level == RiskLevel.LOW else "partial",
            risk_level=risk.level,
            confidence_score=risk.confidence_score,
            summary={k: v for k, v in summary.items() if k != "netTaxDueRangeCny"},
            line_items=lines,
            audit_bundle=audit,
            disclaimers=snapshot.disclaimers,
            triggered_risk_rules=risk.triggered_rules,
            net_tax_due_range_cny=summary.get("netTaxDueRangeCny"),
            notes=notes,
        )

    @staticmethod
    def _is_blocking_high(risk: RiskAssessment) -> bool:
        return risk.level == RiskLevel.HIGH and bool(
            _BLOCKING_HIGH_RULES & set(risk.triggered_rules)
        )

    def _build_line_items(
        self, events: list[TaxEvent], snapshot: RuleSnapshot
    ) -> tuple[list[TaxLineItem], list[str]]:
        stock_events, regular_events = partition_events(events)
        by_category: dict[str, list[TaxEvent]] = {}
        foreign_by_category: dict[str, Decimal] = {}

        for ev in regular_events:
            if ev.event_type == EventType.WITHHOLDING_TAX:
                continue
            if ev.event_type == EventType.FEE:
                continue
            mapped = snapshot.rate_for_event_type(ev.event_type.value)
            if not mapped:
                continue
            cat_id, rate = mapped
            by_category.setdefault(cat_id, []).append(ev)
            if ev.withholding_tax:
                fx = ev.fx_rate_used or Decimal("1")
                foreign_by_category[cat_id] = foreign_by_category.get(cat_id, Decimal("0")) + (
                    ev.withholding_tax.amount * fx
                ).quantize(Q)

        standalone_wh = sum(
            (
                e.resolved_amount_cny()
                for e in regular_events
                if e.event_type == EventType.WITHHOLDING_TAX
            ),
            Decimal("0"),
        )

        lines: list[TaxLineItem] = []
        notes: list[str] = []
        if stock_events:
            mapped = snapshot.rate_for_event_type(EventType.STOCK_COMPENSATION.value)
            if mapped:
                cat_id, rate = mapped
                sc_line, sc_notes = build_stock_compensation_line(
                    stock_events, tax_rate=rate, category_id=cat_id
                )
                if sc_line:
                    lines.append(sc_line)
                notes.extend(sc_notes)
            else:
                notes.append("规则快照未配置股权激励税目，已跳过 STOCK_COMPENSATION 计税。")
        for cat_id, cat_events in by_category.items():
            rate = Decimal(str(snapshot.categories[cat_id]["rate"]))
            cat_formula = str(snapshot.categories[cat_id].get("incomeFormula") or "")
            if cat_id == "cn_property_transfer" or cat_formula == "sum_realized_gain_cny":
                raw_income = sum_realized_gain_cny(cat_events)
                taxable = taxable_gain_cny(cat_events)
                alt_positive = per_disposal_positive_gain_cny(cat_events)
                if alt_positive > taxable:
                    notes.append(
                        f"{cat_id}: 同年度盈亏相抵后应纳税所得额 {taxable} 元；"
                        f"若按次不抵减则为 {alt_positive} 元（辅助对照，非默认申报口径）。"
                    )
                if raw_income < 0 and taxable == 0:
                    notes.append(
                        f"{cat_id}: 本年度转让净亏损 {abs(raw_income)} 元，"
                        f"同年度盈亏相抵后应纳税所得额按 0 计（亏损不得跨年结转）。"
                    )
            else:
                raw_income = sum((e.resolved_amount_cny() for e in cat_events), Decimal("0")).quantize(Q)
                taxable = raw_income if raw_income > 0 else Decimal("0")
                if raw_income < 0:
                    notes.append(
                        f"{cat_id}: 本年净亏损 {abs(raw_income)} 元，按中国个税不可跨类抵减，"
                        f"该类应纳税所得额按 0 计。"
                    )
            tax_due = (taxable * rate).quantize(Q)
            foreign = foreign_by_category.get(cat_id, Decimal("0"))
            credit = min(foreign, tax_due)
            net = (tax_due - credit).quantize(Q)
            income_expr = (
                "max(0, sum(realizedGainCny))"
                if cat_id == "cn_property_transfer" or cat_formula == "sum_realized_gain_cny"
                else "max(0, sum(amountCny))"
            )
            steps = [
                FormulaStep(1, "aggregate_gross_cny", income_expr, taxable, {"count": len(cat_events), "rawIncomeCny": str(raw_income)}),
                FormulaStep(2, "apply_tax_rate", "taxable * rate", tax_due, {"rate": float(rate)}),
                FormulaStep(3, "compute_tax_due", "taxable * rate", tax_due),
                FormulaStep(
                    4,
                    "allocate_foreign_tax",
                    "sum(withholding)",
                    foreign,
                ),
                FormulaStep(5, "apply_credit_limit", "min(foreign, tax_due)", credit),
                FormulaStep(6, "net_tax_due", "tax_due - credit", net),
            ]
            lines.append(
                TaxLineItem(
                    tax_category=cat_id,
                    taxable_income_cny=taxable,
                    tax_rate=rate,
                    tax_due_cny=tax_due,
                    foreign_tax_paid_cny=foreign,
                    credit_allowed_cny=credit,
                    net_tax_due_cny=net,
                    source_event_ids=[e.event_id for e in cat_events],
                    formula_steps=steps,
                )
            )

        if standalone_wh > 0 and lines:
            total_due = sum((ln.tax_due_cny for ln in lines), Decimal("0"))
            if total_due > 0:
                allocated = Decimal("0")
                for ln in lines:
                    share = (ln.tax_due_cny / total_due).quantize(Decimal("0.0001"))
                    add = min((standalone_wh * share).quantize(Q), ln.tax_due_cny - ln.foreign_tax_paid_cny)
                    if add > 0:
                        ln.foreign_tax_paid_cny += add
                        ln.credit_allowed_cny = min(ln.foreign_tax_paid_cny, ln.tax_due_cny)
                        ln.net_tax_due_cny = (ln.tax_due_cny - ln.credit_allowed_cny).quantize(Q)
                        allocated += add
                unused = (standalone_wh - allocated).quantize(Q)
                if unused > 0:
                    notes.append(
                        f"境外预扣税有 {unused} 元因超过当期抵免限额而本年无法抵免"
                        f"（可按规定在以后年度结转）。"
                    )

        return lines, notes

    def _summarize(self, lines: list[TaxLineItem]) -> dict[str, str]:
        tax_due = sum((ln.tax_due_cny for ln in lines), Decimal("0")).quantize(Q)
        credit = sum((ln.credit_allowed_cny for ln in lines), Decimal("0")).quantize(Q)
        net = sum((ln.net_tax_due_cny for ln in lines), Decimal("0")).quantize(Q)
        foreign = sum((ln.foreign_tax_paid_cny for ln in lines), Decimal("0")).quantize(Q)
        return {
            "taxableIncomeCny": str(sum((ln.taxable_income_cny for ln in lines), Decimal("0")).quantize(Q)),
            "taxDueCny": str(tax_due),
            "foreignTaxPaidCny": str(foreign),
            "creditAllowedCny": str(credit),
            "netTaxDueCny": str(net),
        }

    def _confidence_base(self, events: list[TaxEvent], dq: dict[str, Any]) -> float:
        if not events:
            return 0.5
        amb = sum(1 for e in events if e.classification_status == "ambiguous")
        cov = (dq.get("coverage") or {}).get("withholding", 1.0)
        return max(0.0, min(1.0, 1.0 - 0.1 * amb) * float(cov))

    def _audit_bundle(
        self,
        req: ComputeRequest,
        snapshot_id: str,
        summary: dict[str, str],
        lines: list[TaxLineItem],
        domestic_detail: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "taxYear": req.tax_year,
            "residentStatus": req.resident_status.value,
            "fxPolicy": req.fx_policy,
            "filingDate": req.filing_date,
            "filingScope": req.filing_scope,
            "summary": summary,
        }
        if domestic_detail:
            payload["domesticIncome"] = domestic_detail
        result_hash = hashlib.sha256(
            json.dumps([ln.to_dict() for ln in lines], sort_keys=True).encode()
        ).hexdigest()
        fx_sources = sorted({e.fx_rate_source for e in req.events if e.fx_rate_source})
        return {
            "auditId": str(uuid4()),
            "inputFileHashes": req.input_file_hashes,
            "ruleSnapshotId": snapshot_id,
            "parameterSnapshot": payload,
            "fxRateSources": fx_sources,
            "resultHash": result_hash,
            "disclaimerVersion": "disclaimer_v1.0",
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }

    def _blocked_result(self, req: ComputeRequest, snapshot: RuleSnapshot, reason: str) -> ComputeResult:
        risk = assess_risk(
            RiskContext(
                resident_status=req.resident_status.value,
                data_quality=req.data_quality,
                broker_template_id=req.broker_template_id,
                filing_scope=req.filing_scope,
                events=req.events,
                confidence_base=0.0,
                domestic_income_provided=bool(
                    req.domestic_income and not req.domestic_income.is_empty()
                ),
            )
        )
        return ComputeResult(
            run_id=str(uuid4()),
            rule_snapshot_id=snapshot.rule_snapshot_id,
            status="failed",
            risk_level=RiskLevel.HIGH,
            confidence_score=0.0,
            summary={"blockedReason": reason},
            line_items=[],
            audit_bundle=self._audit_bundle(req, snapshot.rule_snapshot_id, {"blockedReason": reason}, []),
            disclaimers=snapshot.disclaimers,
            triggered_risk_rules=risk.triggered_rules,
        )

    def _high_risk_shell(self, req: ComputeRequest, snapshot: RuleSnapshot, risk) -> ComputeResult:
        return ComputeResult(
            run_id=str(uuid4()),
            rule_snapshot_id=snapshot.rule_snapshot_id,
            status="partial",
            risk_level=RiskLevel.HIGH,
            confidence_score=risk.confidence_score,
            summary={"message": "需人工复核，未输出最终税额"},
            line_items=[],
            audit_bundle=self._audit_bundle(req, snapshot.rule_snapshot_id, {"highRisk": True}, []),
            disclaimers=snapshot.disclaimers,
            triggered_risk_rules=risk.triggered_rules,
        )
