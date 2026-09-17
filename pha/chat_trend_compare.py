"""M1-P23: chat wearable trend/compare — progressive baseline atoms into Manifest.

Strategy 1 only: mean / n / baseline_window as ManifestEntry atoms.
Does not call fact_card attach_assessment_* (interpret-only).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Optional, Sequence

from pha.catalog_dch import token_in_message
from pha.fact_card import (
    BASELINE_CANDIDATES,
    MIN_BASELINE_N,
    _round_num,
    _row_value,
)
from pha.health_data import effective_query_reference_date
from pha.models import WearableDailySummary


def chat_trend_compare_enabled() -> bool:
    return (os.environ.get("PHA_CHAT_TREND_COMPARE") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


@dataclass(frozen=True)
class TrendCompareStat:
    metric_id: str
    label: str
    unit: str
    mean: float
    n: int
    baseline_window: str
    earliest: Optional[date]
    as_of: date


def is_trend_compare_turn(
    user_message: str,
    *,
    user_id: str = "default",
    episodic: Any = None,
) -> bool:
    """True when chat must assemble focal + compare Manifest atoms."""
    if not chat_trend_compare_enabled():
        return False
    msg = (user_message or "").strip()
    if not msg:
        return False

    from pha.health_intent_catalog import (
        catalog_goal_markers,
        is_episodic_delta_followup_message,
        message_matches_goal_class,
    )

    block = catalog_goal_markers().get("trend_compare") or {}
    anti = block.get("anti_tokens") or []
    if any(token_in_message(str(tok), msg, case_insensitive=True) for tok in anti):
        return False

    hit = message_matches_goal_class(msg, "trend_compare") or is_episodic_delta_followup_message(
        msg
    )
    if not hit:
        return False

    from pha.ledger_passthrough_lookup import resolve_turn_wearable_scope

    uid = (user_id or "default").strip() or "default"
    scope = resolve_turn_wearable_scope(uid, msg)
    if scope.registry_ids or scope.ledger_types:
        return True
    from pha.health_intent_catalog import infer_metrics_from_message

    return bool(infer_metrics_from_message(msg))


def _window_span_days(key: str, as_of: date) -> tuple[date, date]:
    """Calendar span for a progressive candidate ending at as_of (inclusive)."""
    if key == "90d":
        start = as_of - timedelta(days=89)
        return start, as_of
    if key == "365d":
        start = as_of - timedelta(days=364)
        return start, as_of
    # all — open-ended; use earliest possible sentinel for overlap check only
    return date(2000, 1, 1), as_of


def _spans_equal(
    a_start: date,
    a_end: date,
    b_start: date,
    b_end: date,
) -> bool:
    return a_start == b_start and a_end == b_end


def _candidate_keys_for_focal(
    focal_start: date,
    focal_end: date,
    *,
    grain_source: str,
) -> tuple[tuple[str, Optional[int]], ...]:
    """Skip candidates whose natural span equals the focal window (anti-overlap)."""
    ordered: list[tuple[str, Optional[int]]] = []
    focal_days = (focal_end - focal_start).days + 1
    # Default grain ≈ 90d: starting at 90d would coincide with focal — prefer 365d→all.
    skip_90 = grain_source == "default" or focal_days >= 80
    for key, days in BASELINE_CANDIDATES:
        if skip_90 and key == "90d":
            continue
        if days is not None and days == focal_days and grain_source != "default":
            # e.g. explicit 7d focal must not use a 7d "baseline" of the same span
            continue
        ordered.append((key, days))
    return tuple(ordered) if ordered else BASELINE_CANDIDATES


def pick_compare_baseline_excluding_focal(
    rows: Sequence[WearableDailySummary],
    *,
    field: str,
    focal_start: date,
    focal_end: date,
    grain_source: str = "explicit",
) -> tuple[Optional[str], list[float], Optional[date], date]:
    """Progressive baseline; samples exclude the focal day range; reject span collision."""
    as_of = focal_end
    last_samples: list[float] = []
    last_earliest: Optional[date] = None
    for key, days in _candidate_keys_for_focal(
        focal_start, focal_end, grain_source=grain_source
    ):
        cand_start, cand_end = _window_span_days(key, as_of)
        if _spans_equal(cand_start, cand_end, focal_start, focal_end):
            continue
        # Collect with explicit focal exclusion (as_of-day skip alone is not enough).
        filtered, earliest = _samples_excluding_focal(
            rows,
            field=field,
            as_of=as_of,
            days=days,
            focal_start=focal_start,
            focal_end=focal_end,
        )
        last_samples, last_earliest = filtered, earliest
        if len(filtered) >= MIN_BASELINE_N:
            # Token / span collision: chosen window identical to focal
            if days is not None:
                w_start, w_end = _window_span_days(key, as_of)
                if _spans_equal(w_start, w_end, focal_start, focal_end):
                    continue
            return key, filtered, earliest, as_of
    return None, last_samples, last_earliest, as_of


def _samples_excluding_focal(
    rows: Sequence[WearableDailySummary],
    *,
    field: str,
    as_of: date,
    days: Optional[int],
    focal_start: date,
    focal_end: date,
) -> tuple[list[float], Optional[date]]:
    from pha.wearable_time_grain import rolling_n_grain

    earliest: Optional[date] = None
    samples: list[float] = []
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
        if focal_start <= row.day <= focal_end:
            continue
        value = _row_value(row, field)
        if value is None:
            continue
        samples.append(value)
        if earliest is None or row.day < earliest:
            earliest = row.day
    return samples, earliest


def _label_unit_for_metric(metric_id: str) -> tuple[str, str]:
    from pha.wearable_metric_registry import catalog_labels, catalog_unit_for, metric_entry

    labels = catalog_labels(metric_id)
    label = (labels.stem_zh if labels else "") or metric_id
    unit = catalog_unit_for(metric_id) or ""
    entry = metric_entry(metric_id) or {}
    if not unit:
        unit = str((entry.get("l1") or {}).get("unit") or "")
    return label, unit


def compile_trend_compare_stats(
    user_id: str,
    user_message: str,
    *,
    metric_ids: Sequence[str],
    focal_start: date,
    focal_end: date,
    grain_source: str = "explicit",
) -> list[TrendCompareStat]:
    """Rule-layer progressive baseline per metric; empty list → compare_insufficient."""
    from pha.sqlite_storage import query_max_wearable_daily_day, query_wearable_daily_range
    from pha.wearable_metric_registry import l1_field_for

    uid = (user_id or "default").strip() or "default"
    ref = effective_query_reference_date()
    max_day = query_max_wearable_daily_day(uid)
    end = max(focal_end, max_day or focal_end, ref)
    # Prefer a bounded lookback (covers 90d + 365d). Expand only if "all" is required.
    start_365 = min(focal_start, end) - timedelta(days=400)
    if start_365.year < 2000:
        start_365 = date(2000, 1, 1)
    rows = query_wearable_daily_range(uid, start_365, end)

    out: list[TrendCompareStat] = []
    need_all = False
    for mid in metric_ids:
        field = l1_field_for(mid)
        if not field:
            continue
        window, samples, earliest, as_of = pick_compare_baseline_excluding_focal(
            rows,
            field=field,
            focal_start=focal_start,
            focal_end=focal_end,
            grain_source=grain_source,
        )
        if window is None and not need_all:
            need_all = True
        if window is None or len(samples) < MIN_BASELINE_N:
            continue
        label, unit = _label_unit_for_metric(mid)
        mean = _round_num(sum(samples) / len(samples), unit=unit)
        if mean is None:
            continue
        out.append(
            TrendCompareStat(
                metric_id=mid,
                label=label,
                unit=unit or "",
                mean=float(mean),
                n=len(samples),
                baseline_window=window,
                earliest=earliest,
                as_of=as_of,
            )
        )
    if need_all and len(out) < len([m for m in metric_ids if l1_field_for(m)]):
        rows_all = query_wearable_daily_range(uid, date(2000, 1, 1), end)
        out = []
        for mid in metric_ids:
            field = l1_field_for(mid)
            if not field:
                continue
            window, samples, earliest, as_of = pick_compare_baseline_excluding_focal(
                rows_all,
                field=field,
                focal_start=focal_start,
                focal_end=focal_end,
                grain_source=grain_source,
            )
            if window is None or len(samples) < MIN_BASELINE_N:
                continue
            label, unit = _label_unit_for_metric(mid)
            mean = _round_num(sum(samples) / len(samples), unit=unit)
            if mean is None:
                continue
            out.append(
                TrendCompareStat(
                    metric_id=mid,
                    label=label,
                    unit=unit or "",
                    mean=float(mean),
                    n=len(samples),
                    baseline_window=window,
                    earliest=earliest,
                    as_of=as_of,
                )
            )
    return out


def trend_compare_manifest_entries(
    stats: Sequence[TrendCompareStat],
) -> tuple[list[Any], set[str]]:
    """Build ManifestEntry list + window_day_tokens. Import ManifestEntry lazily."""
    from pha.numerics_manifest import ManifestEntry

    entries: list[ManifestEntry] = []
    tokens: set[str] = set()
    for st in stats:
        bw = st.baseline_window
        if bw.endswith("d") and bw[:-1].isdigit():
            tokens.add(bw[:-1])
        if bw == "365d":
            tokens.add("12")
        if bw == "90d":
            tokens.add("90")
        tokens.add(str(int(st.n)))
        short = {
            "90d": "近90日",
            "365d": "近12个月",
            "all": "全部历史",
        }.get(bw, "基线")
        earliest = st.earliest.isoformat() if st.earliest else ""
        end = st.as_of.isoformat()
        anchor = f"{earliest}~{end}" if earliest else end
        entries.append(
            ManifestEntry(
                domain="wearable",
                metric=f"{st.label}·{short}均值",
                value=round(float(st.mean), 2),
                unit=st.unit or "",
                anchor=anchor,
                source="wearable.trend_compare",
            )
        )
        entries.append(
            ManifestEntry(
                domain="wearable",
                metric=f"{st.label}·{short}n",
                value=float(st.n),
                unit="-",
                anchor=anchor,
                source="wearable.trend_compare",
            )
        )
    return entries, tokens


__all__ = [
    "TrendCompareStat",
    "chat_trend_compare_enabled",
    "compile_trend_compare_stats",
    "is_trend_compare_turn",
    "pick_compare_baseline_excluding_focal",
    "trend_compare_manifest_entries",
]
