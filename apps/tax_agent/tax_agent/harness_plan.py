"""FilingTurnPlan — Tax Agent harness contract (PHA TurnEvidencePlan 报税版)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Literal

from tax_agent.chat_orchestrator import infer_tax_year
from tax_agent.tax_intent_catalog import profile_catalog_meta, resolve_profile_from_catalog

JourneyPhase = Literal[
    "onboarding",
    "collecting",
    "ready",
    "computed",
    "reviewing",
    "export",
]

TAX_HARNESS_TIER0_MAX_CHARS = int(os.environ.get("TAX_HARNESS_TIER0_MAX_CHARS", "3200"))

_ONBOARDING = re.compile(r"(怎么用|开始|入门|第一次|需要什么|材料|上传什么|checklist|清单)", re.I)
_FILING_COACH = re.compile(r"(填表|申报表|四列|怎么填|个税\s*app|财产转让|合理费用|资产原值)", re.I)
_NARRATIVE = re.compile(r"(帮我写|叙述|说明信|申报说明|润色|总结申报)", re.I)

FAST_PROFILES = frozenset(
    {
        "policy_explain",
        "policy_qa",
        "guided_filing",
        "provenance_fast",
        "insight_fast",
        "filing_onboarding",
        "coverage_check",
        "filing_narrative",
        "realized_vs_deferred",
        "holdings_year_end",
        "compound_deferral_options",
        "classified_income",
    }
)


@dataclass(frozen=True)
class FilingTurnPlan:
    """单轮 Harness 契约：profile、证据槽、禁止项、工具白名单。"""

    profile: str
    focus: str
    tax_year: int
    journey_phase: JourneyPhase
    slots_tier0: tuple[str, ...]
    slots_tier1: tuple[str, ...]
    forbidden: tuple[str, ...]
    tools_allowed: tuple[str, ...]
    task_text: str
    inject_insight: bool = False
    fast_lane: bool = False
    preserve_raw_user: bool = True
    intent_score: float = 0.0

    @property
    def all_slots(self) -> tuple[str, ...]:
        return self.slots_tier0 + self.slots_tier1

    @property
    def inject_insight_legacy(self) -> bool:
        return self.inject_insight


def _infer_journey_phase(
    *,
    has_dataset: bool,
    has_compute: bool,
    message: str,
) -> JourneyPhase:
    if _ONBOARDING.search(message) and not has_dataset:
        return "onboarding"
    if not has_dataset:
        return "collecting"
    if _FILING_COACH.search(message) or _NARRATIVE.search(message):
        return "reviewing" if has_compute else "ready"
    if has_compute:
        return "computed"
    return "ready"


# Slot/tool contracts for registry introspection (Phase A P1). Domain strings only — no PII.
PROFILE_SLOT_CONTRACTS: dict[str, dict] = {
    "casual": {
        "slots_tier0": ("MASTER_ANCHOR", "TASK"),
        "slots_tier1": (),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE", "USER_SNAPSHOT"),
        "tools_allowed": ("reply_only",),
        "task_text": "简短寒暄，引导用户上传富途 Annual_Statement 或提问具体纳税年度。",
        "fast_lane": True,
    },
    "guided_filing": {
        "slots_tier0": ("MASTER_ANCHOR", "DATA_COVERAGE", "FILING_SNAPSHOT", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE", "INVENT_POLICY"),
        "tools_allowed": ("check_coverage", "compute_tax", "get_filing_table", "reply_only"),
        "task_text": "申报向导：按 collecting→ready→computed→reviewing→export 分步辅导；数字仅来自会话状态。",
        "fast_lane": True,
    },
    "filing_onboarding": {
        "slots_tier0": ("MASTER_ANCHOR", "FILING_SCOPE", "TASK"),
        "slots_tier1": (),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE"),
        "tools_allowed": ("request_upload", "reply_only"),
        "task_text": "说明富途税表上传路径、跨年 FIFO 材料要求、免责声明。",
        "fast_lane": True,
    },
    "coverage_check": {
        "slots_tier0": ("MASTER_ANCHOR", "DATA_COVERAGE", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE"),
        "tools_allowed": ("check_coverage", "request_upload", "reply_only"),
        "task_text": "对照已上传年度列出缺口，提示需补齐的买入年至卖出年税表。",
    },
    "policy_qa": {
        "slots_tier0": ("MASTER_ANCHOR", "POLICY_CARDS", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE", "INVENT_POLICY"),
        "tools_allowed": ("reply_only",),
        "task_text": "仅依据 POLICY_CARDS 审定知识卡作答；无命中时诚实说明超范围，禁止编造法条。",
        "fast_lane": True,
    },
    "policy_explain": {
        "slots_tier0": ("MASTER_ANCHOR", "FX_PROVENANCE", "TASK"),
        "slots_tier1": (),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE", "GET_HEALTH_DATA"),
        "tools_allowed": ("reply_only", "show_report"),
        "task_text": "仅解释汇率政策与 month_key，数字来自 fx_rates / provenance 工具。",
        "fast_lane": True,
    },
    "compute": {
        "slots_tier0": ("MASTER_ANCHOR", "FILING_SNAPSHOT", "NUMERICS_MANIFEST", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE"),
        "tools_allowed": ("compute_tax", "request_upload", "reply_only"),
        "task_text": "调用 compute_tax；禁止 LLM 心算税额。",
    },
    "filing_narrative": {
        "slots_tier0": ("FILING_TABLE_AUTHORITY", "NUMERICS_MANIFEST", "RISK_BRIEF", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE"),
        "tools_allowed": ("compose_filing_narrative", "reply_only"),
        "task_text": "润色申报说明；所有金额必须来自 FILING_TABLE_AUTHORITY，经 numerics 审计。",
        "fast_lane": True,
    },
    "filing_coach": {
        "slots_tier0": ("FILING_TABLE_AUTHORITY", "FX_PROVENANCE", "RISK_BRIEF", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE"),
        "tools_allowed": ("get_filing_table", "reply_only", "show_report"),
        "task_text": "辅导个税 App 四列填表；数字仅引用申报数据表。",
    },
    "risk_brief": {
        "slots_tier0": ("MASTER_ANCHOR", "RISK_BRIEF", "TASK"),
        "slots_tier1": (),
        "forbidden": ("LLM_COMPUTE",),
        "tools_allowed": ("get_risk_brief", "reply_only"),
        "task_text": "列出 R001–R008 与 ambiguous 符号，不编造新风险。",
    },
    "compound_deferral_options": {
        "slots_tier0": ("MASTER_ANCHOR", "TAX_INSIGHT", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE"),
        "tools_allowed": ("get_tax_insight", "reply_only", "show_report"),
        "task_text": "区分已实现 vs 未实现；期权到期规则用 TAX_INSIGHT。",
        "inject_insight": True,
        "fast_lane": True,
    },
    "classified_income": {
        "slots_tier0": ("MASTER_ANCHOR", "TAX_INSIGHT", "NUMERICS_MANIFEST", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE"),
        "tools_allowed": ("get_tax_insight", "reply_only", "show_report"),
        "task_text": "股息/利息分类所得数字仅来自 TAX_INSIGHT；与财产转让分税目，不得跨类抵减。",
        "inject_insight": True,
        "fast_lane": True,
    },
    "realized_vs_deferred": {
        "slots_tier0": ("MASTER_ANCHOR", "TAX_INSIGHT", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE"),
        "tools_allowed": ("get_tax_insight", "reply_only", "show_report"),
        "task_text": "区分申报口径(T0)与辅助对照(T1)。",
        "inject_insight": True,
        "fast_lane": True,
    },
    "holdings_year_end": {
        "slots_tier0": ("MASTER_ANCHOR", "TAX_INSIGHT", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE"),
        "tools_allowed": ("get_tax_insight", "reply_only", "show_report"),
        "task_text": "年末持仓/未实现盈亏为辅助信息，不得当作应税收入。",
        "inject_insight": True,
        "fast_lane": True,
    },
    "explain_summary": {
        "slots_tier0": ("MASTER_ANCHOR", "FILING_SNAPSHOT", "NUMERICS_MANIFEST", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("LLM_COMPUTE", "INVENT_FX_RATE"),
        "tools_allowed": ("reply_only", "show_report"),
        "task_text": "解读 lastSummary / 申报表；禁止编造数字。",
    },
    "general": {
        "slots_tier0": ("MASTER_ANCHOR", "FILING_SNAPSHOT", "TASK"),
        "slots_tier1": ("CHAT_RECALL",),
        "forbidden": ("INVENT_FX_RATE",),
        "tools_allowed": (
            "compute_tax",
            "request_upload",
            "show_report",
            "reply_only",
            "get_tax_insight",
        ),
        "task_text": "一般报税问答；数值问题优先工具或快车道。",
    },
}


def _plan_from_profile(
    profile_id: str,
    *,
    year: int,
    phase: JourneyPhase,
    has_dataset: bool,
    has_compute: bool,
    meta: dict,
    intent_score: float = 0.0,
) -> FilingTurnPlan:
    focus = str(meta.get("focus") or profile_id)
    fast = bool(meta.get("fast_lane"))
    if profile_id == "coverage_check" and meta.get("fast_lane_when_no_dataset"):
        fast = not has_dataset
    inject = bool(meta.get("inject_insight"))

    tpl = PROFILE_SLOT_CONTRACTS.get(profile_id, PROFILE_SLOT_CONTRACTS["general"])
    journey: JourneyPhase = phase
    if profile_id == "filing_onboarding":
        journey = "onboarding"
    elif profile_id == "filing_narrative":
        journey = "reviewing"
    elif profile_id == "guided_filing":
        journey = phase
    elif profile_id == "filing_coach":
        journey = "reviewing" if has_compute else phase

    return FilingTurnPlan(
        profile=profile_id,
        focus=focus,
        tax_year=year,
        journey_phase=journey,
        slots_tier0=tpl["slots_tier0"],
        slots_tier1=tpl["slots_tier1"],
        forbidden=tpl["forbidden"],
        tools_allowed=tpl["tools_allowed"],
        task_text=tpl["task_text"],
        inject_insight=inject or bool(tpl.get("inject_insight")),
        fast_lane=fast or bool(tpl.get("fast_lane")),
        intent_score=intent_score,
    )


def build_filing_turn_plan(
    message: str,
    *,
    default_tax_year: int,
    has_dataset: bool = False,
    has_compute: bool = False,
    journey_phase: JourneyPhase | None = None,
    focus_tax_year: int | None = None,
    resolved_tax_year: int | None = None,
    episodic_profile: str | None = None,
) -> FilingTurnPlan:
    msg = (message or "").strip()

    if resolved_tax_year is not None:
        year = int(resolved_tax_year)
    elif focus_tax_year:
        from tax_agent.session_turn_focus import TaxSessionTurnFocus, resolve_focus_tax_year

        stub = TaxSessionTurnFocus(
            session_id="",
            focus_tax_year=focus_tax_year,
            focus_profile="",
            focus_summary="",
            focus_tokens=[str(focus_tax_year)],
            turns_remaining=1,
        )
        year = resolve_focus_tax_year(msg, default_tax_year, stub)
    else:
        year = infer_tax_year(msg, default_tax_year)

    phase = journey_phase or _infer_journey_phase(
        has_dataset=has_dataset,
        has_compute=has_compute,
        message=msg,
    )

    profile_id, score, _all = resolve_profile_from_catalog(
        msg,
        has_dataset=has_dataset,
        episodic_profile=episodic_profile,
    )
    meta = profile_catalog_meta(profile_id)
    return _plan_from_profile(
        profile_id,
        year=year,
        phase=phase,
        has_dataset=has_dataset,
        has_compute=has_compute,
        meta=meta,
        intent_score=score,
    )
