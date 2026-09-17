"""M1-P22: compile assessment rolling window / vs-yesterday into interpret inject."""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional, Sequence

from pha.fact_card import (
    MIN_BASELINE_N,
    _round_num,
    _row_value,
    _samples_for_window,
    band_from_percentile,
    percentile_rank,
)
from pha.models import WearableDailySummary
from pha.wearable_time_grain import _parse_day_count, _ROLLING_N_RE, _ROLLING_WEEK_RE

_MAX_WINDOW_DAYS = 365

_ROLLING_WEEK_N_RE = re.compile(
    r"(?:过去|近|最近)\s*(\d+|两|三|四)\s*周"
    r"|(?:last|past)\s+(\d+)\s+weeks?",
    re.I,
)
_TWO_WEEKS_RE = re.compile(
    r"近两周|过去两周|最近两周|last\s+two\s+weeks|past\s+two\s+weeks",
    re.I,
)
_YESTERDAY_COMPARE_RE = re.compile(
    r"(?:跟|与|和|比|相比|对比|比较).{0,8}昨天|昨天.{0,8}(?:相比|对比|比较|数据)"
    r"|(?:vs\.?|versus|compared\s+to|compare\s+(?:to|with))\s+yesterday",
    re.I,
)
_MONTH_30_RE = re.compile(
    r"(?:过去|近|最近).{0,4}(?:一个?月|1\s*个月)|(?:last|past)\s+30\s+days?",
    re.I,
)


def assessment_window_compare_enabled() -> bool:
    return (os.environ.get("PHA_ASSESSMENT_WINDOW_COMPARE") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


@dataclass(frozen=True)
class AssessmentWindowPlan:
    window_days: Optional[int] = None
    window_token: str = ""
    spoken_day_tokens: tuple[str, ...] = ()
    ambiguous: bool = False
    point_compare: Optional[str] = None  # "yesterday"


def _clamp_days(n: int) -> int:
    return max(1, min(int(n), _MAX_WINDOW_DAYS))


def _week_count_token(raw: str) -> Optional[int]:
    token = (raw or "").strip().lower()
    if token.isdigit():
        n = int(token)
        return n if 1 <= n <= 52 else None
    return {"两": 2, "三": 3, "四": 4}.get(token)


def iter_assessment_rolling_hits(text: str) -> list[tuple[int, str]]:
    """All explicit rolling windows in assessment text (days, surface token)."""
    raw = text or ""
    hits: list[tuple[int, str]] = []
    if not raw.strip():
        return hits
    for m in _TWO_WEEKS_RE.finditer(raw):
        hits.append((14, m.group(0)))
    for m in _ROLLING_WEEK_N_RE.finditer(raw):
        weeks = _week_count_token(m.group(1) or m.group(2) or "")
        if weeks is None:
            continue
        hits.append((_clamp_days(weeks * 7), m.group(0)))
    if _ROLLING_WEEK_RE.search(raw):
        hits.append((7, "近一周"))
    for m in _ROLLING_N_RE.finditer(raw):
        token = m.group(1) or m.group(2) or ""
        days = _parse_day_count(token)
        if days is None:
            continue
        hits.append((_clamp_days(days), m.group(0)))
    if _MONTH_30_RE.search(raw) and not any(d == 30 for d, _ in hits):
        hits.append((30, "近30天"))
    return hits


def parse_assessment_point_compare(text: str) -> Optional[str]:
    raw = text or ""
    if not raw.strip():
        return None
    if _YESTERDAY_COMPARE_RE.search(raw):
        return "yesterday"
    return None


def parse_assessment_window_plan(assessment_prompt: str) -> AssessmentWindowPlan:
    """Parse rolling N + optional vs-yesterday from assessment prompt only."""
    raw = (assessment_prompt or "").strip()
    point = parse_assessment_point_compare(raw)
    hits = iter_assessment_rolling_hits(raw)
    if not hits:
        return AssessmentWindowPlan(point_compare=point)
    distinct = sorted({d for d, _ in hits})
    if len(distinct) > 1:
        return AssessmentWindowPlan(ambiguous=True, point_compare=point)
    days = distinct[0]
    token = next(t for d, t in hits if d == days)
    spoken = [str(days)]
    if re.search(r"周|weeks?", token, re.I):
        weeks = max(1, int(round(days / 7.0)))
        spoken.append(str(weeks))
    return AssessmentWindowPlan(
        window_days=days,
        window_token=token,
        spoken_day_tokens=tuple(dict.fromkeys(spoken)),
        point_compare=point,
    )


def _metric_field(item: dict[str, Any]) -> str:
    field = str(item.get("value_field") or "").strip()
    if field:
        return field
    mid = str(item.get("metric") or "").strip()
    if not mid:
        return ""
    try:
        from pha.fact_card_prefs import catalog_by_id

        spec = catalog_by_id().get(mid)
        if spec is not None:
            return str(spec.field or "")
    except Exception:
        pass
    return ""


def _metric_hib(item: dict[str, Any]) -> bool:
    mid = str(item.get("metric") or "").strip()
    if not mid:
        return True
    try:
        from pha.fact_card_prefs import catalog_by_id

        spec = catalog_by_id().get(mid)
        if spec is not None:
            return bool(spec.higher_is_better)
    except Exception:
        pass
    return True


def _parse_iso(raw: Any) -> Optional[date]:
    text = str(raw or "")[:10]
    if len(text) != 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _compare_for_metric(
    item: dict[str, Any],
    *,
    rows: Sequence[WearableDailySummary],
    window_days: int,
    unit: str,
) -> Optional[dict[str, Any]]:
    if item.get("value") is None:
        return None
    field = _metric_field(item)
    if not field:
        return None
    anchor = _parse_iso(item.get("day"))
    if anchor is None:
        return None
    samples, _earliest = _samples_for_window(
        rows, field=field, as_of=anchor, days=window_days
    )
    if not samples:
        return {
            "n": 0,
            "mean": None,
            "min": None,
            "max": None,
            "percentile": None,
            "band": "unknown",
        }
    mean = _round_num(sum(samples) / len(samples), unit=unit)
    min_v = _round_num(min(samples), unit=unit)
    max_v = _round_num(max(samples), unit=unit)
    n = len(samples)
    if n < MIN_BASELINE_N:
        return {
            "n": n,
            "mean": mean,
            "min": min_v,
            "max": max_v,
            "percentile": None,
            "band": "unknown",
        }
    value = float(item["value"])
    pct = percentile_rank(value, samples)
    band = band_from_percentile(pct, higher_is_better=_metric_hib(item))
    return {
        "n": n,
        "mean": mean,
        "min": min_v,
        "max": max_v,
        "percentile": pct,
        "band": band,
    }


def _yesterday_for_metric(
    item: dict[str, Any],
    *,
    rows: Sequence[WearableDailySummary],
    point_day: date,
    unit: str,
) -> Optional[dict[str, Any]]:
    if item.get("value") is None:
        return None
    field = _metric_field(item)
    if not field:
        return None
    by_day = {row.day: row for row in rows}
    row = by_day.get(point_day)
    raw = _row_value(row, field) if row is not None else None
    if raw is None:
        return None
    shown = _round_num(raw, unit=unit)
    current = float(item["value"])
    delta = _round_num(current - float(shown), unit=unit)
    value_out: Any = int(shown) if unit in {"count", "bpm"} else shown
    delta_out: Any = int(round(delta)) if unit in {"count", "bpm"} else delta
    return {
        "day": point_day.isoformat(),
        "value": value_out,
        "delta": delta_out,
    }


def strip_orphan_baseline_stats(card: dict[str, Any]) -> dict[str, Any]:
    """Interpret inject only: drop mean/min/max/percentile when no baseline_window.

    Pending/short-history rows may still carry sample means with window=None; models
    then invent 「近 15 天」 to hang those numbers. Keep baseline_n for qualitative copy.
    HTML-visible cards must not call this.
    """
    out = copy.deepcopy(card) if isinstance(card, dict) else {}
    facts = out.get("facts") if isinstance(out, dict) else None
    if not isinstance(facts, dict):
        return out
    metrics = facts.get("metrics")
    if not isinstance(metrics, list):
        return out
    for item in metrics:
        if not isinstance(item, dict):
            continue
        if str(item.get("baseline_window") or "").strip():
            continue
        item["baseline_mean"] = None
        item["baseline_min"] = None
        item["baseline_max"] = None
        item["percentile"] = None
    return out


def attach_assessment_evidence(
    card: dict[str, Any],
    assessment_prompt: str,
    *,
    rows: Sequence[WearableDailySummary] | None = None,
) -> dict[str, Any]:
    """Deep-copy card and hang assessment_compare / point_compare on facts.

    HTML-visible cards must not call this. Interpret inject only.
    Progressive baseline fields are preserved (dual tokens with 90d).
    """
    if not assessment_window_compare_enabled():
        return card
    plan = parse_assessment_window_plan(assessment_prompt)
    if plan.window_days is None and not plan.point_compare and not plan.ambiguous:
        return card

    out = copy.deepcopy(card) if isinstance(card, dict) else {}
    facts = out.setdefault("facts", {}) if isinstance(out, dict) else {}
    if not isinstance(facts, dict):
        return out

    if plan.ambiguous:
        facts["assessment_compare"] = {
            "status": "ambiguous",
            "source": "assessment_prompt",
        }
    elif plan.window_days is not None:
        per_metric: dict[str, Any] = {}
        for item in facts.get("metrics") or []:
            if not isinstance(item, dict):
                continue
            mid = str(item.get("metric") or "").strip()
            if not mid:
                continue
            unit = str(item.get("unit") or "") or "-"
            block = _compare_for_metric(
                item,
                rows=rows or (),
                window_days=plan.window_days,
                unit=unit,
            )
            if block is not None:
                per_metric[mid] = block
        facts["assessment_compare"] = {
            "status": "ok",
            "window_days": plan.window_days,
            "window_label": f"{plan.window_days}d",
            "source": "assessment_prompt",
            "token": plan.window_token,
            "spoken_day_tokens": list(plan.spoken_day_tokens),
            "per_metric": per_metric,
        }

    if plan.point_compare == "yesterday":
        cal = _parse_iso(facts.get("calendar_day")) or _parse_iso(facts.get("as_of"))
        if cal is not None:
            yday = cal - timedelta(days=1)
            per_y: dict[str, Any] = {}
            for item in facts.get("metrics") or []:
                if not isinstance(item, dict):
                    continue
                mid = str(item.get("metric") or "").strip()
                if not mid:
                    continue
                unit = str(item.get("unit") or "") or "-"
                block = _yesterday_for_metric(
                    item, rows=rows or (), point_day=yday, unit=unit
                )
                if block is not None:
                    per_y[mid] = block
            facts["assessment_point_compare"] = {
                "kind": "yesterday",
                "day": yday.isoformat(),
                "source": "assessment_prompt",
                "per_metric": per_y,
            }
    return out


__all__ = [
    "AssessmentWindowPlan",
    "assessment_window_compare_enabled",
    "attach_assessment_evidence",
    "iter_assessment_rolling_hits",
    "parse_assessment_point_compare",
    "parse_assessment_window_plan",
    "strip_orphan_baseline_stats",
]
