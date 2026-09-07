"""Shared wearable daily rollup: metrics + sleep (import, rebuild, segment refresh)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pha.data_processor import SleepSegment, compute_sleep_hours_union
from pha.date_parser import safe_parse_datetime
from pha.models import WearableDailySummary

# Keep in sync with ``pha.sqlite_storage`` metric_type values (no import — avoids cycle).
_METRIC_STEPS = "steps"
_METRIC_HEART_RATE = "heart_rate"
_METRIC_RHR = "rhr"
_METRIC_HRV = "hrv"
_METRIC_HRV_SDNN = "hrv_sdnn"
_METRIC_SLEEP_CORE = "sleep_core"
_METRIC_SLEEP_DEEP = "sleep_deep"
_METRIC_SLEEP_REM = "sleep_rem"
_METRIC_SLEEP_IN_BED = "sleep_in_bed"
_METRIC_SLEEP_ASLEEP = "sleep_asleep"
_METRIC_AWAKE = "awake_duration"
_METRIC_ACTIVE_ENERGY = "active_energy"
_METRIC_SPO2 = "spo2"
_METRIC_RESPIRATORY_RATE = "respiratory_rate"
_METRIC_VO2MAX = "vo2max"
_METRIC_WRIST_TEMP = "wrist_temp"


@dataclass
class WearableDayMetricAgg:
    """Per-calendar-day accumulators for non-sleep wearable metrics."""

    steps_by_source: Dict[str, int] = field(default_factory=dict)
    hr_sum: float = 0.0
    hr_n: int = 0
    rhr_sum: float = 0.0
    rhr_n: int = 0
    hrv_sum: float = 0.0
    hrv_n: int = 0
    hrv_sdnn_sum: float = 0.0
    hrv_sdnn_n: int = 0
    active_energy_sum: float = 0.0
    spo2_sum: float = 0.0
    spo2_n: int = 0
    respiratory_sum: float = 0.0
    respiratory_n: int = 0
    vo2max_sum: float = 0.0
    vo2max_n: int = 0
    wrist_temp_sum: float = 0.0
    wrist_temp_n: int = 0
    # Scalar daily sleep (HealthKit ingest). Segments still win when present.
    sleep_hours_max: Optional[float] = None
    sleep_core_hours: Optional[float] = None
    sleep_deep_hours: Optional[float] = None
    sleep_rem_hours: Optional[float] = None
    sleep_asleep_hours: Optional[float] = None
    in_bed_hours: Optional[float] = None
    awake_hours: Optional[float] = None


def accumulate_wearable_sample(
    metric_type: str,
    value: float,
    sample_id: str,
    agg: WearableDayMetricAgg,
) -> None:
    """Ingest one ``wearable_data`` row into daily metric accumulators."""
    mt = str(metric_type or "")
    if mt == _METRIC_STEPS:
        src = sample_id.rsplit("|", 1)[-1].strip() if "|" in sample_id else "unknown"
        agg.steps_by_source[src] = agg.steps_by_source.get(src, 0) + int(round(value))
    elif mt == _METRIC_HEART_RATE:
        agg.hr_sum += value
        agg.hr_n += 1
    elif mt == _METRIC_RHR:
        agg.rhr_sum += value
        agg.rhr_n += 1
    elif mt == _METRIC_HRV:
        # M1-P8: legacy metric_type=hrv samples are Apple SDNN, not RMSSD.
        agg.hrv_sdnn_sum += value
        agg.hrv_sdnn_n += 1
    elif mt == _METRIC_HRV_SDNN:
        agg.hrv_sdnn_sum += value
        agg.hrv_sdnn_n += 1
    elif mt == _METRIC_ACTIVE_ENERGY:
        agg.active_energy_sum += value
    elif mt == _METRIC_SPO2:
        agg.spo2_sum += value
        agg.spo2_n += 1
    elif mt == _METRIC_RESPIRATORY_RATE:
        agg.respiratory_sum += value
        agg.respiratory_n += 1
    elif mt == _METRIC_VO2MAX:
        agg.vo2max_sum += value
        agg.vo2max_n += 1
    elif mt == _METRIC_WRIST_TEMP:
        agg.wrist_temp_sum += value
        agg.wrist_temp_n += 1
    elif mt in ("sleep", "sleep_hours"):
        if value > 0 and (agg.sleep_hours_max is None or value > agg.sleep_hours_max):
            agg.sleep_hours_max = value
    elif mt == _METRIC_SLEEP_CORE:
        agg.sleep_core_hours = value
    elif mt == _METRIC_SLEEP_DEEP:
        agg.sleep_deep_hours = value
    elif mt == _METRIC_SLEEP_REM:
        agg.sleep_rem_hours = value
    elif mt == _METRIC_SLEEP_ASLEEP:
        agg.sleep_asleep_hours = value
    elif mt == _METRIC_SLEEP_IN_BED:
        agg.in_bed_hours = value
    elif mt == _METRIC_AWAKE:
        agg.awake_hours = value


def resolve_daily_metrics(agg: WearableDayMetricAgg) -> Dict[str, Any]:
    """Resolve optional daily metric fields from accumulators."""
    steps = max(agg.steps_by_source.values()) if agg.steps_by_source else None
    if agg.rhr_n > 0:
        rhr = agg.rhr_sum / agg.rhr_n
    elif agg.hr_n > 0:
        rhr = agg.hr_sum / agg.hr_n
    else:
        rhr = None
    hrv = (agg.hrv_sum / agg.hrv_n) if agg.hrv_n > 0 else None
    hrv_sdnn = (agg.hrv_sdnn_sum / agg.hrv_sdnn_n) if agg.hrv_sdnn_n > 0 else None
    kcal = agg.active_energy_sum if agg.active_energy_sum > 0 else None
    spo2 = (agg.spo2_sum / agg.spo2_n) if agg.spo2_n > 0 else None
    resp = (agg.respiratory_sum / agg.respiratory_n) if agg.respiratory_n > 0 else None
    vo2 = (agg.vo2max_sum / agg.vo2max_n) if agg.vo2max_n > 0 else None
    wrist = (agg.wrist_temp_sum / agg.wrist_temp_n) if agg.wrist_temp_n > 0 else None
    return {
        "steps": steps,
        "resting_heart_rate_bpm": rhr,
        # Legacy RMSSD column: no Apple sample writes here after M1-P8.
        "hrv_rmssd_ms": hrv,
        "hrv_sdnn_ms": hrv_sdnn,
        "active_energy_kcal": kcal,
        "spo2_pct": spo2,
        "respiratory_rate_bpm": resp,
        "vo2max_ml_kg_min": vo2,
        "wrist_temp_c": wrist,
    }


_ASLEEP_STAGE_KINDS = frozenset({"core", "deep", "rem", "asleep"})
_STAGE_OVERLAP_RATIO = 0.05


def _is_healthkit_sleep_segment(raw: Mapping[str, Any]) -> bool:
    return str(raw.get("sample_id") or "").startswith("healthkit|")


def _interval_hours_union(pairs: Sequence[tuple[datetime, datetime]]) -> float:
    segs = [SleepSegment(start=start, end=end) for start, end in pairs if end > start]
    if not segs:
        return 0.0
    hours, _ = compute_sleep_hours_union(segs)
    return hours


def _positive_hours(hours: float) -> Optional[float]:
    return hours if hours > 0 else None


def healthkit_sleep_fields_from_segments(
    raw_segs: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """T2 HealthKit mapping: one asleep union; null stages when they disagree >5%."""
    from pha.sleep_aggregator import sleep_stage_kind_from_sample_id

    by_kind: Dict[str, List[tuple[datetime, datetime]]] = defaultdict(list)
    in_bed: List[tuple[datetime, datetime]] = []
    asleep_all: List[tuple[datetime, datetime]] = []
    first_sleep_start: Optional[datetime] = None
    for raw in raw_segs:
        start = safe_parse_datetime(str(raw.get("start_time") or ""))
        end = safe_parse_datetime(str(raw.get("end_time") or ""))
        if start is None or end is None or end <= start:
            continue
        sid = str(raw.get("sample_id") or "")
        parts = sid.split("|")
        metric = parts[2] if len(parts) >= 3 else ""
        kind = sleep_stage_kind_from_sample_id(sid)
        folded_metric = metric.replace("_", "")
        if metric == _METRIC_SLEEP_IN_BED or "inbed" in folded_metric:
            in_bed.append((start, end))
            continue
        if int(raw.get("is_awake") or 0) or kind == "awake":
            by_kind["awake"].append((start, end))
            continue
        if kind not in _ASLEEP_STAGE_KINDS:
            continue
        by_kind[kind].append((start, end))
        asleep_all.append((start, end))
        if first_sleep_start is None or start < first_sleep_start:
            first_sleep_start = start

    core_h = _interval_hours_union(by_kind["core"])
    deep_h = _interval_hours_union(by_kind["deep"])
    rem_h = _interval_hours_union(by_kind["rem"])
    asleep_h = _interval_hours_union(by_kind["asleep"])
    union_asleep = _interval_hours_union(asleep_all)
    awake_h = _interval_hours_union(by_kind["awake"])
    in_bed_h = _interval_hours_union(in_bed)
    stage_sum = core_h + deep_h + rem_h + asleep_h
    overlap = False
    if union_asleep > 0 and abs(stage_sum - union_asleep) / union_asleep > _STAGE_OVERLAP_RATIO:
        overlap = True
    per_stage_h: Dict[str, float] = {}
    if core_h > 0:
        per_stage_h["sleep_core"] = core_h
    if deep_h > 0:
        per_stage_h["sleep_deep"] = deep_h
    if rem_h > 0:
        per_stage_h["sleep_rem"] = rem_h
    if asleep_h > 0:
        per_stage_h["sleep_asleep"] = asleep_h
    if awake_h > 0:
        per_stage_h["sleep_awake"] = awake_h
    if in_bed_h > 0:
        per_stage_h["sleep_in_bed"] = in_bed_h
    period_h = 0.0
    if asleep_all:
        period_h = (
            max(end for _start, end in asleep_all) - min(start for start, _end in asleep_all)
        ).total_seconds() / 3600.0
    efficiency = None
    if in_bed_h > 0 and union_asleep > 0:
        efficiency = union_asleep / in_bed_h
    return {
        "sleep_hours": _positive_hours(union_asleep),
        "awake": _positive_hours(awake_h),
        "in_bed": _positive_hours(in_bed_h),
        "core": None if overlap else _positive_hours(core_h),
        "deep": None if overlap else _positive_hours(deep_h),
        "rem": None if overlap else _positive_hours(rem_h),
        "stage_overlap": overlap,
        "first_start": first_sleep_start,
        "per_stage_h": per_stage_h,
        "union_asleep_h": union_asleep,
        "sleep_period_h": period_h,
        "sleep_efficiency": efficiency,
    }


def sleep_stage_hours_from_segment_rows(
    raw_segs: Sequence[Mapping[str, Any]],
) -> Tuple[Optional[float], Optional[float]]:
    """Sum deep/REM asleep segment durations (hours) from DB segment rows."""
    from pha.sleep_aggregator import sleep_stage_kind_from_sample_id

    deep_s = 0.0
    rem_s = 0.0
    for raw in raw_segs:
        if int(raw.get("is_awake") or 0):
            continue
        start = safe_parse_datetime(str(raw.get("start_time") or ""))
        end = safe_parse_datetime(str(raw.get("end_time") or ""))
        if start is None or end is None or end <= start:
            continue
        dur = (end - start).total_seconds()
        stage = sleep_stage_kind_from_sample_id(str(raw.get("sample_id") or ""))
        if stage == "deep":
            deep_s += dur
        elif stage == "rem":
            rem_s += dur
    deep_h = deep_s / 3600.0 if deep_s > 0 else None
    rem_h = rem_s / 3600.0 if rem_s > 0 else None
    return deep_h, rem_h


def sleep_metrics_from_segment_rows(
    raw_segs: Sequence[Mapping[str, Any]],
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[datetime]]:
    """Return sleep_h, awake_h, deep_h, rem_h, first_sleep_start from DB segment rows."""
    asleep: List[SleepSegment] = []
    awake_seconds = 0.0
    first_sleep_start: Optional[datetime] = None
    for raw in raw_segs:
        start = safe_parse_datetime(str(raw.get("start_time") or ""))
        end = safe_parse_datetime(str(raw.get("end_time") or ""))
        if start is None or end is None:
            continue
        if int(raw.get("is_awake") or 0):
            awake_seconds += max(0.0, (end - start).total_seconds())
        else:
            asleep.append(
                SleepSegment(
                    start=start,
                    end=end,
                    source_name=str(raw.get("source_name") or ""),
                    sample_id=str(raw.get("sample_id") or ""),
                ),
            )
            if first_sleep_start is None or start < first_sleep_start:
                first_sleep_start = start

    sleep_h, _ = compute_sleep_hours_union(asleep)
    awake_h = awake_seconds / 3600.0 if awake_seconds > 0 else None
    deep_h, rem_h = sleep_stage_hours_from_segment_rows(raw_segs)
    return (
        sleep_h if sleep_h > 0 else None,
        awake_h,
        deep_h,
        rem_h,
        first_sleep_start,
    )


def sleep_metrics_from_import_accumulators(
    *,
    sleep_segments: Sequence[SleepSegment],
    sleep_deep_seconds: float,
    sleep_rem_seconds: float,
    awake_seconds: float,
    first_sleep_start: Optional[datetime],
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[datetime]]:
    """Sleep fields during zip import (before segments are persisted)."""
    sleep_h, _ = compute_sleep_hours_union(list(sleep_segments))
    sleep_h = sleep_h if sleep_h > 0 else None
    deep_h = (sleep_deep_seconds / 3600.0) if sleep_deep_seconds > 0 else None
    rem_h = (sleep_rem_seconds / 3600.0) if sleep_rem_seconds > 0 else None
    awake_h = (awake_seconds / 3600.0) if awake_seconds > 0 else None
    return sleep_h, awake_h, deep_h, rem_h, first_sleep_start


def build_wearable_daily_summary(
    user_id: str,
    day: date,
    *,
    metrics: Optional[WearableDayMetricAgg] = None,
    segment_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    import_sleep: Optional[tuple[Sequence[SleepSegment], float, float, float, Optional[datetime]]] = None,
    existing: Optional[WearableDailySummary] = None,
    sleep_only: bool = False,
) -> WearableDailySummary:
    """
    Build or patch a ``WearableDailySummary``.

    - ``metrics`` + optional ``segment_rows`` / ``import_sleep``: full day rollup.
    - ``sleep_only`` + ``segment_rows``: refresh sleep columns on ``existing`` row.
    """
    uid = (user_id or "default").strip() or "default"
    row = existing or WearableDailySummary(user_id=uid, day=day)

    if not sleep_only and metrics is not None:
        resolved = resolve_daily_metrics(metrics)
        row.steps = resolved["steps"]
        row.resting_heart_rate_bpm = resolved["resting_heart_rate_bpm"]
        row.hrv_rmssd_ms = resolved["hrv_rmssd_ms"]
        row.hrv_sdnn_ms = resolved["hrv_sdnn_ms"]
        row.active_energy_kcal = resolved["active_energy_kcal"]
        row.spo2_pct = resolved["spo2_pct"]
        row.respiratory_rate_bpm = resolved["respiratory_rate_bpm"]
        row.vo2max_ml_kg_min = resolved["vo2max_ml_kg_min"]
        row.wrist_temp_c = resolved["wrist_temp_c"]

    if segment_rows:
        hk_rows = [raw for raw in segment_rows if _is_healthkit_sleep_segment(raw)]
        other_rows = [raw for raw in segment_rows if not _is_healthkit_sleep_segment(raw)]
        if hk_rows and not other_rows:
            fields = healthkit_sleep_fields_from_segments(hk_rows)
            row.sleep_hours = fields["sleep_hours"]
            row.awake_duration_hours = fields["awake"]
            row.in_bed_hours = fields["in_bed"]
            row.sleep_core_hours = fields["core"]
            row.sleep_deep_hours = fields["deep"]
            row.sleep_rem_hours = fields["rem"]
            row.sleep_start_time = fields["first_start"]
            row.sleep_period_hours = _positive_hours(float(fields.get("sleep_period_h") or 0.0))
        else:
            sleep_h, awake_h, deep_h, rem_h, first_start = sleep_metrics_from_segment_rows(
                other_rows or segment_rows,
            )
            row.sleep_hours = sleep_h
            row.awake_duration_hours = awake_h
            row.sleep_deep_hours = deep_h
            row.sleep_rem_hours = rem_h
            row.sleep_start_time = first_start
            if row.sleep_hours is None and metrics is not None and metrics.sleep_hours_max is not None:
                row.sleep_hours = metrics.sleep_hours_max
    elif import_sleep is not None:
        segs, deep_s, rem_s, awake_s, first_start = import_sleep
        sleep_h, awake_h, deep_h, rem_h, first_start = sleep_metrics_from_import_accumulators(
            sleep_segments=segs,
            sleep_deep_seconds=deep_s,
            sleep_rem_seconds=rem_s,
            awake_seconds=awake_s,
            first_sleep_start=first_start,
        )
        row.sleep_hours = sleep_h
        row.awake_duration_hours = awake_h
        row.sleep_deep_hours = deep_h
        row.sleep_rem_hours = rem_h
        row.sleep_start_time = first_start
    elif metrics is not None:
        if metrics.sleep_core_hours is not None:
            row.sleep_core_hours = metrics.sleep_core_hours
        if metrics.sleep_deep_hours is not None:
            row.sleep_deep_hours = metrics.sleep_deep_hours
        if metrics.sleep_rem_hours is not None:
            row.sleep_rem_hours = metrics.sleep_rem_hours
        if metrics.in_bed_hours is not None:
            row.in_bed_hours = metrics.in_bed_hours
        if metrics.awake_hours is not None:
            row.awake_duration_hours = metrics.awake_hours
        asleep_parts = [
            part
            for part in (
                metrics.sleep_core_hours,
                metrics.sleep_deep_hours,
                metrics.sleep_rem_hours,
                metrics.sleep_asleep_hours,
            )
            if part is not None
        ]
        if asleep_parts:
            row.sleep_hours = float(sum(asleep_parts))
        elif metrics.sleep_hours_max is not None and row.sleep_hours is None:
            row.sleep_hours = metrics.sleep_hours_max

    return row
