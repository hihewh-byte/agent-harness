"""M1 no-LLM fact card: ledger numbers + rule bands + fixed wellness templates.

Numbers are taken only from ``wearable_daily`` rows passed in (or queried).
Point-day honesty: a missing calendar day is not filled from MAX(day).
``as_of`` may be an earlier day; then ``stale=true`` and copy must not say 今日.
Metric set comes from the wearable registry + user prefs — not a Python list.

Baseline (v1.6 / M1-P7): per-metric progressive window 90d → 365d → all history.
Reference ranges come from the registry (Tier-1 disclosure format), not Python constants.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional, Sequence

from pha.fact_card_copy import card_copy
from pha.fact_card_prefs import (
    FactCardMetricSpec,
    catalog_by_id,
    load_fact_card_locale,
    resolve_metric_specs,
    spec_display_label,
)
from pha.health_data import effective_query_reference_date
from pha.models import WearableDailySummary
from pha.wearable_time_grain import rolling_n_grain

SCHEMA = "pha.fact_card/v1"
BASELINE_DAYS = 90
MIN_BASELINE_N = 7
DISCLAIMER = card_copy("zh-CN", "disclaimer")

# Ordered candidates: first window with n >= MIN_BASELINE_N wins.
BASELINE_CANDIDATES: tuple[tuple[str, Optional[int]], ...] = (
    ("90d", 90),
    ("365d", 365),
    ("all", None),
)

_ADVICE_MISSING = card_copy("zh-CN", "advice_missing")
_SUMMARY_SYNC = card_copy("zh-CN", "advice_coverage")
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
    locale: str = "zh-CN",
) -> str:
    unit = card_copy(locale, "unit_night" if night else "unit_day")
    if window == "90d":
        return card_copy(locale, "window_90d", n=n, unit=unit)
    if window == "365d":
        return card_copy(locale, "window_365d", n=n, unit=unit)
    if window == "all":
        since = earliest.strftime("%Y-%m") if earliest is not None else "?"
        return card_copy(locale, "window_all", since=since, n=n, unit=unit)
    return card_copy(locale, "window_short", n=n, unit=unit)


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
    locale: str = "zh-CN",
) -> str:
    status_key = {"within": "ref_within", "below": "ref_below", "above": "ref_above"}[status]
    status_label = card_copy(locale, status_key)
    lo = _fmt(low, unit)
    hi = _fmt(high, unit)
    span = f"{lo}–{hi} {unit}".strip()
    title = (note or card_copy(locale, "ref_note")).strip()
    return card_copy(
        locale,
        "ref_text",
        title=title,
        span=span,
        shown=shown,
        unit=unit,
        status=status_label,
        source=source,
    )


def build_reference(
    spec: FactCardMetricSpec,
    *,
    value: Optional[float],
    unit: str,
    locale: str = "zh-CN",
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
    note = str(rr.get("note") or card_copy(locale, "ref_note")).strip()
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
            locale=locale,
        ),
    }


def _composite_from_metrics(
    metrics: Sequence[dict[str, Any]],
    *,
    locale: str = "zh-CN",
) -> tuple[str, Optional[str]]:
    """Return (label, kind). Missing selection → not combined."""
    by_id = {str(m.get("metric") or ""): m for m in metrics}
    sleep = by_id.get(_COMPOSITE_SLEEP_ID)
    rhr = by_id.get(_COMPOSITE_RHR_ID)
    hrv = next(
        (by_id[mid] for mid in _COMPOSITE_HRV_IDS if mid in by_id),
        None,
    )
    if sleep is None or rhr is None or hrv is None:
        return card_copy(locale, "comp_none"), None
    if any(item.get("partial_day") for item in (sleep, hrv, rhr)):
        return card_copy(locale, "comp_none"), None
    bands = [sleep.get("band"), hrv.get("band"), rhr.get("band")]
    if any(b not in _BANDED for b in bands):
        return card_copy(locale, "comp_none"), None
    score = sum(1 if b == "above" else -1 if b == "below" else 0 for b in bands)
    if score <= -1:
        return card_copy(locale, "comp_easy"), "easy"
    if score >= 1:
        return card_copy(locale, "comp_good"), "good"
    return card_copy(locale, "comp_typical"), "typical"


def compose_assessment_summary(
    *,
    stale: bool,
    metrics: Sequence[dict[str, Any]],
    locale: str = "zh-CN",
) -> dict[str, Any]:
    """Card-level analysis: coverage + stale + rule bands + composite. No LLM."""
    coverage_metrics = [m for m in metrics if m.get("counts_for_coverage", True)]
    present = [m for m in coverage_metrics if m.get("value") is not None]
    missing = [m for m in coverage_metrics if m.get("value") is None]
    below = [m for m in present if m.get("band") == "below"]
    unknown = [m for m in present if m.get("band") == "unknown"]
    n_present = len(present)
    total = len(coverage_metrics)
    bits: list[str] = []
    if stale:
        bits.append(card_copy(locale, "summary_stale"))
    if len(metrics) == 0:
        bits.append(card_copy(locale, "summary_none"))
    elif total == 0:
        bits.append(card_copy(locale, "summary_sparse"))
    else:
        bits.append(card_copy(locale, "summary_cover", total=total, n=n_present))
    prior_n = sum(1 for m in present if m.get("freshness") == "prior_day")
    partial_n = sum(1 for m in present if m.get("partial_day"))
    extras: list[str] = []
    if prior_n:
        extras.append(card_copy(locale, "summary_prior", n=prior_n))
    if partial_n:
        extras.append(card_copy(locale, "summary_partial", n=partial_n))
    if extras:
        bits[-1] = bits[-1].rstrip("。").rstrip(".") + card_copy(
            locale, "summary_join", bits="，".join(extras) if locale.startswith("zh") else ", ".join(extras)
        )
    if missing:
        joiner = "、" if str(locale).startswith("zh") else ", "
        labels = joiner.join(m["label"] for m in missing)
        bits.append(card_copy(locale, "summary_missing", labels=labels))
    for item in present:
        if item.get("band") not in _BANDED:
            continue
        phrase = window_phrase(
            item.get("baseline_window"),
            int(item.get("baseline_n") or 0),
            earliest=_parse_iso_day(item.get("baseline_earliest")),
            night=_is_night_metric(str(item.get("metric") or "")),
            locale=locale,
        )
        direction = {
            "below": card_copy(locale, "dir_below"),
            "above": card_copy(locale, "dir_above"),
            "typical": card_copy(locale, "dir_typical"),
        }[str(item.get("numeric_band") or item["band"])]
        bits.append(
            card_copy(locale, "summary_dir", label=item["label"], dir=direction, phrase=phrase)
        )
    if unknown and not below:
        for item in unknown:
            n = int(item.get("baseline_n") or 0)
            if n <= 0:
                bits.append(card_copy(locale, "summary_no_hist", label=item["label"]))
            else:
                bits.append(card_copy(locale, "summary_hist_short", label=item["label"], n=n))
    composite_label, composite_kind = _composite_from_metrics(metrics, locale=locale)
    bits.append(card_copy(locale, "summary_comp", label=composite_label))
    if len(metrics) == 0:
        advice = card_copy(locale, "advice_empty_sel")
        kind = "empty_selection"
    elif total == 0:
        advice = card_copy(locale, "advice_sparse")
        kind = "sparse_only"
    elif n_present == 0:
        advice = card_copy(locale, "advice_empty")
        kind = "empty"
    elif n_present < total:
        advice = card_copy(locale, "advice_coverage")
        kind = "coverage"
    elif below:
        advice = card_copy(locale, "advice_below")
        kind = "below_baseline"
    elif unknown:
        advice = card_copy(locale, "advice_short")
        kind = "baseline_short"
    else:
        advice = card_copy(locale, "advice_typical")
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
    partial_day: bool = False,
    as_of_time: Optional[str] = None,
    freshness: Optional[str] = None,
    day: Optional[str] = None,
    numeric_band: Optional[str] = None,
    locale: str = "zh-CN",
) -> str:
    if band == "missing":
        return card_copy(locale, "advice_missing")
    if partial_day:
        until = card_copy(locale, "until", hm=as_of_time) + " " if as_of_time else ""
        return card_copy(locale, "advice_partial", label=label, until=until)
    if band == "unknown":
        if baseline_n <= 0:
            return card_copy(locale, "advice_unknown_none", label=label)
        return card_copy(locale, "advice_unknown_n", label=label, n=baseline_n)
    phrase = window_phrase(
        baseline_window,
        baseline_n,
        earliest=baseline_earliest,
        night=night,
        locale=locale,
    )
    direction_key = numeric_band or band
    easy = card_copy(locale, "easy_tail") if band == "below" else ""
    if direction_key == "below":
        return card_copy(locale, "advice_below_line", label=label, phrase=phrase, easy=easy)
    if direction_key == "above":
        return card_copy(locale, "advice_above_line", label=label, phrase=phrase, easy=easy)
    if direction_key == "typical":
        return card_copy(locale, "advice_typical_line", label=label, phrase=phrase)
    return card_copy(locale, "advice_unknown_n", label=label, n=baseline_n)


def sleep_verify_copy(
    *,
    label: str,
    value: float,
    unit: str,
    percentile: Optional[float],
    baseline_window: Optional[str] = None,
    baseline_n: int = 0,
    baseline_earliest: Optional[date] = None,
    locale: str = "zh-CN",
) -> Optional[str]:
    """Fixed template when a sleep metric sits outside the personal baseline band."""
    if percentile is None:
        return None
    if percentile < 25:
        direction = card_copy(locale, "dir_below")
    elif percentile > 75:
        direction = card_copy(locale, "dir_above")
    else:
        return None
    shown = _fmt(value, unit)
    phrase = window_phrase(
        baseline_window,
        baseline_n,
        earliest=baseline_earliest,
        night=True,
        locale=locale,
    )
    return card_copy(
        locale,
        "sleep_verify",
        label=label,
        shown=shown,
        unit=unit,
        dir=direction,
        phrase=phrase,
    )


def compose_fact_card(
    *,
    calendar_day: date,
    rows: Sequence[WearableDailySummary],
    user_id: str = "default",
    enabled_metric_ids: Optional[Sequence[str]] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Pure bind: ``rows`` is the only number source."""
    locale = load_fact_card_locale(user_id)
    specs = resolve_metric_specs(user_id, enabled_metric_ids)
    by_day = {row.day: row for row in rows}
    as_of = max(by_day) if by_day else None
    stale = as_of is None or as_of < calendar_day
    today_row = by_day.get(calendar_day)
    as_of_row = by_day.get(as_of) if as_of is not None else None
    clock = now or datetime.now()

    metrics: list[dict[str, Any]] = []
    advice_items: list[dict[str, str]] = []
    for spec in specs:
        row = _metric_row(
            spec,
            calendar_day,
            as_of,
            as_of_row,
            rows,
            by_day=by_day,
            clock=clock,
            locale=locale,
        )
        metrics.append(row)
        earliest = _parse_iso_day(row.get("baseline_earliest"))
        text = _advice(
            row["band"],
            row["label"],
            baseline_window=row.get("baseline_window"),
            baseline_n=int(row.get("baseline_n") or 0),
            baseline_earliest=earliest,
            night=_is_night_metric(spec.metric_id),
            partial_day=bool(row.get("partial_day")),
            as_of_time=row.get("as_of_time"),
            freshness=row.get("freshness"),
            day=row.get("day"),
            numeric_band=row.get("numeric_band"),
            locale=locale,
        )
        verify = None
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
                locale=locale,
            )
            if verify:
                text = verify
        advice_items.append(
            {
                "metric": spec.metric_id,
                "band": row["band"],
                "text": text,
                "sleep_verify": bool(verify) if spec.metric_id in _SLEEP_VERIFY_METRIC_IDS else False,
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
    summary = compose_assessment_summary(stale=stale, metrics=metrics, locale=locale)
    assessment = {
        "kind": "rule_band_template",
        "disclaimer": card_copy(locale, "disclaimer"),
        "summary": summary,
        "advice": advice_items,
    }
    uid = (user_id or "default").strip() or "default"
    card = {
        "schema": SCHEMA,
        "user_id": uid,
        "facts": facts,
        "assessment": assessment,
        "notification": _notification(facts, assessment, user_id=uid, locale=locale),
        "disclaimer": card_copy(locale, "disclaimer"),
    }
    return card


def _pick_value_row(
    spec: FactCardMetricSpec,
    *,
    calendar_day: date,
    as_of: Optional[date],
    as_of_row: Optional[WearableDailySummary],
    by_day: dict[date, WearableDailySummary],
    clock: datetime,
) -> tuple[
    Optional[WearableDailySummary],
    Optional[date],
    Optional[str],
    bool,
    Optional[str],
    Optional[int],
]:
    """Return (row, value_day, freshness, partial_day, as_of_time, n_days)."""
    temporal = spec.temporal or {}
    kind = str(temporal.get("kind") or "")
    if kind == "latest":
        freshness_days = max(1, int(temporal.get("freshness_days") or 90))
        for offset in range(0, freshness_days):
            day = calendar_day - timedelta(days=offset)
            row = by_day.get(day)
            if row is None or _row_value(row, spec.field) is None:
                continue
            freshness = "same_day" if day == calendar_day else "latest"
            return row, day, freshness, False, None, None
        return None, None, None, False, None, None
    if kind == "daily_lagged" or kind == "overnight":
        freshness_days = max(1, int(temporal.get("freshness_days") or 2))
        for offset in range(0, freshness_days):
            day = calendar_day - timedelta(days=offset)
            row = by_day.get(day)
            if row is None or _row_value(row, spec.field) is None:
                continue
            freshness = "same_day" if day == calendar_day else "prior_day"
            return row, day, freshness, False, None, None
        return None, None, None, False, None, None
    if kind == "accrual":
        row = by_day.get(calendar_day)
        if row is None or _row_value(row, spec.field) is None:
            return None, None, None, False, None, None
        partial = calendar_day == clock.date()
        stamp = clock.strftime("%H:%M") if partial else None
        return row, calendar_day, "same_day", partial, stamp, None
    if kind == "rolling_mean":
        window_days = max(1, int(temporal.get("window_days") or 7))
        values: list[float] = []
        for offset in range(0, window_days):
            day = calendar_day - timedelta(days=offset)
            row = by_day.get(day)
            if row is None:
                continue
            raw = _row_value(row, spec.field)
            if raw is None:
                continue
            values.append(raw)
        if not values:
            return None, None, None, False, None, 0
        mean = sum(values) / len(values)
        synthetic = WearableDailySummary(user_id="rolling", day=calendar_day)
        setattr(synthetic, spec.field, mean)
        return synthetic, calendar_day, "same_day", False, None, len(values)
    # overnight / default: existing as_of-row bind
    if as_of_row is None or as_of is None:
        return None, None, None, False, None, None
    freshness = "same_day" if as_of == calendar_day else "prior_day"
    return as_of_row, as_of, freshness, False, None, None


def _metric_row(
    spec: FactCardMetricSpec,
    calendar_day: date,
    as_of: Optional[date],
    as_of_row: Optional[WearableDailySummary],
    rows: Sequence[WearableDailySummary],
    *,
    by_day: dict[date, WearableDailySummary],
    clock: datetime,
    locale: str = "zh-CN",
) -> dict[str, Any]:
    field = spec.field
    label = spec_display_label(spec, locale)
    unit = spec.unit
    value_kind = spec.field
    higher_is_better = spec.higher_is_better
    source_row, value_day, freshness, partial_day, as_of_time, n_days = _pick_value_row(
        spec,
        calendar_day=calendar_day,
        as_of=as_of,
        as_of_row=as_of_row,
        by_day=by_day,
        clock=clock,
    )
    value = _row_value(source_row, field) if source_row is not None else None
    if spec.metric_id == "sleep_in_bed" and value is not None and value < 1.0:
        stages = (
            _row_value(source_row, "sleep_core_hours"),
            _row_value(source_row, "sleep_deep_hours"),
            _row_value(source_row, "sleep_rem_hours"),
            _row_value(source_row, "sleep_hours"),
        )
        if all(item is None for item in stages):
            value = None
    active_spec = spec
    if value is None and spec.display_fallback_metric_id:
        fallback = catalog_by_id().get(spec.display_fallback_metric_id)
        if fallback is not None:
            fb_value = (
                _row_value(source_row, fallback.field) if source_row is not None else None
            )
            if fb_value is not None:
                value = fb_value
                field = fallback.field
                label = fallback.label
                unit = fallback.unit
                value_kind = fallback.field
                higher_is_better = fallback.higher_is_better
                active_spec = fallback
    baseline_as_of = value_day or as_of
    window, samples, earliest = pick_baseline_samples(
        rows, field=field, as_of=baseline_as_of
    )
    sparse = False
    min_samples = (spec.temporal or {}).get("min_samples")
    if value is None:
        band = "missing"
        pct = None
        mean = min_v = max_v = None
    elif partial_day:
        band = "pending"
        pct = None
        mean = _round_num(sum(samples) / len(samples), unit=unit) if samples else None
        min_v = _round_num(min(samples), unit=unit) if samples else None
        max_v = _round_num(max(samples), unit=unit) if samples else None
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
    if (
        value is not None
        and not partial_day
        and isinstance(min_samples, int)
        and min_samples > 0
        and n_days is not None
        and n_days < min_samples
    ):
        band = "unknown"
        sparse = True
        pct = None
    if value is None:
        shown = None
    elif unit in {"count", "bpm"}:
        shown = int(round(value))
    else:
        shown = _round_num(value, unit=unit)
    reference = build_reference(active_spec, value=value, unit=unit, locale=locale)
    if value is None:
        numeric_band = "missing"
    elif partial_day:
        numeric_band = "pending"
    elif pct is None:
        numeric_band = "unknown"
    elif pct < 25:
        numeric_band = "below"
    elif pct > 75:
        numeric_band = "above"
    else:
        numeric_band = "typical"
    return {
        "metric": spec.metric_id,
        "label": label,
        "value": shown,
        "unit": unit,
        "value_field": value_kind,
        "day": value_day.isoformat() if value_day is not None else None,
        "freshness": freshness,
        "partial_day": partial_day,
        "as_of_time": as_of_time,
        "n_days": n_days,
        "sparse_samples": sparse,
        "baseline_n": len(samples),
        "baseline_window": window,
        "baseline_earliest": earliest.isoformat() if earliest is not None else None,
        "baseline_mean": mean,
        "baseline_min": min_v,
        "baseline_max": max_v,
        "percentile": pct,
        "band": band,
        "numeric_band": numeric_band,
        "reference": reference,
        "counts_for_coverage": spec.coverage_denominator,
    }


def _notification(
    facts: dict[str, Any],
    assessment: dict[str, Any],
    *,
    user_id: str,
    locale: str = "zh-CN",
) -> dict[str, str]:
    """Lock-screen teaser. Full list lives on the HTML view — iOS truncates body."""
    calendar_day = facts["calendar_day"]
    as_of = facts["as_of"]
    stale = bool(facts["stale"])
    title = card_copy(locale, "notif_title", day=calendar_day)
    summary = assessment.get("summary") or {}
    present = int(summary.get("coverage_present") or 0)
    total = int(summary.get("coverage_total") or 0)
    open_path = f"/proactive/fact-card/view?user_id={user_id}"
    disclaimer = card_copy(locale, "disclaimer")
    if as_of is None:
        return {
            "title": title,
            "body": card_copy(locale, "notif_empty", disclaimer=disclaimer),
            "open_path": open_path,
        }
    stamp = card_copy(locale, "notif_stamp", as_of=as_of)
    if stale:
        stamp += card_copy(locale, "notif_not_today")
    verify_lines = [
        item.get("text") or ""
        for item in (assessment.get("advice") or [])
        if item.get("sleep_verify")
        or (
            item.get("metric") in _SLEEP_VERIFY_METRIC_IDS
            and (
                "请到健康 App 核对" in str(item.get("text") or "")
                or "check this night" in str(item.get("text") or "")
            )
        )
    ]
    extra_verify = f"\n{verify_lines[0]}" if verify_lines else ""
    prior_n = sum(
        1
        for m in (facts.get("metrics") or [])
        if m.get("value") is not None and m.get("freshness") == "prior_day"
    )
    partial_n = sum(
        1 for m in (facts.get("metrics") or []) if m.get("partial_day")
    )
    cover_bits: list[str] = []
    if prior_n:
        cover_bits.append(card_copy(locale, "summary_prior", n=prior_n))
    if partial_n:
        cover_bits.append(card_copy(locale, "summary_partial", n=partial_n))
    joiner = "，" if str(locale).startswith("zh") else ", "
    cover_extra = card_copy(locale, "summary_join", bits=joiner.join(cover_bits)) if cover_bits else ""
    body = card_copy(
        locale,
        "notif_cover",
        stamp=stamp,
        present=present,
        total=total,
        extra=cover_extra,
        verify=extra_verify,
        disclaimer=disclaimer,
    )
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
        if item.get("day"):
            atoms.add(str(item["day"]))
        stamp = item.get("as_of_time")
        if stamp:
            atoms.add(str(stamp))
            parts = str(stamp).split(":")
            if len(parts) == 2:
                atoms.add(str(int(parts[0])))
                atoms.add(str(int(parts[1])))
        if item.get("n_days") is not None:
            atoms.add(str(int(item["n_days"])))
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
        from pha.wearable_metric_registry import shortcut_pack_version

        ingest_last = load_healthkit_ingest_last(uid)
        expected_pack = shortcut_pack_version()
        got_pack = str(ingest_last.get("pack_version") or "").strip()
        ingest_last["expected_pack_version"] = expected_pack
        ingest_last["pack_stale"] = bool(got_pack) and got_pack != expected_pack
        card["facts"]["ingest_last"] = ingest_last
    except Exception:
        card["facts"]["ingest_last"] = {"ok": None, "message": "receipt_unavailable"}
    try:
        from pha.fact_card_interpret import load_interpretation_for_user

        card["interpretation"] = load_interpretation_for_user(uid, card=card)
    except Exception:
        card["interpretation"] = None
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
