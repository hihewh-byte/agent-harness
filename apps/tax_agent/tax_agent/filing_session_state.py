"""FilingSessionState — 报税会话结构化状态（PHA patient_state 报税版）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from tax_agent.harness_plan import FilingTurnPlan, JourneyPhase, TAX_HARNESS_TIER0_MAX_CHARS
from tax_agent.session_context import SessionContext


@dataclass
class FilingSessionState:
    """跨轮持久化的报税旅程状态（可由 SessionContext 投影）。"""

    dataset_id: str | None = None
    last_run_id: str | None = None
    focus_tax_year: int = 2024
    journey_phase: JourneyPhase = "onboarding"
    uploaded_years: list[int] = field(default_factory=list)
    broker_template_id: str | None = None
    filing_scope: str = "foreign_only"
    resident_status: str = "cn_tax_resident"
    has_compute: bool = False
    last_filing_snapshot: dict[str, Any] | None = None
    last_provenance: dict[str, Any] | None = None
    last_insight: dict[str, Any] | None = None
    last_policy_kb: list[dict[str, Any]] | None = None
    risk_flags: list[str] = field(default_factory=list)
    short_symbols: list[str] = field(default_factory=list)
    turn_focus_year: int | None = None
    turn_focus_ttl: int = 0
    guided_step: str | None = None
    guided_wizard_active: bool = False
    session_id: str | None = None
    user_key: str | None = None
    data_quality: dict[str, Any] | None = None
    fx_provider: Any = None
    chat_history: list[dict[str, str]] | None = None
    events: list[Any] | None = None

    @classmethod
    def from_session_context(cls, ctx: SessionContext) -> FilingSessionState:
        from tax_agent.coverage_check import uploaded_tax_years

        dq = ctx.data_quality or {}
        uploaded = uploaded_tax_years(dq)
        risk: list[str] = []
        if ctx.risk_level:
            risk.append(f"risk_level={ctx.risk_level}")
        for note in (dq.get("warnings") or dq.get("notes") or [])[:12]:
            risk.append(str(note))

        snapshot = None
        if ctx.last_summary:
            snapshot = {"summary": ctx.last_summary}
        ft = dq.get("filingTable") or dq.get("lastFilingTable")
        if isinstance(ft, dict):
            snapshot = ft if snapshot is None else {**snapshot, **ft}

        phase: JourneyPhase = "onboarding"
        if ctx.dataset_id:
            phase = "computed" if ctx.last_run_id or ctx.last_summary else "ready"
        if not uploaded and ctx.dataset_id:
            phase = "collecting"

        from tax_agent.session_turn_focus import get_tax_session_focus

        db_focus = get_tax_session_focus(ctx.session_id or "") if ctx.session_id else None
        tf_year = db_focus.focus_tax_year if db_focus and db_focus.active else None
        tf_ttl = db_focus.turns_remaining if db_focus else 0

        guided_step = None
        guided_active = False
        if ctx.session_id:
            from tax_agent.tax_guided_session import get_tax_guided_session

            gs = get_tax_guided_session(ctx.session_id)
            if gs:
                guided_step = gs.guided_step
                guided_active = gs.wizard_active

        return cls(
            session_id=ctx.session_id,
            user_key=ctx.user_key,
            dataset_id=ctx.dataset_id,
            last_run_id=ctx.last_run_id,
            focus_tax_year=tf_year or ctx.tax_year,
            journey_phase=phase,
            uploaded_years=uploaded,
            broker_template_id=ctx.broker_template_id,
            filing_scope=ctx.filing_scope,
            resident_status=ctx.resident_status,
            has_compute=bool(ctx.last_run_id or ctx.last_summary),
            last_filing_snapshot=snapshot,
            last_provenance=ctx.tax_provenance,
            last_insight=ctx.tax_insight,
            last_policy_kb=ctx.policy_kb_cards,
            risk_flags=risk,
            short_symbols=list(dq.get("ambiguousSymbols") or [])[:20],
            turn_focus_year=tf_year,
            turn_focus_ttl=tf_ttl,
            guided_step=guided_step,
            guided_wizard_active=guided_active,
            data_quality=dq or None,
            fx_provider=ctx.fx_provider,
            chat_history=ctx.chat_history,
            events=list(ctx.events) if ctx.events else None,
        )

    def apply_to_session_context(self, ctx: SessionContext) -> None:
        ctx.tax_year = self.focus_tax_year
        if self.last_insight is not None:
            ctx.tax_insight = self.last_insight
        if self.last_provenance is not None:
            ctx.tax_provenance = self.last_provenance

    def update_turn_focus(self, tax_year: int, *, ttl: int = 3) -> None:
        self.turn_focus_year = tax_year
        self.turn_focus_ttl = ttl

    def tick_turn_focus(self) -> None:
        if self.turn_focus_ttl > 0:
            self.turn_focus_ttl -= 1
        if self.turn_focus_ttl <= 0:
            self.turn_focus_year = None

    def effective_tax_year(self, plan: FilingTurnPlan) -> int:
        if plan.tax_year:
            return plan.tax_year
        if self.turn_focus_year:
            return self.turn_focus_year
        return self.focus_tax_year


def _master_anchor_block(state: FilingSessionState) -> str:
    lines = [
        "【报税助手 · 会话锚点】",
        f"- 旅程阶段: {state.journey_phase}",
        *( [f"- 申报向导: {state.guided_step}（进行中）"] if state.guided_wizard_active and state.guided_step else [] ),
        f"- 关注年度: {state.focus_tax_year}",
        f"- 居民身份: {state.resident_status}",
        f"- 申报范围: {state.filing_scope}",
        f"- 已上传 dataset: {'是' if state.dataset_id else '否'}",
    ]
    if state.uploaded_years:
        lines.append(f"- 税表覆盖年度: {', '.join(str(y) for y in state.uploaded_years)}")
    if state.broker_template_id:
        lines.append(f"- 券商模板: {state.broker_template_id}")
    return "\n".join(lines)


def master_anchor_with_profile(state: FilingSessionState) -> str:
    block = _master_anchor_block(state)
    key = (state.user_key or "").strip()
    if not key:
        return block
    from tax_agent.tax_user_profile import profile_anchor_line

    line = profile_anchor_line(key)
    if not line:
        return block
    return block + "\n" + line


def _filing_scope_block() -> str:
    return (
        "【申报范围 v1】\n"
        "- 仅支持：中国税务居民 + 富途 Annual_Statement xlsx + 境外股票/期权财产转让 FIFO\n"
        "- 不支持：自动代申报、非富途券商、港股/A股/crypto\n"
        "- 免责声明：仅供参考，不构成税务意见"
    )


def _data_coverage_block(state: FilingSessionState) -> str:
    if not state.dataset_id:
        return "【材料覆盖】尚未上传税表。需 App「我的税表」→ Annual_Statement xlsx。"
    years = state.uploaded_years or ["（未能解析年度，请重新上传）"]
    amb = state.short_symbols
    lines = [
        "【材料覆盖】",
        f"- 已识别年度: {years}",
        f"- 已测算: {'是' if state.has_compute else '否'}",
    ]
    if amb:
        lines.append(f"- ambiguous 符号（需复核）: {', '.join(amb[:10])}")
    return "\n".join(lines)


def build_authoritative_filing_report(
    state: FilingSessionState,
    *,
    years: list[int] | None = None,
) -> dict[str, Any]:
    """申报权威报告：财产转让四列 + 分类所得 + combinedRows（须带 events 才有股息/利息）。"""
    if not state.data_quality:
        return {"error": "无 data_quality"}
    from tax_agent.filing_table import build_filing_report

    return build_filing_report(
        state.data_quality,
        provider=state.fx_provider,
        years=years,
        events=state.events,
    )


def _combined_row_for_year(
    report: dict[str, Any] | None,
    tax_year: int,
) -> dict[str, Any] | None:
    if not report:
        return None
    for r in report.get("combinedRows") or []:
        if int(r.get("taxYear") or 0) == tax_year:
            return r
    return None


def _filing_authority_row(state: FilingSessionState, tax_year: int) -> dict[str, Any] | None:
    snap = state.last_filing_snapshot or {}
    rows = snap.get("rows") if isinstance(snap.get("rows"), list) else None
    if rows:
        for r in rows:
            if int(r.get("taxYear") or 0) == tax_year:
                return r
    if state.data_quality:
        rep = build_authoritative_filing_report(state, years=[tax_year])
        if not rep.get("error"):
            for r in rep.get("rows") or []:
                if int(r.get("taxYear") or 0) == tax_year:
                    return r
    summary = snap.get("summary") or snap
    if isinstance(summary, dict) and summary.get("taxYear") == tax_year:
        return summary
    return None


def _filing_snapshot_block(state: FilingSessionState, tax_year: int) -> str:
    row = _filing_authority_row(state, tax_year)
    combined = None
    if state.data_quality:
        rep = build_authoritative_filing_report(state, years=[tax_year])
        if not rep.get("error"):
            combined = _combined_row_for_year(rep, tax_year)
    if row or combined:
        payload: dict[str, Any] = {"taxYear": tax_year}
        if row:
            payload["propertyTransfer"] = row
        if combined:
            if combined.get("classifiedIncome"):
                payload["classifiedIncome"] = combined["classifiedIncome"]
            if combined.get("grandTotal"):
                payload["grandTotal"] = combined["grandTotal"]
        text = json.dumps(payload, ensure_ascii=False, indent=0)
        if len(text) > 1800:
            text = text[:1800] + "…"
        return f"【FILING_TABLE_AUTHORITY · {tax_year}】\n{text}"
    snap = state.last_filing_snapshot or {}
    summary = snap.get("summary") or snap
    if not summary:
        return "【申报快照】尚无测算结果；请先 compute_tax 或生成申报数据表。"
    text = json.dumps(summary, ensure_ascii=False, indent=0)
    if len(text) > 1200:
        text = text[:1200] + "…"
    return f"【申报快照 · {tax_year}】\n{text}"


def _risk_brief_block(state: FilingSessionState) -> str:
    if not state.risk_flags:
        return "【风险简报】当前无阻断级风险标记（仍须人工复核申报）。"
    return "【风险简报】\n" + "\n".join(f"- {f}" for f in state.risk_flags[:15])


def _fx_provenance_block(state: FilingSessionState) -> str:
    prov = state.last_provenance
    if not prov:
        return "【汇率溯源】本轮无 provenance 缓存；汇率问题走 provenance_fast。"
    text = json.dumps(prov, ensure_ascii=False, indent=0)
    if len(text) > 800:
        text = text[:800] + "…"
    return f"【汇率溯源】\n{text}"


def _tax_insight_block(state: FilingSessionState) -> str:
    ins = state.last_insight
    if not ins:
        return ""
    text = json.dumps(ins, ensure_ascii=False, indent=0)
    if len(text) > 1500:
        text = text[:1500] + "…"
    return f"【TAX_INSIGHT】\n{text}"


def _policy_cards_block(state: FilingSessionState) -> str:
    cards = state.last_policy_kb
    if not cards:
        return "【POLICY_CARDS】本轮无知识卡缓存；政策问题走 policy_qa 快车道。"
    text = json.dumps(cards, ensure_ascii=False, indent=0)
    if len(text) > 1600:
        text = text[:1600] + "…"
    return f"【POLICY_CARDS · T0】\n{text}"


_SLOT_BUILDERS = {
    "MASTER_ANCHOR": lambda s, _p, y: master_anchor_with_profile(s),
    "FILING_SCOPE": lambda s, _p, _y: _filing_scope_block(),
    "DATA_COVERAGE": lambda s, _p, _y: _data_coverage_block(s),
    "FILING_SNAPSHOT": lambda s, p, y: _filing_snapshot_block(s, y),
    "FILING_TABLE_AUTHORITY": lambda s, p, y: _filing_snapshot_block(s, y),
    "RISK_BRIEF": lambda s, _p, _y: _risk_brief_block(s),
    "FX_PROVENANCE": lambda s, _p, _y: _fx_provenance_block(s),
    "TAX_INSIGHT": lambda s, _p, _y: _tax_insight_block(s),
    "POLICY_CARDS": lambda s, _p, _y: _policy_cards_block(s),
}


def _assemble_evidence_parts(
    state: FilingSessionState,
    plan: FilingTurnPlan,
    *,
    numerics_block: str = "",
    include_task: bool = True,
) -> list[str]:
    year = state.effective_tax_year(plan)
    parts: list[str] = []
    for slot in plan.slots_tier0:
        if slot == "TASK":
            if include_task:
                parts.append(f"【本轮任务】\n{plan.task_text}")
            continue
        if slot == "NUMERICS_MANIFEST" and numerics_block:
            parts.append(numerics_block)
            continue
        builder = _SLOT_BUILDERS.get(slot)
        if builder:
            block = builder(state, plan, year).strip()
            if block:
                parts.append(block)
    return parts


def build_filing_ledger_slice(
    state: FilingSessionState,
    plan: FilingTurnPlan,
    *,
    numerics_block: str = "",
) -> str:
    """FILING_LEDGER：Tier0 证据（不含 TASK，供 user 消息注入；protected SLA 组装）。"""
    from tax_agent.harness_tier0_assembly import assemble_filing_ledger

    year = state.effective_tax_year(plan)
    slot_blocks: list[tuple[str, str]] = []
    for slot in plan.slots_tier0:
        if slot == "TASK":
            continue
        if slot == "NUMERICS_MANIFEST" and numerics_block:
            slot_blocks.append((slot, numerics_block))
            continue
        builder = _SLOT_BUILDERS.get(slot)
        if builder:
            block = builder(state, plan, year).strip()
            if block:
                slot_blocks.append((slot, block))

    ledger, _assemblies, _integrity = assemble_filing_ledger(slot_blocks, plan)
    return ledger


def build_tier0_evidence_slice(
    state: FilingSessionState,
    plan: FilingTurnPlan,
    *,
    numerics_block: str = "",
    chat_recall_block: str = "",
) -> str:
    """按 plan.slots_tier0 组装 Tier0 证据块（含 TASK，兼容旧路径）。"""
    parts = _assemble_evidence_parts(
        state, plan, numerics_block=numerics_block, include_task=True
    )
    if "CHAT_RECALL" in plan.slots_tier1 and chat_recall_block.strip():
        parts.append(chat_recall_block.strip())

    budget = TAX_HARNESS_TIER0_MAX_CHARS
    out = "\n\n---\n\n".join(parts)
    if len(out) > budget:
        out = out[:budget] + "\n…（Tier0 已截断，完整数据请查申报数据表 API）"
    return out
