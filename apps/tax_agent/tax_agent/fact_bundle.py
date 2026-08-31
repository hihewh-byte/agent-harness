"""Structured facts for GroundedAnswerComposer (Tax Chat Experience v2 · C1)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_YEAR_MANIFEST_RE = re.compile(r"^20\d{2}$")


@dataclass
class PolicyCitation:
    id: str
    label: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label}


@dataclass
class FactBundle:
    profile: str
    facts: dict[str, Any] | list[dict[str, Any]]
    numerics: set[str] = field(default_factory=set)
    citations: list[PolicyCitation] = field(default_factory=list)
    fallback_markdown: str = ""
    tier: str = "T0"
    journey_phase: str | None = None
    tax_year: int | None = None
    has_dataset: bool = False

    def citations_dicts(self) -> list[dict[str, str]]:
        return [c.to_dict() for c in self.citations]

    def merged_numerics(self) -> set[str]:
        out = set(self.numerics)
        years: set[int] = set()
        if self.tax_year is not None:
            years.add(int(self.tax_year))
        for token in self.numerics:
            ts = str(token).strip()
            if _YEAR_MANIFEST_RE.match(ts):
                years.add(int(ts))
        for y in sorted(years):
            ys = str(y)
            out.add(ys)
            if y > 2000:
                out.add(str(y - 1))
            if len(ys) == 4 and ys.startswith("20"):
                out.add(ys[2:])
        return out


def _collect_provenance_numerics(rows: list[dict[str, Any]]) -> set[str]:
    nums: set[str] = set()
    for row in rows:
        y = row.get("taxYear")
        if y is not None:
            nums.add(str(int(y)))
            if int(y) > 2000:
                nums.add(str(int(y) - 1))
        rate = row.get("rate")
        if rate is not None and str(rate).strip():
            nums.add(str(rate).strip())
    return nums


def build_provenance_fact_bundle(
    rows: list[dict[str, Any]],
    *,
    fx_policy: str,
    fallback_markdown: str,
    tax_year: int | None = None,
    has_dataset: bool = False,
    journey_phase: str | None = None,
) -> FactBundle:
    """Build FactBundle from FX provenance rows (policy_explain lane)."""
    from tax_agent.fx_filing_rules import SUPPLEMENTAL_FX_LEGAL_REF

    facts: dict[str, Any] | list[dict[str, Any]]
    if len(rows) == 1:
        facts = dict(rows[0])
    else:
        facts = {
            "multi": True,
            "fxPolicy": fx_policy,
            "rows": rows,
        }

    primary_year = tax_year
    if primary_year is None and rows:
        primary_year = int(rows[0].get("taxYear") or 0) or None

    return FactBundle(
        profile="policy_explain",
        facts=facts,
        numerics=_collect_provenance_numerics(rows),
        citations=[
            PolicyCitation(
                id="kb:cn-iit-ir-art32",
                label="个人所得税法实施条例第三十二条",
            ),
        ],
        fallback_markdown=fallback_markdown,
        tier="T0",
        journey_phase=journey_phase,
        tax_year=primary_year,
        has_dataset=has_dataset,
    )


_NUMERIC_TOKEN_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _collect_numerics_deep(obj: Any) -> set[str]:
    nums: set[str] = set()

    def walk(val: Any) -> None:
        if isinstance(val, dict):
            for v in val.values():
                walk(v)
        elif isinstance(val, list):
            for item in val:
                walk(item)
        elif val is not None:
            s = str(val).strip().replace(",", "")
            if _NUMERIC_TOKEN_RE.match(s):
                nums.add(s)
            elif isinstance(val, int):
                nums.add(str(val))

    walk(obj)
    return nums


def _insight_facts_for_composer(insight: dict[str, Any]) -> dict[str, Any]:
    return {
        "taxYear": insight.get("taxYear"),
        "focus": insight.get("focus"),
        "fx": insight.get("fx"),
        "declared": insight.get("declared"),
        "filingTable": insight.get("filingTable"),
        "classifiedIncome": insight.get("classifiedIncome"),
        "grandTotal": insight.get("grandTotal"),
        "optionExpire": insight.get("optionExpire"),
        "unrealizedSummary": insight.get("unrealizedSummary"),
        "sensitivity": insight.get("sensitivity"),
        "interpretationHints": insight.get("interpretationHints"),
    }


def build_insight_fact_bundle(
    insight: dict[str, Any],
    *,
    fallback_markdown: str,
    has_dataset: bool = True,
    journey_phase: str | None = None,
) -> FactBundle:
    tax_year = int(insight.get("taxYear") or 0) or None
    facts = _insight_facts_for_composer(insight)
    nums = _collect_numerics_deep(facts)
    if tax_year:
        nums.add(str(tax_year))
    return FactBundle(
        profile="insight_fast",
        facts=facts,
        numerics=nums,
        citations=[],
        fallback_markdown=fallback_markdown,
        tier="T0",
        journey_phase=journey_phase,
        tax_year=tax_year,
        has_dataset=has_dataset,
    )


def build_filing_narrative_fact_bundle(
    row: dict[str, Any],
    *,
    tax_year: int,
    fallback_markdown: str,
    has_dataset: bool = True,
    journey_phase: str | None = None,
    classified_income: dict[str, Any] | None = None,
    grand_total: dict[str, Any] | None = None,
) -> FactBundle:
    facts: dict[str, Any] = {
        "taxYear": tax_year,
        "propertyTransfer": dict(row),
    }
    if classified_income:
        facts["classifiedIncome"] = classified_income
    if grand_total:
        facts["grandTotal"] = grand_total
    nums = _collect_numerics_deep(row)
    if classified_income:
        nums |= _collect_numerics_deep(classified_income)
    if grand_total:
        nums |= _collect_numerics_deep(grand_total)
    nums.add(str(tax_year))
    nums.add("20")
    return FactBundle(
        profile="filing_narrative",
        facts=facts,
        numerics=nums,
        citations=[],
        fallback_markdown=fallback_markdown,
        tier="T0",
        journey_phase=journey_phase,
        tax_year=tax_year,
        has_dataset=has_dataset,
    )


def build_coverage_fact_bundle(
    report: dict[str, Any],
    *,
    fallback_markdown: str,
    tax_year: int | None = None,
    journey_phase: str | None = None,
) -> FactBundle:
    nums: set[str] = set()
    for key in ("uploadedYears", "sellYears", "missingYears"):
        for y in report.get(key) or []:
            nums.add(str(int(y)))
    return FactBundle(
        profile="coverage_check",
        facts=report,
        numerics=nums,
        citations=[],
        fallback_markdown=fallback_markdown,
        tier="T0",
        journey_phase=journey_phase,
        tax_year=tax_year,
        has_dataset=bool(report.get("hasDataset")),
    )
