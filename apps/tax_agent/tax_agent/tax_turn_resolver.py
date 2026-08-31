"""TaxTurnResolver — 统一回合年度范围与澄清（v1.6，对齐 PHA temporal_router）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from tax_agent.chat_orchestrator import ChatTurnResult, infer_tax_years
from tax_agent.coverage_check import uploaded_tax_years
from tax_agent.tax_intent_catalog import (
    catalog_topic_markers,
    matches_anaphora,
    matches_multi_scope,
    token_in_message,
)

def _fx_topic_match(message: str) -> bool:
    for tok in catalog_topic_markers("policy_explain"):
        if token_in_message(tok, message):
            return True
    return bool(re.search(r"补缴汇率", message or ""))


@dataclass(frozen=True)
class TaxTurnScope:
    tax_years: list[int]
    year_source: str
    needs_clarification: bool = False
    clarification_prompt: str | None = None
    profile_hint: str | None = None
    episodic_revived: bool = False

    @property
    def primary_year(self) -> int:
        return self.tax_years[0] if self.tax_years else 0


def supplemental_tax_years_from_provider(provider: Any | None) -> list[int]:
    if provider is None:
        return []
    if hasattr(provider, "list_supplemental_tax_years"):
        return list(provider.list_supplemental_tax_years())
    monthly = getattr(provider, "monthly", None) or {}
    out: set[int] = set()
    for mk in monthly:
        parts = str(mk).split("-")
        if len(parts) == 2 and parts[1] == "12" and parts[0].isdigit():
            out.add(int(parts[0]) + 1)
    return sorted(out)


def _explicit_years(message: str, default: int) -> list[int]:
    years = infer_tax_years(message, default)
    if years == [default] and not re.search(
        r"(20\d{2}|\d{2}\s*年|\d{2,4}\s*年?\s*(?:到|至|—|-)\s*\d{2,4})",
        message or "",
    ):
        return []
    return years


def _infer_profile_hint(message: str) -> str | None:
    for topic in (
        "policy_explain",
        "coverage_check",
        "filing_coach",
        "filing_narrative",
        "risk_brief",
    ):
        for tok in catalog_topic_markers(topic):
            if token_in_message(tok, message):
                return topic
    return None


def _years_from_episodic(focus: Any) -> list[int]:
    years = getattr(focus, "focus_tax_years", None) or []
    if years:
        return [int(y) for y in years]
    y = int(getattr(focus, "focus_tax_year", 0) or 0)
    return [y] if y > 0 else []


def _topic_continues(message: str, focus: Any, profile_hint: str | None) -> bool:
    if not focus:
        return False
    msg = message or ""
    if matches_anaphora(msg):
        return True
    last_topic = (getattr(focus, "focus_profile", "") or "").strip()
    if profile_hint and last_topic and profile_hint == last_topic:
        return True
    digest = (getattr(focus, "last_assistant_digest", "") or "").strip()
    if digest:
        from tax_agent.chat_context import extract_tax_keywords

        overlap = set(extract_tax_keywords(msg)) & set(extract_tax_keywords(digest))
        if overlap:
            return True
    return False


def resolve_turn_scope(
    message: str,
    default_tax_year: int,
    *,
    data_quality: dict[str, Any] | None = None,
    fx_provider: Any | None = None,
    episodic: Any | None = None,
    profile_hint: str | None = None,
) -> TaxTurnScope:
    """Resolve effective tax year(s) for the current turn (data-driven, no hardcoded ranges)."""
    msg = (message or "").strip()
    hint = profile_hint or _infer_profile_hint(msg)
    uploaded = uploaded_tax_years(data_quality)
    fx_years = supplemental_tax_years_from_provider(fx_provider)
    explicit = _explicit_years(msg, default_tax_year)

    if explicit:
        return TaxTurnScope(
            tax_years=sorted(set(explicit)),
            year_source="explicit",
            profile_hint=hint,
        )

    if matches_multi_scope(msg):
        if uploaded:
            return TaxTurnScope(
                tax_years=uploaded,
                year_source="uploaded_all",
                profile_hint=hint,
            )
        if fx_years:
            return TaxTurnScope(
                tax_years=fx_years,
                year_source="fx_dataset",
                profile_hint=hint,
            )
        return TaxTurnScope(
            tax_years=[default_tax_year],
            year_source="clarify",
            needs_clarification=True,
            clarification_prompt="尚未上传税表，无法列出各年度汇率。请先上传富途 Annual_Statement，或指定纳税年度（如「2023年汇率」）。",
            profile_hint=hint,
        )

    active = episodic and getattr(episodic, "active", False)
    revived = False
    if episodic and not active and _topic_continues(msg, episodic, hint):
        revived = True
        active = True

    if active or revived:
        years = _years_from_episodic(episodic)
        shifted = anaphora_shift_year(msg, years) if years else None
        if shifted and shifted != years:
            return TaxTurnScope(
                tax_years=shifted,
                year_source="explicit",
                profile_hint=hint or getattr(episodic, "focus_profile", None),
                episodic_revived=revived,
            )
        if years:
            return TaxTurnScope(
                tax_years=years,
                year_source="focus",
                profile_hint=hint or getattr(episodic, "focus_profile", None),
                episodic_revived=revived,
            )

    if len(uploaded) == 1:
        return TaxTurnScope(
            tax_years=uploaded,
            year_source="uploaded_single",
            profile_hint=hint,
        )

    if len(uploaded) > 1 and _fx_topic_match(msg):
        ys = ", ".join(str(y) for y in uploaded)
        return TaxTurnScope(
            tax_years=uploaded,
            year_source="clarify",
            needs_clarification=True,
            clarification_prompt=(
                f"您已上传 {ys} 年度税表。请指定要查询的纳税年度"
                f"（例如「{uploaded[-1]}年汇率」），或说「每个年度汇率」查看对照表。"
            ),
            profile_hint=hint or "policy_explain",
        )

    return TaxTurnScope(
        tax_years=[default_tax_year],
        year_source="sidebar",
        profile_hint=hint,
    )


def scope_primary_year(scope: TaxTurnScope, default: int) -> int:
    return scope.primary_year if scope.primary_year > 0 else default


def format_clarification_reply(scope: TaxTurnScope) -> str:
    prompt = (scope.clarification_prompt or "请指定纳税年度。").strip()
    if scope.tax_years and scope.year_source == "clarify":
        choices = "、".join(str(y) for y in scope.tax_years)
        return f"{prompt}\n\n可选年度：{choices}"
    return prompt


def try_clarify_turn(scope: TaxTurnScope) -> ChatTurnResult | None:
    if not scope.needs_clarification:
        return None
    return ChatTurnResult(
        reply=format_clarification_reply(scope),
        action="clarify",
        compute_params={"taxYears": scope.tax_years, "yearSource": scope.year_source},
    )


def anaphora_shift_year(message: str, years: list[int]) -> list[int] | None:
    """「那23年呢」类指代：在续焦时切换到消息中的新年度。"""
    msg = message or ""
    explicit = _explicit_years(msg, years[0] if years else 2022)
    if explicit:
        return explicit
    m = re.search(r"那\s*(\d{2})\s*年", msg)
    if m:
        yy = int(m.group(1))
        y = 2000 + yy if yy < 70 else 1900 + yy
        return [y]
    m4 = re.search(r"那\s*(20\d{2})\s*年", msg)
    if m4:
        return [int(m4.group(1))]
    return None
