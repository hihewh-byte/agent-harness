"""M1 no-LLM fact card: ledger numbers + rule bands + fixed wellness templates.

Numbers are taken only from ``wearable_daily`` rows passed in (or queried).
Point-day honesty: a missing calendar day is not filled from MAX(day).
``as_of`` may be an earlier day; then ``stale=true`` and copy must not say 今日.
Metric set comes from the wearable registry + user prefs — not a Python list.

Baseline (v1.6 / M1-P7): per-metric progressive window 90d → 365d → all history.
Reference ranges come from the registry (Tier-1 disclosure format), not Python constants.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional, Sequence

from pha.fact_card_prefs import FactCardMetricSpec, catalog_by_id, resolve_metric_specs
from pha.health_data import effective_query_reference_date
from pha.models import WearableDailySummary
from pha.wearable_time_grain import rolling_n_grain

SCHEMA = "pha.fact_card/v1"
BASELINE_DAYS = 90
MIN_BASELINE_N = 7
DISCLAIMER = "教育参考，非医疗建议，不能替代医师诊治。"

# Ordered candidates: first window with n >= MIN_BASELINE_N wins.
BASELINE_CANDIDATES: tuple[tuple[str, Optional[int]], ...] = (
    ("90d", 90),
    ("365d", 365),
    ("all", None),
)

_ADVICE_MISSING = "该指标当日无记录，不用其他日期的数字代替。"
_SUMMARY_SYNC = "先把缺项同步进库，有数后再做恢复向评估。"
_SLEEP_VERIFY_METRIC_IDS = frozenset(
    {
        "sleep_time_asleep",
        "sleep_core",
        "sleep_deep",
        "sleep_rem",
        "sleep_in_bed",
        "sleep_awake",
    }
)
_COMPOSITE_SLEEP_ID = "sleep_time_asleep"
_COMPOSITE_RHR_ID = "resting_heart_rate_bpm"
_COMPOSITE_HRV_IDS = frozenset({"hrv_rmssd_ms", "hrv_sdnn_ms"})
_BANDED = frozenset({"below", "typical", "above"})


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


def _is_night_metric(metric_id: str) -> bool:
    return metric_id in _SLEEP_VERIFY_METRIC_IDS or metric_id == _COMPOSITE_SLEEP_ID


def window_phrase(
    window: Optional[str],
    n: int,
    *,
    earliest: Optional[date] = None,
    night: bool = False,
) -> str:
    unit = "夜" if night else "天"
    if window == "90d":
        return f"近 90 日 {n} {unit}"
    if window == "365d":
        return f"近 12 个月 {n} {unit}"
    if window == "all":
        since = earliest.strftime("%Y-%m") if earliest is not None else "?"
        return f"全部历史（自 {since}）{n} {unit}"
    return f"个人历史 {n}/7 {unit}"


def _samples_for_window(
    rows: Sequence[WearableDailySummary],
    *,
    field: str,
    as_of: Optional[date],
    days: Optional[int],
) -> tuple[list[float], Optional[date]]:
    earliest: Optional[date] = None
    samples: list[float] = []
    if as_of is None:
        return samples, earliest
    if days is None:
        candidates = [row for row in rows if row.day != as_of]
    else:
        grain = rolling_n_grain(days, as_of)
        candidates = [
            row
            for row in rows
            if grain.start <= row.day <= grain.end and row.day != as_of
        ]
    for row in candidates:
        value = _row_value(row, field)
        if value is None:
            continue
        samples.append(value)
        if earliest is None or row.day < earliest:
            earliest = row.day
    return samples, earliest


def pick_baseline_samples(
    rows: Sequence[WearableDailySummary],
    *,
    field: str,
    as_of: Optional[date],
) -> tuple[Optional[str], list[float], Optional[date]]:
    """Return (window_key, samples, earliest_day_in_chosen_or_all)."""
    last_samples: list[float] = []
    last_earliest: Optional[date] = None
    for key, days in BASELINE_CANDIDATES:
        samples, earliest = _samples_for_window(
            rows, field=field, as_of=as_of, days=days
        )
        last_samples, last_earliest = samples, earliest
        if len(samples) >= MIN_BASELINE_N:
            return key, samples, earliest
    return None, last_samples, last_earliest


def _reference_status(value: float, low: float, high: float) -> str:
    if value < low:
        return "below"
    if value > high:
        return "above"
    return "within"


def _reference_text(
    *,
    note: str,
    low: float,
    high: float,
    unit: str,
    shown: str,
    status: str,
    source: str,
) -> str:
    status_zh = {"within": "在范围内", "below": "低于参考范围", "above": "高于参考范围"}[
        status
    ]
    lo = _fmt(low, unit)
    hi = _fmt(high, unit)
    span = f"{lo}–{hi} {unit}".strip()
    title = (note or "常见建议范围").strip()
    return (
        f"【参考标准】{title} {span}，你今日 {shown}{unit} {status_zh}"
        f"（来源：{source}，请自行查证，非医疗建议）"
    )


def build_reference(
    spec: FactCardMetricSpec,
    *,
    value: Optional[float],
    unit: str,
) -> Optional[dict[str, Any]]:
    rr = spec.reference_range
    if not rr or value is None:
        return None
    try:
        low = float(rr["low"])
        high = float(rr["high"])
    except (KeyError, TypeError, ValueError):
        return None
    source = str(rr.get("source") or "").strip()
    if not source:
        return None
    ref_unit = str(rr.get("unit") or unit or "").strip() or unit
    status = _reference_status(value, low, high)
    shown = _fmt(value, ref_unit)
    note = str(rr.get("note") or "常见建议范围").strip()
    return {
        "low": _round_num(low, unit=ref_unit),
        "high": _round_num(high, unit=ref_unit),
        "unit": ref_unit,
        "source": source,
        "note": note,
        "status": status,
        "text": _reference_text(
            note=note,
            low=low,
            high=high,
            unit=ref_unit,
            shown=shown,
            status=status,
            source=source,
        ),
    }


def _composite_from_metrics(
    metrics: Sequence[dict[str, Any]],
) -> tuple[str, Optional[str]]:
    """Return (label, kind). Missing selection → 不综合."""
    by_id = {str(m.get("metric") or ""): m for m in metrics}
    sleep = by_id.get(_COMPOSITE_SLEEP_ID)
    rhr = by_id.get(_COMPOSITE_RHR_ID)
    hrv = next(
        (by_id[mid] for mid in _COMPOSITE_HRV_IDS if mid in by_id),
        None,
    )
    if sleep is None or rhr is None or hrv is None:
        return "不综合", None
    bands = [sleep.get("band"), hrv.get("band"), rhr.get("band")]
    if any(b not in _BANDED for b in bands):
        return "不综合", None
    score = sum(1 if b == "above" else -1 if b == "below" else 0 for b in bands)
    if score <= -1:
        return "偏轻松", "easy"
    if score >= 1:
        return "偏好", "good"
    return "持平", "typical"


def compose_assessment_summary(
    *,
    stale: bool,
    metrics: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Card-level analysis: coverage + stale + rule bands + composite. No LLM."""
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
    for item in present:
        if item.get("band") not in _BANDED:
            continue
        phrase = window_phrase(
            item.get("baseline_window"),
            int(item.get("baseline_n") or 0),
            earliest=_parse_iso_day(item.get("baseline_earliest")),
            night=_is_night_metric(str(item.get("metric") or "")),
        )
        direction = {
            "below": "低于",
            "above": "高于",
            "typical": "接近",
        }[item["band"]]
        bits.append(f"{item['label']}{direction}你{phrase}的水平。")
    if unknown and not below:
        for item in unknown:
            n = int(item.get("baseline_n") or 0)
            if n <= 0:
                bits.append(f"{item['label']}无历史，暂不分档。")
            else:
                bits.append(f"{item['label']}个人历史 {n}/7 天，暂不分档。")
    composite_label, composite_kind = _composite_from_metrics(metrics)
    bits.append(f"卡级综合：{composite_label}。")
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
        advice = "有指标低于个人基线，可考虑偏轻松安排。"
        kind = "below_baseline"
    elif unknown:
        advice = "有指标历史不足 7 天，只展示数字、暂不分档。"
        kind = "baseline_short"
    else:
        advice = "有数指标相对个人基线大致持平或偏好。"
        kind = "typical"
    return {
        "kind": kind,
        "coverage_present": n_present,
        "coverage_total": total,
        "text": "".join(bits),
        "advice": advice,
        "composite": composite_label,
        "composite_kind": composite_kind,
    }


def _parse_iso_day(raw: Any) -> Optional[date]:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _advice(
    band: str,
    label: str,
    *,
    baseline_window: Optional[str],
    baseline_n: int,
    baseline_earliest: Optional[date],
    night: bool,
) -> str:
    if band == "missing":
        return _ADVICE_MISSING
    if band == "unknown":
        if baseline_n <= 0:
            return f"{label}无历史，暂不分档。"
        return f"{label}个人历史 {baseline_n}/7 天，暂不分档。"
    phrase = window_phrase(
        baseline_window,
        baseline_n,
        earliest=baseline_earliest,
        night=night,
    )
    if band == "below":
        return f"{label}低于你{phrase}的水平。可考虑偏轻松安排。"
    if band == "above":
        return f"{label}高于你{phrase}的水平。"
    if band == "typical":
        return f"{label}接近你{phrase}的中位。"
    return f"{label}个人历史 {baseline_n}/7 天，暂不分档。"


def sleep_verify_copy(
    *,
    label: str,
    value: float,
    unit: str,
    percentile: Optional[float],
    baseline_window: Optional[str] = None,
    baseline_n: int = 0,
    baseline_earliest: Optional[date] = None,
) -> Optional[str]:
    """Fixed template when a sleep metric sits outside the personal baseline band."""
    if percentile is None:
        return None
    if percentile < 25:
        direction = "低于"
    elif percentile > 75:
        direction = "高于"
    else:
        return None
    shown = _fmt(value, unit)
    phrase = window_phrase(
        baseline_window,
        baseline_n,
        earliest=baseline_earliest,
        night=True,
    )
    return (
        f"{label} {shown}{unit}，明显{direction}你{phrase}的水平，"
        "请到健康 App 核对这一夜的数据"
    )


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

    metrics: list[dict[str, Any]] = []
    advice_items: list[dict[str, str]] = []
    for spec in specs:
        row = _metric_row(spec, as_of, as_of_row, rows)
        metrics.append(row)
        earliest = _parse_iso_day(row.get("baseline_earliest"))
        text = _advice(
            row["band"],
            row["label"],
            baseline_window=row.get("baseline_window"),
            baseline_n=int(row.get("baseline_n") or 0),
            baseline_earliest=earliest,
            night=_is_night_metric(spec.metric_id),
        )
        if (
            spec.metric_id in _SLEEP_VERIFY_METRIC_IDS
            and row.get("value") is not None
        ):
            verify = sleep_verify_copy(
                label=row["label"],
                value=float(row["value"]),
                unit=str(row.get("unit") or ""),
                percentile=row.get("percentile"),
                baseline_window=row.get("baseline_window"),
                baseline_n=int(row.get("baseline_n") or 0),
                baseline_earliest=earliest,
            )
            if verify:
                text = verify
        advice_items.append(
            {
                "metric": spec.metric_id,
                "band": row["band"],
                "text": text,
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
    rows: Sequence[WearableDailySummary],
) -> dict[str, Any]:
    field = spec.field
    label = spec.label
    unit = spec.unit
    value_kind = spec.field
    higher_is_better = spec.higher_is_better
    value = _row_value(as_of_row, field) if as_of_row is not None else None
    if spec.metric_id == "sleep_in_bed" and value is not None and value < 1.0:
        stages = (
            _row_value(as_of_row, "sleep_core_hours"),
            _row_value(as_of_row, "sleep_deep_hours"),
            _row_value(as_of_row, "sleep_rem_hours"),
            _row_value(as_of_row, "sleep_hours"),
        )
        if all(item is None for item in stages):
            value = None
    active_spec = spec
    if value is None and spec.display_fallback_metric_id:
        fallback = catalog_by_id().get(spec.display_fallback_metric_id)
        if fallback is not None:
            fb_value = _row_value(as_of_row, fallback.field) if as_of_row is not None else None
            if fb_value is not None:
                value = fb_value
                field = fallback.field
                label = fallback.label
                unit = fallback.unit
                value_kind = fallback.field
                higher_is_better = fallback.higher_is_better
                active_spec = fallback
    window, samples, earliest = pick_baseline_samples(
        rows, field=field, as_of=as_of
    )
    if value is None:
        band = "missing"
        pct = None
        mean = min_v = max_v = None
    elif window is None or len(samples) < MIN_BASELINE_N:
        band = "unknown"
        pct = None
        mean = _round_num(sum(samples) / len(samples), unit=unit) if samples else None
        min_v = _round_num(min(samples), unit=unit) if samples else None
        max_v = _round_num(max(samples), unit=unit) if samples else None
        window = None
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
    reference = build_reference(active_spec, value=value, unit=unit)
    return {
        "metric": spec.metric_id,
        "label": label,
        "value": shown,
        "unit": unit,
        "value_field": value_kind,
        "day": as_of.isoformat() if as_of is not None else None,
        "baseline_n": len(samples),
        "baseline_window": window,
        "baseline_earliest": earliest.isoformat() if earliest is not None else None,
        "baseline_mean": mean,
        "baseline_min": min_v,
        "baseline_max": max_v,
        "percentile": pct,
        "band": band,
        "reference": reference,
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
    verify_lines = [
        item.get("text") or ""
        for item in (assessment.get("advice") or [])
        if item.get("metric") in _SLEEP_VERIFY_METRIC_IDS
        and "请到健康 App 核对" in str(item.get("text") or "")
    ]
    extra = f"\n{verify_lines[0]}" if verify_lines else ""
    body = f"{stamp} · {present}/{total}有数{extra}\n打开完整卡看清单与评估。{DISCLAIMER}"
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
        ref = item.get("reference") or {}
        if isinstance(ref, dict):
            ref_unit = str(ref.get("unit") or item.get("unit") or "")
            for key in ("low", "high"):
                raw = ref.get(key)
                if raw is None:
                    continue
                atoms.add(_fmt(float(raw), ref_unit))
    return atoms


def load_fact_card(user_id: str, *, reference: Optional[date] = None) -> dict[str, Any]:
    from pha.sqlite_storage import (
        query_last_healthkit_sample,
        query_max_wearable_daily_day,
        query_wearable_daily_range,
    )

    uid = (user_id or "default").strip() or "default"
    ref = reference or effective_query_reference_date()
    max_day = query_max_wearable_daily_day(uid)
    # Progressive baseline may need full history (M1-P7); SQLite local ~3k rows is fine.
    start = date(2000, 1, 1)
    end = max(ref, max_day or ref)
    rows = query_wearable_daily_range(uid, start, end)
    card = compose_fact_card(calendar_day=ref, rows=rows, user_id=uid)
    last = query_last_healthkit_sample(uid)
    if last is None:
        card["facts"]["healthkit"] = {"reached": False}
    else:
        metric, ts, value = last
        card["facts"]["healthkit"] = {
            "reached": True,
            "last_metric": metric,
            "last_timestamp": ts,
            "last_value": value,
        }
    try:
        from pha.healthkit_ingest_receipt import load_healthkit_ingest_last

        card["facts"]["ingest_last"] = load_healthkit_ingest_last(uid)
    except Exception:
        card["facts"]["ingest_last"] = {"ok": None, "message": "receipt_unavailable"}
    return card


__all__ = [
    "BASELINE_CANDIDATES",
    "BASELINE_DAYS",
    "DISCLAIMER",
    "SCHEMA",
    "band_from_percentile",
    "build_reference",
    "compose_assessment_summary",
    "compose_fact_card",
    "fact_card_numeric_atoms",
    "load_fact_card",
    "percentile_rank",
    "pick_baseline_samples",
    "sleep_verify_copy",
    "window_phrase",
]
