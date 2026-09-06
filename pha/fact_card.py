"""M1 no-LLM fact card: ledger numbers + rule bands + fixed wellness templates.

Numbers are taken only from ``wearable_daily`` rows passed in (or queried).
Point-day honesty: a missing calendar day is not filled from MAX(day).
``as_of`` may be an earlier day; then ``stale=true`` and copy must not say 今日.
Metric set comes from the wearable registry + user prefs — not a Python list.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional, Sequence

from pha.fact_card_prefs import FactCardMetricSpec, resolve_metric_specs
from pha.health_data import effective_query_reference_date
from pha.models import WearableDailySummary
from pha.wearable_time_grain import rolling_n_grain

SCHEMA = "pha.fact_card/v1"
BASELINE_DAYS = 90
MIN_BASELINE_N = 7
DISCLAIMER = "教育参考，非医疗建议，不能替代医师诊治。"

_ADVICE_MISSING = "该指标当日无记录，不用其他日期的数字代替。"
_ADVICE_UNKNOWN = "个人基线天数不足，只展示数字、不做分档。"
_SUMMARY_SYNC = "先把缺项同步进库，有数后再做恢复向评估。"
_SUMMARY_BASELINE = "个人基线不足7天，只展示数字、不做分档。"
_SUMMARY_BELOW = "有指标低于近90日个人基线，可考虑偏轻松安排。"
_SUMMARY_OK = "有数指标相对近90日个人基线大致持平或偏好。"


def _round_num(value: float, *, unit: str) -> float:
    if unit in {"count", "bpm"}:
        return float(int(round(value)))
    return round(float(value), 1)


def _fmt(value: float, unit: str) -> str:
    n = _round_num(value, unit=unit)
    if unit in {"count", "bpm"}:
        return str(int(n))
    return f"{n:.1f}".rstrip("0").rstrip(".")


def _row_value(row: WearableDailySummary, attr: str) -> Optional[float]:
    raw = getattr(row, attr, None)
    if raw is None:
        return None
    return float(raw)


def percentile_rank(value: float, samples: Sequence[float]) -> Optional[float]:
    if not samples:
        return None
    n = sum(1 for item in samples if item <= value)
    return round(100.0 * n / len(samples), 1)


def band_from_percentile(percentile: Optional[float], *, higher_is_better: bool) -> str:
    if percentile is None:
        return "unknown"
    if percentile < 25:
        raw = "below"
    elif percentile > 75:
        raw = "above"
    else:
        raw = "typical"
    if higher_is_better:
        return raw
    if raw == "below":
        return "above"
    if raw == "above":
        return "below"
    return raw


def compose_assessment_summary(
    *,
    stale: bool,
    metrics: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Card-level analysis: coverage + stale + rule bands. No LLM."""
    present = [m for m in metrics if m.get("value") is not None]
    missing = [m for m in metrics if m.get("value") is None]
    below = [m for m in present if m.get("band") == "below"]
    unknown = [m for m in present if m.get("band") == "unknown"]
    n_present = len(present)
    total = len(metrics)
    bits: list[str] = []
    if stale:
        bits.append("不是今日。")
    if total == 0:
        bits.append("未选择任何指标。")
    else:
        bits.append(f"已选{total}项中{n_present}项有数。")
    if missing:
        labels = "、".join(m["label"] for m in missing)
        bits.append(f"{labels}无记录，不顶。")
    if unknown and not below:
        bits.append(_SUMMARY_BASELINE)
    if below:
        labels = "、".join(m["label"] for m in below)
        bits.append(f"{labels}低于近90日个人基线。")
    if total == 0:
        advice = "到完整卡底部勾选要看的指标。"
        kind = "empty_selection"
    elif n_present == 0:
        advice = "库内无已选指标数字，无法评估。"
        kind = "empty"
    elif n_present < total:
        advice = _SUMMARY_SYNC
        kind = "coverage"
    elif below:
        advice = _SUMMARY_BELOW
        kind = "below_baseline"
    elif unknown:
        advice = _SUMMARY_BASELINE
        kind = "baseline_short"
    else:
        advice = _SUMMARY_OK
        kind = "typical"
    return {
        "kind": kind,
        "coverage_present": n_present,
        "coverage_total": total,
        "text": "".join(bits),
        "advice": advice,
    }


def _advice(band: str, label: str) -> str:
    if band == "missing":
        return _ADVICE_MISSING
    if band == "unknown":
        return _ADVICE_UNKNOWN
    if band == "below":
        return f"{label}低于近90日个人基线。可考虑偏轻松安排。"
    if band == "above":
        return f"{label}高于近90日个人基线。"
    if band == "typical":
        return f"{label}接近近90日个人中位。"
    return _ADVICE_UNKNOWN


def compose_fact_card(
    *,
    calendar_day: date,
    rows: Sequence[WearableDailySummary],
    user_id: str = "default",
    enabled_metric_ids: Optional[Sequence[str]] = None,
) -> dict[str, Any]:
    """Pure bind: ``rows`` is the only number source."""
    specs = resolve_metric_specs(user_id, enabled_metric_ids)
    by_day = {row.day: row for row in rows}
    as_of = max(by_day) if by_day else None
    stale = as_of is None or as_of < calendar_day
    today_row = by_day.get(calendar_day)
    as_of_row = by_day.get(as_of) if as_of is not None else None

    baseline_end = as_of or calendar_day
    grain = rolling_n_grain(BASELINE_DAYS, baseline_end)
    baseline_rows = [
        row for row in rows if grain.start <= row.day <= grain.end and row.day != as_of
    ]

    metrics: list[dict[str, Any]] = []
    advice_items: list[dict[str, str]] = []
    for spec in specs:
        metrics.append(_metric_row(spec, as_of, as_of_row, baseline_rows))
        advice_items.append(
            {
                "metric": spec.metric_id,
                "band": metrics[-1]["band"],
                "text": _advice(metrics[-1]["band"], spec.label),
            }
        )

    today_steps = None
    if today_row is not None and today_row.steps is not None:
        today_steps = int(today_row.steps)

    facts = {
        "calendar_day": calendar_day.isoformat(),
        "as_of": as_of.isoformat() if as_of is not None else None,
        "stale": stale,
        "source": "wearable_daily",
        "selection": {
            "enabled_metric_ids": [spec.metric_id for spec in specs],
            "source": "explicit" if enabled_metric_ids is not None else "prefs_or_default",
        },
        "today": {
            "day": calendar_day.isoformat(),
            "present": today_row is not None,
            "steps": today_steps,
        },
        "metrics": metrics,
    }
    summary = compose_assessment_summary(stale=stale, metrics=metrics)
    assessment = {
        "kind": "rule_band_template",
        "disclaimer": DISCLAIMER,
        "summary": summary,
        "advice": advice_items,
    }
    uid = (user_id or "default").strip() or "default"
    card = {
        "schema": SCHEMA,
        "user_id": uid,
        "facts": facts,
        "assessment": assessment,
        "notification": _notification(facts, assessment, user_id=uid),
        "disclaimer": DISCLAIMER,
    }
    return card


def _metric_row(
    spec: FactCardMetricSpec,
    as_of: Optional[date],
    as_of_row: Optional[WearableDailySummary],
    baseline_rows: Sequence[WearableDailySummary],
) -> dict[str, Any]:
    value = _row_value(as_of_row, spec.field) if as_of_row is not None else None
    samples = [
        v
        for v in (_row_value(row, spec.field) for row in baseline_rows)
        if v is not None
    ]
    unit = spec.unit
    if value is None:
        band = "missing"
        pct = None
        mean = min_v = max_v = None
    elif len(samples) < MIN_BASELINE_N:
        band = "unknown"
        pct = None
        mean = _round_num(sum(samples) / len(samples), unit=unit) if samples else None
        min_v = _round_num(min(samples), unit=unit) if samples else None
        max_v = _round_num(max(samples), unit=unit) if samples else None
    else:
        pct = percentile_rank(value, samples)
        band = band_from_percentile(pct, higher_is_better=spec.higher_is_better)
        mean = _round_num(sum(samples) / len(samples), unit=unit)
        min_v = _round_num(min(samples), unit=unit)
        max_v = _round_num(max(samples), unit=unit)
    if value is None:
        shown = None
    elif unit in {"count", "bpm"}:
        shown = int(round(value))
    else:
        shown = _round_num(value, unit=unit)
    return {
        "metric": spec.metric_id,
        "label": spec.label,
        "value": shown,
        "unit": unit,
        "day": as_of.isoformat() if as_of is not None else None,
        "baseline_n": len(samples),
        "baseline_mean": mean,
        "baseline_min": min_v,
        "baseline_max": max_v,
        "percentile": pct,
        "band": band,
    }


def _notification(facts: dict[str, Any], assessment: dict[str, Any], *, user_id: str) -> dict[str, str]:
    """Lock-screen teaser. Full list lives on the HTML view — iOS truncates body."""
    calendar_day = facts["calendar_day"]
    as_of = facts["as_of"]
    stale = bool(facts["stale"])
    title = f"PHA 事实卡 · {calendar_day}"
    summary = assessment.get("summary") or {}
    present = int(summary.get("coverage_present") or 0)
    total = int(summary.get("coverage_total") or 0)
    open_path = f"/proactive/fact-card/view?user_id={user_id}"
    if as_of is None:
        body = f"库内无穿戴日行。打开完整卡。{DISCLAIMER}"
        return {"title": title, "body": body, "open_path": open_path}
    stamp = f"截至{as_of}"
    if stale:
        stamp += "（非今日）"
    body = f"{stamp} · {present}/{total}有数\n打开完整卡看清单与评估。{DISCLAIMER}"
    return {"title": title, "body": body, "open_path": open_path}


def fact_card_numeric_atoms(card: dict[str, Any]) -> set[str]:
    """Canonical numeric strings that the card is allowed to show."""
    atoms: set[str] = set()
    facts = card.get("facts") or {}
    if facts.get("calendar_day"):
        atoms.add(str(facts["calendar_day"]))
    if facts.get("as_of"):
        atoms.add(str(facts["as_of"]))
    today = facts.get("today") or {}
    if today.get("steps") is not None:
        atoms.add(str(int(today["steps"])))
    for item in facts.get("metrics") or []:
        for key in ("value", "baseline_mean", "baseline_min", "baseline_max", "percentile", "baseline_n"):
            raw = item.get(key)
            if raw is None:
                continue
            if key == "baseline_n":
                atoms.add(str(int(raw)))
                continue
            unit = item.get("unit") or ""
            atoms.add(_fmt(float(raw), unit if key != "percentile" else "h"))
    return atoms


def load_fact_card(user_id: str, *, reference: Optional[date] = None) -> dict[str, Any]:
    from pha.sqlite_storage import query_max_wearable_daily_day, query_wearable_daily_range

    uid = (user_id or "default").strip() or "default"
    ref = reference or effective_query_reference_date()
    max_day = query_max_wearable_daily_day(uid)
    start = (max_day or ref) - timedelta(days=BASELINE_DAYS - 1)
    end = max(ref, max_day or ref)
    rows = query_wearable_daily_range(uid, start, end)
    return compose_fact_card(calendar_day=ref, rows=rows, user_id=uid)


__all__ = [
    "BASELINE_DAYS",
    "DISCLAIMER",
    "SCHEMA",
    "band_from_percentile",
    "compose_assessment_summary",
    "compose_fact_card",
    "fact_card_numeric_atoms",
    "load_fact_card",
    "percentile_rank",
]
