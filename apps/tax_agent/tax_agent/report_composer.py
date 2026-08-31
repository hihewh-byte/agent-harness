from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from tax_agent.compute_engine import ComputeResult


def _template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "advisory_report_v1.yaml"


def load_report_template() -> dict[str, Any]:
    return yaml.safe_load(_template_path().read_text(encoding="utf-8"))


def compose_markdown_report(result: ComputeResult, template: dict[str, Any] | None = None) -> str:
    tpl = template or load_report_template()
    sections = tpl.get("sections") or []
    lines: list[str] = [f"# {tpl.get('title', '报税测算报告')}", ""]

    if result.risk_level.value == "high" and not result.line_items:
        lines.append("## 结论摘要")
        lines.append("> **需人工税务专家复核**：系统未输出最终应补税额。")
        for msg in result.triggered_risk_rules:
            lines.append(f"- 触发规则：`{msg}`")
        lines.append("")
        lines.append("## 免责声明")
        for block in result.disclaimers:
            lines.append(block.get("text", "").strip())
        return "\n".join(lines)

    if result.risk_level.value == "high" and result.line_items:
        lines.append("## 结论摘要")
        lines.append("> **股权激励草稿（R007）**：以下为系统估算，须专家复核后方可申报。")
        for msg in result.triggered_risk_rules:
            lines.append(f"- 触发规则：`{msg}`")
        lines.append("")

    summary = result.summary
    lines.append("## 结论摘要")
    lines.append(f"- 应纳税所得额（人民币）：**{summary.get('taxableIncomeCny', '—')}** 元")
    lines.append(f"- 应纳税额：**{summary.get('taxDueCny', '—')}** 元")
    lines.append(f"- 境外已纳税额（折算）：**{summary.get('foreignTaxPaidCny', '—')}** 元")
    lines.append(f"- 可抵免税额：**{summary.get('creditAllowedCny', '—')}** 元")
    lines.append(f"- 预计应补税额：**{summary.get('netTaxDueCny', '—')}** 元")
    if summary.get("foreignNetTaxDueCny"):
        lines.append(f"- 其中境外应补：**{summary.get('foreignNetTaxDueCny')}** 元")
    if summary.get("domesticNetTaxDueCny"):
        lines.append(
            f"- 其中境内综合所得应补：**{summary.get('domesticNetTaxDueCny')}** 元"
            f"（应纳税所得 {summary.get('domesticTaxableIncomeCny', '—')} 元）"
        )
    if result.net_tax_due_range_cny:
        lines.append(
            f"- 预计区间：{result.net_tax_due_range_cny.get('low')} ~ "
            f"{result.net_tax_due_range_cny.get('high')} 元（风险等级：中）"
        )
    lines.append(f"- 规则快照：`{result.rule_snapshot_id}`")
    lines.append(f"- 风险等级：`{result.risk_level.value}`")
    lines.append("")

    if "detail_table" in sections and result.line_items:
        lines.append("## 分项明细")
        lines.append("| 税目 | 应税收入 | 税率 | 应纳税 | 可抵免 | 应补 |")
        lines.append("|------|----------|------|--------|--------|------|")
        for ln in result.line_items:
            d = ln.to_dict()
            lines.append(
                f"| {d['taxCategory']} | {d['taxableIncomeCny']} | {d['taxRate']:.0%} | "
                f"{d['taxDueCny']} | {d['creditAllowedCny']} | {d['netTaxDueCny']} |"
            )
        lines.append("")

    if "filing_checklist" in sections:
        lines.append("## 申报材料清单")
        for item in tpl.get("filing_checklist") or []:
            lines.append(f"- {item}")
        lines.append("")

    if result.filing_recommendation and result.filing_recommendation.get("recommended"):
        rec = result.filing_recommendation
        r = rec["recommended"]
        lines.append("## 最优申报日推荐（税 + 滞纳金）")
        lines.append(f"> {rec.get('rationale', '')}")
        if rec.get("status") == "ok":
            lines.append(f"- **推荐办理日**：`{r.get('filingDate')}`（`{r.get('fxPolicy')}`）")
            lines.append(
                f"- 应补 **{r.get('netTaxDueCny')}** 元 + 滞纳金 **{r.get('lateFeeCny')}** 元 "
                f"= 合计 **{r.get('totalCashCny')}** 元"
            )
            if Decimal(str(r.get("savingsVsPrimaryCny", "0"))) > 0:
                lines.append(f"- 较当前方案少支出：**{r.get('savingsVsPrimaryCny')}** 元")
        elif rec.get("status") == "already_optimal":
            lines.append(f"- 当前申报日 `{rec.get('primaryFilingDate')}` 已为最优（合计 {rec.get('primaryTotalCashCny')} 元）")
        if rec.get("note"):
            lines.append(f"- {rec['note']}")
        top = rec.get("topCandidates") or []
        if len(top) > 1:
            lines.append("")
            lines.append("| 排名 | 申报日 | 应补 | 滞纳金 | 合计 |")
            lines.append("|------|--------|------|--------|------|")
            for i, row in enumerate(top[:5], 1):
                lines.append(
                    f"| {i} | {row.get('filingDate')} | {row.get('netTaxDueCny')} | "
                    f"{row.get('lateFeeCny')} | {row.get('totalCashCny')} |"
                )
        lines.append("")

    if result.late_fee:
        lf = result.late_fee
        lines.append("## 滞纳金估算")
        lines.append(f"- 法定申报截止：**{lf.get('statutoryDeadline', '—')}**")
        lines.append(f"- 办理申报日：**{lf.get('filingDate', '—')}**")
        if lf.get("applicable"):
            lines.append(f"- 逾期天数：**{lf.get('overdueDays', 0)}** 天（自 {lf.get('penaltyStartDate')} 起）")
            lines.append(f"- 应纳税额：**{lf.get('taxDueCny')}** 元")
            lines.append(f"- 滞纳金（0.05%/日）：**{lf.get('lateFeeCny')}** 元")
            lines.append(f"- **合计应缴（税+滞纳金）：{lf.get('totalPayableCny')}** 元")
        else:
            lines.append(f"- {lf.get('note', '未产生滞纳金')}")
        lines.append("")

    if result.fx_comparison and result.fx_comparison.get("scenarios"):
        cmp_ = result.fx_comparison
        lines.append("## 多口径汇率对照")
        lines.append("| 口径 | 应补税额 | 含滞纳金合计 | 较主场景 | 说明 |")
        lines.append("|------|----------|--------------|----------|------|")
        for sc in cmp_["scenarios"]:
            delta = sc.get("deltaVsPrimaryCny")
            delta_s = f"{delta}" if delta is not None else "—"
            mark = " ★" if sc.get("isLowestNetTax") else ""
            tier = sc.get("tier", "")
            tier_tag = {"primary": "主", "compliant_alternative": "合规备选", "auxiliary": "辅助"}.get(tier, tier)
            total = sc.get("totalPayableCny") or sc.get("netTaxDueCny")
            lines.append(
                f"| [{tier_tag}] {sc.get('label', '')}{mark} | {sc.get('netTaxDueCny')} | {total} | "
                f"{delta_s} | {sc.get('fxNote', '')[:36]} |"
            )
        lines.append("")
        monthly = cmp_.get("monthlyBreakdown") or []
        if monthly:
            lines.append("### 分月折算明细（辅助核对）")
            lines.append("| 月份 | 笔数 | 原币 (USD) | 折算 (CNY) | 当月中间价 |")
            lines.append("|------|------|------------|------------|------------|")
            for row in monthly:
                lines.append(
                    f"| {row.get('month')} | {row.get('eventCount')} | {row.get('grossUsd')} | "
                    f"{row.get('grossCny')} | {row.get('fxRate') or '—'} |"
                )
            ms = cmp_.get("monthlyPolicySummary") or {}
            if ms.get("netTaxDueCny"):
                lines.append(f"\n分月口径合计应补：**{ms.get('netTaxDueCny')}** 元（仅辅助，非默认申报口径）")
            lines.append("")
        for tip in cmp_.get("optimizationTips") or []:
            lines.append(f"> {tip}")
        lines.append("")

    if result.notes:
        lines.append("## 计算说明")
        for note in result.notes:
            lines.append(f"- {note}")
        lines.append("")

    if result.triggered_risk_rules:
        lines.append("## 风险与不确定性")
        for rid in result.triggered_risk_rules:
            lines.append(f"- 已触发规则 `{rid}`，请核对原始对账单。")
        lines.append("")

    lines.append("## 下一步行动")
    for step in tpl.get("next_steps") or []:
        lines.append(f"- {step}")
    lines.append("")
    lines.append("## 免责声明")
    for block in result.disclaimers:
        lines.append(block.get("text", "").strip())
        lines.append("")

    return "\n".join(lines)
