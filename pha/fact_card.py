"""M1 no-LLM fact card: ledger numbers + rule bands + fixed wellness templates.

Numbers are taken only from ``wearable_daily`` rows passed in (or queried).
Point-day honesty: a missing calendar day is not filled from MAX(day).
``as_of`` may be an earlier day; then ``stale=true`` and copy must not say 今日.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional, Sequence

from pha.health_data import effective_query_reference_date
from pha.models import WearableDailySummary
from pha.wearable_time_grain import rolling_n_grain

SCHEMA = "pha.fact_card/v1"
BASELINE_DAYS = 90
MIN_BASELINE_N = 7
DISCLAIMER = "教育参考，非医疗建议，不能替代医师诊治。"

# (key, row attr, zh label, unit, higher_is_better)
_METRICS: tuple[tuple[str, str, str, str, bool], ...] = (
    ("steps", "steps", "步数", "count", True),
    ("hrv", "hrv_rmssd_ms", "HRV", "ms", True),
    ("rhr", "resting_heart_rate_bpm", "静息心率", "bpm", False),
    ("sleep_hours", "sleep_hours", "睡眠", "h", True),
    ("active_energy", "active_energy_kcal", "活动消耗", "kcal", True),
)

_ADVICE: dict[tuple[str, str], str] = {
    ("steps", "below"): "步数低于近90日个人基线。可安排步行或日常活动。",
    ("steps", "typical"): "步数接近近90日个人中位。",
    ("steps", "above"): "步数高于近90日个人基线。注意休息与补水。",
    ("hrv", "below"): "HRV低于近90日个人基线。可考虑偏轻松安排。",
    ("hrv", "typical"): "HRV接近近90日个人中位。",
    ("hrv", "above"): "HRV高于近90日个人基线。",
    ("rhr", "below"): "静息心率高于近90日个人基线。可考虑偏轻松安排。",
    ("rhr", "typical"): "静息心率接近近90日个人中位。",
    ("rhr", "above"): "静息心率低于近90日个人基线。",
    ("sleep_hours", "below"): "睡眠短于近90日个人基线。可优先保证夜间休息。",
    ("sleep_hours", "typical"): "睡眠接近近90日个人中位。",
    ("sleep_hours", "above"): "睡眠长于近90日个人基线。",
    ("active_energy", "below"): "活动消耗低于近90日个人基线。",
    ("active_energy", "typical"): "活动消耗接近近90日个人中位。",
    ("active_energy", "above"): "活动消耗高于近90日个人基线。注意恢复。",
}
_ADVICE_MISSING = "该指标当日无记录，不用其他日期的数字代替。"
_ADVICE_UNKNOWN = "个人基线天数不足，只展示数字、不做分档。"
WHITELIST_N = len(_METRICS)
_SUMMARY_SYNC = "先把缺项同步进库（HRV/睡眠/心率/消耗），有数后再做恢复向评估。"
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
    bits: list[str] = []
    if stale:
        bits.append("不是今日。")
    bits.append(f"白名单{WHITELIST_N}项中{n_present}项有数。")
    if missing:
        labels = "、".join(m["label"] for m in missing)
        bits.append(f"{labels}无记录，不顶。")
    if unknown and not below:
        bits.append(_SUMMARY_BASELINE)
    if below:
        labels = "、".join(m["label"] for m in below)
        bits.append(f"{labels}低于近90日个人基线。")
    if n_present == 0:
        advice = "库内无白名单数字，无法评估。"
        kind = "empty"
    elif n_present < WHITELIST_N:
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
        "coverage_total": WHITELIST_N,
        "text": "".join(bits),
        "advice": advice,
    }


def _advice(metric: str, band: str) -> str:
    if band == "missing":
        return _ADVICE_MISSING
    if band == "unknown":
        return _ADVICE_UNKNOWN
    return _ADVICE.get((metric, band), _ADVICE_UNKNOWN)


def compose_fact_card(
    *,
    calendar_day: date,
    rows: Sequence[WearableDailySummary],
    user_id: str = "default",
) -> dict[str, Any]:
    """Pure bind: ``rows`` is the only number source."""
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
    for key, attr, label, unit, higher_is_better in _METRICS:
        value = _row_value(as_of_row, attr) if as_of_row is not None else None
        samples = [
            v
            for v in (_row_value(row, attr) for row in baseline_rows)
            if v is not None
        ]
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
            band = band_from_percentile(pct, higher_is_better=higher_is_better)
            mean = _round_num(sum(samples) / len(samples), unit=unit)
            min_v = _round_num(min(samples), unit=unit)
            max_v = _round_num(max(samples), unit=unit)
        if value is None:
            shown = None
        elif unit in {"count", "bpm"}:
            shown = int(round(value))
        else:
            shown = _round_num(value, unit=unit)
        metrics.append(
            {
                "metric": key,
                "label": label,
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
        )
        advice_items.append(
            {
                "metric": key,
                "band": band,
                "text": _advice(key, band),
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
    card = {
        "schema": SCHEMA,
        "user_id": user_id,
        "facts": facts,
        "assessment": assessment,
        "notification": _notification(facts, assessment),
        "disclaimer": DISCLAIMER,
    }
    return card


def _metric_bit(item: dict[str, Any]) -> str:
    if item["value"] is None:
        return f"{item['label']}无"
    unit_s = "" if item["unit"] == "count" else item["unit"]
    return f"{item['label']}{_fmt(float(item['value']), item['unit'])}{unit_s}"


def _notification(facts: dict[str, Any], assessment: dict[str, Any]) -> dict[str, str]:
    calendar_day = facts["calendar_day"]
    as_of = facts["as_of"]
    stale = bool(facts["stale"])
    title = f"PHA 事实卡 · {calendar_day}"
    if as_of is None:
        body = f"库内无穿戴日行。评估：无法评估。{DISCLAIMER}"
        return {"title": title, "body": body}
    stamp = f"截至{as_of}"
    if stale:
        stamp += "（非今日）"
    facts_line = " · ".join(_metric_bit(item) for item in facts["metrics"])
    summary = assessment.get("summary") or {}
    eval_line = summary.get("text") or ""
    advice_line = summary.get("advice") or _ADVICE_UNKNOWN
    body = f"{stamp}\n{facts_line}\n评估：{eval_line}\n建议：{advice_line} {DISCLAIMER}"
    return {"title": title, "body": body}


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
