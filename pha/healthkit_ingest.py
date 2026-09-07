"""HealthKit JSON ingest → ``wearable_data`` + same-day ``wearable_daily`` rebuild.

M0-P0: fail-closed parse, token auth, no LLM, no invented samples.
Source is encoded in ``sample_id`` (``healthkit|{user}|{metric}|{ts}|healthkit``);
``wearable_data`` has no dedicated source column in v1.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from dataclasses import dataclass
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from pha.date_parser import safe_parse_datetime
from pha.sqlite_storage import (
    METRIC_ACTIVE_ENERGY,
    METRIC_HRV_SDNN,
    METRIC_RHR,
    METRIC_AWAKE,
    METRIC_SLEEP,
    METRIC_SLEEP_ASLEEP,
    METRIC_SLEEP_CORE,
    METRIC_SLEEP_DEEP,
    METRIC_SLEEP_IN_BED,
    METRIC_SLEEP_REM,
    METRIC_STEPS,
    WearableDataBatchWriter,
    delete_healthkit_sleep_family_on_day,
    delete_stale_healthkit_metric_on_day,
    rebuild_wearable_daily_for_days,
    replace_healthkit_sleep_segments_for_day,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])

INGEST_TOKEN_ENV = "PHA_INGEST_TOKEN"
INGEST_TZ_ENV = "PHA_INGEST_TZ"
DEFAULT_INGEST_TZ = "Asia/Shanghai"
MAX_SAMPLES = 5000
INGEST_SOURCE = "healthkit"
_VALUE_TOKEN_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

# Public v1 names → stored ``wearable_data.metric_type``.
_CANONICAL: dict[str, str] = {
    "hrv": METRIC_HRV_SDNN,
    "hrv_sdnn": METRIC_HRV_SDNN,
    "rhr": METRIC_RHR,
    "steps": METRIC_STEPS,
    "sleep_hours": METRIC_SLEEP,
    "sleep": METRIC_SLEEP,
    "sleep_core": METRIC_SLEEP_CORE,
    "sleep_deep": METRIC_SLEEP_DEEP,
    "sleep_rem": METRIC_SLEEP_REM,
    "sleep_in_bed": METRIC_SLEEP_IN_BED,
    "sleep_asleep": METRIC_SLEEP_ASLEEP,
    "sleep_awake": METRIC_AWAKE,
    "active_energy": METRIC_ACTIVE_ENERGY,
}

_SLEEP_HOUR_METRICS = frozenset(
    {
        METRIC_SLEEP,
        METRIC_SLEEP_CORE,
        METRIC_SLEEP_DEEP,
        METRIC_SLEEP_REM,
        METRIC_SLEEP_IN_BED,
        METRIC_SLEEP_ASLEEP,
        METRIC_AWAKE,
    }
)
_ASLEEP_STAGE_METRICS = frozenset(
    {
        METRIC_SLEEP_CORE,
        METRIC_SLEEP_DEEP,
        METRIC_SLEEP_REM,
        METRIC_SLEEP_ASLEEP,
    }
)

# Shortcuts / HealthKit type identifiers (lowercased, no punctuation).
_ALIASES: dict[str, str] = {
    "hkquantitytypeidentifierheartratevariabilitysdnn": METRIC_HRV_SDNN,
    "heartratevariabilitysdnn": METRIC_HRV_SDNN,
    "hkquantitytypeidentifierrestingheartrate": METRIC_RHR,
    "restingheartrate": METRIC_RHR,
    "hkquantitytypeidentifierstepcount": METRIC_STEPS,
    "stepcount": METRIC_STEPS,
    "hkcategorytypeidentifiersleepanalysis": METRIC_SLEEP,
    "sleepanalysis": METRIC_SLEEP,
    "hkquantitytypeidentifieractiveenergyburned": METRIC_ACTIVE_ENERGY,
    "activeenergyburned": METRIC_ACTIVE_ENERGY,
}


class HealthKitSample(BaseModel):
    metric_type: str
    timestamp: str
    value: float
    unit: Optional[str] = None
    source: str = INGEST_SOURCE


class HealthKitIngestRequest(BaseModel):
    user_id: str = "default"
    token: Optional[str] = None
    samples: list[HealthKitSample] = Field(default_factory=list)


@dataclass
class IngestResult:
    inserted: int
    ignored: int
    dropped: int
    days_rebuilt: int
    sample_ids: list[str]
    timestamp_defaulted: int = 0
    audit: Optional[dict[str, Any]] = None


def ingest_token_configured() -> str:
    return os.environ.get(INGEST_TOKEN_ENV, "").strip()


def ingest_tz_name() -> str:
    raw = os.environ.get(INGEST_TZ_ENV, "").strip()
    return raw or DEFAULT_INGEST_TZ


def _fold_metric_key(raw: str) -> str:
    return "".join(ch for ch in (raw or "").strip().lower() if ch.isalnum())


def resolve_metric_type(raw: str) -> Optional[str]:
    key = (raw or "").strip().lower()
    if key in _CANONICAL:
        return _CANONICAL[key]
    folded = _fold_metric_key(raw)
    if folded in _CANONICAL:
        return _CANONICAL[folded]
    return _ALIASES.get(folded)


def _load_zoneinfo(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown_ingest_tz:{tz_name}") from exc


def normalize_timestamp(raw: str, tz_name: str) -> datetime:
    """Parse ISO-8601 to naive local time so ``substr(timestamp,1,10)`` is calendar day."""
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty_timestamp")
    tz = _load_zoneinfo(tz_name)
    parsed = safe_parse_datetime(s)
    if parsed is None:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(s)
        except ValueError as exc:
            raise ValueError(f"unreadable_timestamp:{raw}") from exc
    dt = parsed
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    local = dt.astimezone(tz)
    return local.replace(tzinfo=None)


def _as_sleep_hours(metric: str, value: float) -> float:
    """Accept hours, or Duration-as-seconds. Reject empty-night 0 and >16h."""
    if 0 < value <= 16:
        return value
    # Duration coerced through Math is seconds; ignore 16–60 (not hours, not 1min+).
    if value >= 60 and value <= 16 * 3600:
        hours = value / 3600.0
        if 0 < hours <= 16:
            logger.info(
                "healthkit_ingest sleep seconds→hours metric=%s raw=%s hours=%s",
                metric,
                value,
                hours,
            )
            return hours
    logger.warning(
        "healthkit_ingest implausible_sleep_hours metric=%s value=%s",
        metric,
        value,
    )
    raise ValueError("implausible_sleep_hours")


_SLEEP_STAGE_FOLD: dict[str, str] = {
    "inbed": "sleep_in_bed",
    "timeinbed": "sleep_in_bed",
    "asleepcore": "sleep_core",
    "core": "sleep_core",
    "asleepdeep": "sleep_deep",
    "deep": "sleep_deep",
    "asleeprem": "sleep_rem",
    "rem": "sleep_rem",
    "awake": "sleep_awake",
    "asleepunspecified": "sleep_asleep",
    "asleep": "sleep_asleep",
}


def _fold_sleep_stage_label(raw: str) -> str:
    return "".join(ch for ch in (raw or "").lower() if ch.isalnum())


def resolve_sleep_stage_metric(raw: str) -> Optional[str]:
    return _SLEEP_STAGE_FOLD.get(_fold_sleep_stage_label(raw))


def _as_str_list(raw: Any) -> list[str]:
    if raw is None:
        raise ValueError("sleep_stage_list_mismatch")
    if isinstance(raw, (list, tuple)):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    if "|" in text:
        return [part.strip() for part in text.split("|") if part.strip()]
    if "\n" in text:
        return [part.strip() for part in text.splitlines() if part.strip()]
    return [text]


def _union_hours(intervals: list[tuple[datetime, datetime]]) -> float:
    if not intervals:
        return 0.0
    ordered = sorted(intervals, key=lambda item: item[0])
    cur_start, cur_end = ordered[0]
    total = 0.0
    for start, end in ordered[1:]:
        if start <= cur_end:
            if end > cur_end:
                cur_end = end
            continue
        total += (cur_end - cur_start).total_seconds()
        cur_start, cur_end = start, end
    total += (cur_end - cur_start).total_seconds()
    return total / 3600.0


def sleep_stage_hour_samples_from_lists(
    values_raw: Any,
    starts_raw: Any,
    ends_raw: Any,
    *,
    tz_name: str,
    now: Optional[datetime] = None,
) -> list[dict[str, Any]]:
    """Pair Find Sleep Value + Start + End lists; keep segments overlapping last 24h."""
    values = _as_str_list(values_raw)
    starts = _as_str_list(starts_raw)
    ends = _as_str_list(ends_raw)
    if not values or len(values) != len(starts) or len(values) != len(ends):
        raise ValueError("sleep_stage_list_mismatch")
    tz = _load_zoneinfo(tz_name)
    local_now = now or datetime.now(tz).replace(tzinfo=None)
    window_start = local_now - timedelta(hours=24)
    intervals: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    kept = 0
    skipped_zero = 0
    for label, start_raw, end_raw in zip(values, starts, ends):
        metric = resolve_sleep_stage_metric(label)
        if metric is None:
            continue
        start = normalize_timestamp(start_raw, tz_name)
        end = normalize_timestamp(end_raw, tz_name)
        delta = (end - start).total_seconds()
        if delta <= 0:
            # Shortcuts Get Details is minute-precision; a 20s blip becomes end==start.
            if delta >= -120:
                skipped_zero += 1
                logger.info(
                    "healthkit_ingest skip zero-duration sleep stage=%s start=%r end=%r",
                    metric,
                    start_raw,
                    end_raw,
                )
                continue
            raise ValueError(f"implausible_sleep_hours:end_before_start:{start_raw}..{end_raw}")
        clip_start = max(start, window_start)
        clip_end = min(end, local_now)
        if clip_end <= clip_start:
            continue
        intervals[metric].append((clip_start, clip_end))
        kept += 1
    if kept == 0:
        raise ValueError("empty_sleep_window")
    if skipped_zero:
        logger.info("healthkit_ingest skipped_zero_duration_sleep=%s kept=%s", skipped_zero, kept)
    out: list[dict[str, Any]] = []
    for metric, metric_intervals in intervals.items():
        value = _union_hours(metric_intervals)
        if value <= 0:
            continue
        out.append(
            {
                "metric_type": metric,
                "timestamp": "",
                "value": value,
                "unit": "h",
                "source": INGEST_SOURCE,
            }
        )
    if not out:
        raise ValueError("empty_sleep_window")
    return out


def _sleep_wake_window(wake_day: date) -> tuple[datetime, datetime]:
    noon = datetime.combine(wake_day, time(12, 0, 0))
    return noon - timedelta(days=1), noon


def _clip_to_window(
    start: datetime,
    end: datetime,
    window_start: datetime,
    window_end: datetime,
) -> Optional[tuple[datetime, datetime]]:
    clip_start = max(start, window_start)
    clip_end = min(end, window_end)
    if clip_end <= clip_start:
        return None
    return clip_start, clip_end


def make_sleep_segment_sample_id(
    user_id: str,
    metric_type: str,
    start: datetime,
    end: datetime,
    *,
    source: str = INGEST_SOURCE,
) -> str:
    token = "".join(
        ch if ch.isalnum() or ch in "-_." else "_"
        for ch in (source or INGEST_SOURCE)
    )[:48]
    return (
        f"healthkit|{user_id}|{metric_type}|{start.isoformat()}|"
        f"{end.isoformat()}|{token or INGEST_SOURCE}"
    )


def _optional_aligned_str_list(raw: Any, expected: int) -> list[str]:
    """Return a per-row list only when it matches the stage list length."""
    if raw in (None, ""):
        return []
    try:
        items = _as_str_list(raw)
    except ValueError:
        return []
    if len(items) != expected:
        return []
    return items


def _source_name_for_row(source: str, device: str) -> str:
    text = (source or "").strip() or (device or "").strip()
    return text or INGEST_SOURCE


def ingest_sleep_bundle(
    user_id: str,
    lists: dict[str, Any],
    *,
    tz_name: Optional[str] = None,
    received_at: Optional[datetime] = None,
) -> IngestResult:
    """Persist PHA_SLEEP_V1 / sleep_* lists as segments; rebuild daily from T2 rules."""
    from pha.wearable_daily_aggregator import healthkit_sleep_fields_from_segments

    uid = (user_id or "default").strip() or "default"
    tz = tz_name or ingest_tz_name()
    values = _as_str_list(lists.get("sleep_values"))
    starts = _as_str_list(lists.get("sleep_starts"))
    ends = _as_str_list(lists.get("sleep_ends"))
    if not values or len(values) != len(starts) or len(values) != len(ends):
        raise ValueError("sleep_stage_list_mismatch")
    sources = _optional_aligned_str_list(lists.get("sleep_sources"), len(values))
    devices = _optional_aligned_str_list(lists.get("sleep_devices"), len(values))

    skipped_zero = 0
    dropped_unknown = 0
    parsed: list[tuple[str, datetime, datetime, str]] = []
    for idx, (label, start_raw, end_raw) in enumerate(zip(values, starts, ends)):
        metric = resolve_sleep_stage_metric(label)
        if metric is None:
            dropped_unknown += 1
            continue
        start = normalize_timestamp(start_raw, tz)
        end = normalize_timestamp(end_raw, tz)
        delta = (end - start).total_seconds()
        if delta <= 0:
            if delta >= -120:
                skipped_zero += 1
                logger.info(
                    "healthkit_ingest skip zero-duration sleep stage=%s start=%r end=%r",
                    metric,
                    start_raw,
                    end_raw,
                )
                continue
            raise ValueError(
                f"implausible_sleep_hours:end_before_start:{start_raw}..{end_raw}"
            )
        source_name = _source_name_for_row(
            sources[idx] if sources else "",
            devices[idx] if devices else "",
        )
        parsed.append((metric, start, end, source_name))

    asleep = [item for item in parsed if item[0] in _ASLEEP_STAGE_METRICS]
    if not asleep:
        raise ValueError("empty_sleep_window")

    def apply_window(
        wake_day: date,
    ) -> tuple[list[tuple[str, datetime, datetime, str]], datetime, datetime]:
        window_start, window_end = _sleep_wake_window(wake_day)
        kept: list[tuple[str, datetime, datetime, str]] = []
        for metric, start, end, source_name in parsed:
            clipped = _clip_to_window(start, end, window_start, window_end)
            if clipped is None:
                continue
            kept.append((metric, clipped[0], clipped[1], source_name))
        return kept, window_start, window_end

    d0 = max(item[2] for item in asleep).date()
    kept, window_start, window_end = apply_window(d0)
    kept_asleep = [item for item in kept if item[0] in _ASLEEP_STAGE_METRICS]
    if not kept_asleep:
        raise ValueError("empty_sleep_window")
    wake_day = max(item[2] for item in kept_asleep).date()
    if wake_day != d0:
        kept, window_start, window_end = apply_window(wake_day)
        kept_asleep = [item for item in kept if item[0] in _ASLEEP_STAGE_METRICS]
        if not kept_asleep:
            raise ValueError("empty_sleep_window")
        wake_day = max(item[2] for item in kept_asleep).date()

    received = received_at or datetime.now(_load_zoneinfo(tz)).replace(tzinfo=None)
    if (received.date() - wake_day).days > 1:
        raise ValueError("stale_sleep_bundle")

    segment_rows: list[tuple[datetime, datetime, str, str, bool]] = []
    sample_ids: list[str] = []
    for metric, start, end, source_name in kept:
        sid = make_sleep_segment_sample_id(uid, metric, start, end, source=source_name)
        is_awake = metric == "sleep_awake"
        segment_rows.append((start, end, source_name, sid, is_awake))
        sample_ids.append(sid)

    _deleted, inserted = replace_healthkit_sleep_segments_for_day(
        uid, wake_day, segment_rows
    )
    delete_healthkit_sleep_family_on_day(uid, wake_day)
    days_rebuilt = rebuild_wearable_daily_for_days(uid, [wake_day])

    field_rows = [
        {
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "source_name": source,
            "sample_id": sid,
            "is_awake": 1 if is_awake else 0,
        }
        for start, end, source, sid, is_awake in segment_rows
    ]
    fields = healthkit_sleep_fields_from_segments(field_rows)
    session_span_h = 0.0
    if kept:
        session_span_h = (max(item[2] for item in kept) - min(item[1] for item in kept)).total_seconds() / 3600.0
    audit = {
        "kept": len(kept),
        "skipped_zero": skipped_zero,
        "dropped_unknown_label": dropped_unknown,
        "per_stage_h": {
            key: round(value, 3) for key, value in (fields.get("per_stage_h") or {}).items()
        },
        "union_asleep_h": round(float(fields.get("union_asleep_h") or 0.0), 3),
        "session_span": round(session_span_h, 3),
        "window": f"{window_start.isoformat()}/{window_end.isoformat()}",
        "wake_day": wake_day.isoformat(),
        "stage_overlap": bool(fields.get("stage_overlap")),
        "sleep_period_h": round(float(fields.get("sleep_period_h") or 0.0), 3),
    }
    if fields.get("sleep_efficiency") is not None:
        audit["sleep_efficiency"] = round(float(fields["sleep_efficiency"]), 3)
    logger.info("healthkit_ingest sleep_bundle %s", audit)
    return IngestResult(
        inserted=inserted,
        ignored=0,
        dropped=dropped_unknown,
        days_rebuilt=days_rebuilt,
        sample_ids=sample_ids,
        timestamp_defaulted=0,
        audit=audit,
    )


def daily_key_stored_types() -> frozenset[str]:
    """Stored metric_type values that UPSERT one HealthKit row per calendar day.

    Allowlist comes from the wearable registry (``fact_card.daily_key``), not a
    Python set of product names.
    """
    from pha.wearable_metric_registry import fact_card_daily_ingest_keys

    out: set[str] = set()
    for raw in fact_card_daily_ingest_keys():
        resolved = resolve_metric_type(raw)
        if resolved:
            out.add(resolved)
    return frozenset(out)


def make_sample_id(
    user_id: str,
    metric_type: str,
    ts: datetime,
    *,
    daily_keys: Optional[frozenset[str]] = None,
) -> str:
    keys = daily_keys if daily_keys is not None else daily_key_stored_types()
    if metric_type in keys:
        return f"healthkit|{user_id}|{metric_type}|{ts.date().isoformat()}|{INGEST_SOURCE}"
    return f"healthkit|{user_id}|{metric_type}|{ts.isoformat()}|{INGEST_SOURCE}"


def _combine_step_numbers(nums: list[float]) -> float:
    """Daily total if Shortcuts prepended Sum before per-sample increments; else sum."""
    if not nums:
        raise ValueError("unreadable_value")
    if len(nums) == 1:
        return nums[0]
    rest = float(sum(nums[1:]))
    if nums[0] + 1e-6 >= rest:
        return float(nums[0])
    return float(sum(nums))


def _finite_number(value: Any, *, sum_all: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError("unreadable_value")
    if isinstance(value, (int, float)):
        n = float(value)
    elif isinstance(value, dict):
        for key in (
            "Magnitude",
            "magnitude",
            "Value",
            "value",
            "Amount",
            "amount",
            "number",
            "doubleValue",
            "numericValue",
            "quantity",
        ):
            if key in value and value[key] not in (None, ""):
                return _finite_number(value[key], sum_all=sum_all)
        nums = [
            item
            for item in value.values()
            if isinstance(item, (int, float)) and not isinstance(item, bool)
        ]
        if len(nums) == 1:
            return _finite_number(nums[0], sum_all=False)
        if sum_all and nums:
            return _combine_step_numbers([float(x) for x in nums])
        raise ValueError("unreadable_value")
    elif isinstance(value, (list, tuple)) and value:
        if sum_all:
            return _combine_step_numbers(
                [_finite_number(item, sum_all=False) for item in value]
            )
        return _finite_number(value[0], sum_all=False)
    else:
        token = str(value or "")
        token = (
            token.replace("\ufffc", " ")
            .replace("\ufeff", "")
            .replace(",", "")
            .replace("\u00a0", " ")
            .replace("\u202f", " ")
            .strip()
        )
        if token.startswith("{") or token.startswith("["):
            try:
                return _finite_number(json.loads(token), sum_all=sum_all)
            except (json.JSONDecodeError, ValueError, TypeError):
                pass
        matches = list(_VALUE_TOKEN_RE.finditer(token))
        if not matches:
            raise ValueError("unreadable_value")
        if sum_all:
            n = _combine_step_numbers([float(m.group(0)) for m in matches])
        else:
            n = float(matches[0].group(0))
    if not math.isfinite(n):
        raise ValueError("non_finite_value")
    return n


def ingest_healthkit_samples(
    user_id: str,
    samples: list[HealthKitSample] | list[dict[str, Any]],
    *,
    tz_name: Optional[str] = None,
) -> IngestResult:
    """Validate entire batch then write. Parse errors raise ValueError (caller → 400)."""
    uid = (user_id or "default").strip() or "default"
    tz = tz_name or ingest_tz_name()
    if not samples:
        raise ValueError("empty_samples")
    if len(samples) > MAX_SAMPLES:
        raise ValueError(f"too_many_samples:{len(samples)}")

    daily_keys = daily_key_stored_types()
    prepared: list[tuple[str, datetime, float, str]] = []
    dropped = 0
    timestamp_defaulted = 0
    for item in samples:
        if isinstance(item, HealthKitSample):
            metric_raw = item.metric_type
            ts_raw = item.timestamp
            value_raw = item.value
            source_raw = item.source
        else:
            metric_raw = str(item.get("metric_type") or "")
            ts_raw = str(item.get("timestamp") or "")
            value_raw = item.get("value")
            source_raw = str(item.get("source") or INGEST_SOURCE)

        src = (source_raw or INGEST_SOURCE).strip().lower() or INGEST_SOURCE
        if src != INGEST_SOURCE:
            raise ValueError(f"unsupported_source:{source_raw}")

        metric = resolve_metric_type(metric_raw)
        if metric is None:
            dropped += 1
            continue
        if not str(ts_raw or "").strip():
            ts = datetime.now(_load_zoneinfo(tz)).replace(tzinfo=None)
            timestamp_defaulted += 1
            logger.warning("healthkit_ingest empty timestamp; using received_at=%s", ts.isoformat())
        else:
            ts = normalize_timestamp(ts_raw, tz)
        try:
            value = _finite_number(value_raw, sum_all=(metric == METRIC_STEPS))
        except ValueError:
            logger.warning(
                "healthkit_ingest unreadable_value type=%s preview=%r",
                type(value_raw).__name__,
                str(value_raw)[:120],
            )
            raise ValueError("unreadable_value") from None
        if metric in _SLEEP_HOUR_METRICS:
            value = _as_sleep_hours(metric, value)
        if metric in daily_keys:
            ts = datetime.combine(ts.date(), datetime.min.time())
        sid = make_sample_id(uid, metric, ts, daily_keys=daily_keys)
        prepared.append((metric, ts, value, sid))

    if not prepared and dropped == 0:
        raise ValueError("empty_samples")

    for metric, ts, _value, sid in prepared:
        if metric in daily_keys:
            delete_stale_healthkit_metric_on_day(uid, metric, ts.date(), sid)

    writer = WearableDataBatchWriter(uid, on_conflict="update")
    try:
        for metric, ts, value, sid in prepared:
            writer.add_sample(metric, ts, value, sample_id=sid)
    finally:
        writer.close()

    days = sorted({ts.date() for _m, ts, _v, _sid in prepared})
    days_rebuilt = rebuild_wearable_daily_for_days(uid, days) if days else 0
    logger.info(
        "healthkit_ingest user_id=%s inserted=%s ignored=%s dropped=%s days=%s",
        uid,
        writer.total_written,
        writer.total_ignored,
        dropped,
        days_rebuilt,
    )
    return IngestResult(
        inserted=writer.total_written,
        ignored=writer.total_ignored,
        dropped=dropped,
        days_rebuilt=days_rebuilt,
        sample_ids=[sid for _m, _ts, _v, sid in prepared],
        timestamp_defaulted=timestamp_defaulted,
    )


def require_ingest_token(header_token: Optional[str], body_token: Optional[str]) -> None:
    expected = ingest_token_configured()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail={"error": "ingest_token_not_configured", "env": INGEST_TOKEN_ENV},
        )
    offered = (header_token or "").strip() or (body_token or "").strip()
    if offered != expected:
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})


def _preview_body(raw: bytes, limit: int = 400) -> str:
    text = raw.decode("utf-8", errors="replace").replace("\x00", "")
    if "token" in text.lower():
        text = re.sub(r'("token"\s*:\s*")[^"]*(")', r"\1***\2", text, flags=re.I)
    if text.lstrip().startswith("PHA_SLEEP_V1"):
        limit = max(limit, 8000)
    return text[:limit]


def _persist_sleep_bundle_for_replay(text: str) -> None:
    """Write PHA_SLEEP_V1 body to gitignored data/ for T0 replay. Never write tokens."""
    dest = Path(__file__).resolve().parents[1] / "data" / "local_shortcuts"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%dT%H%M%S")
        day = datetime.now().strftime("%Y-%m-%d")
        (dest / f"sleep_body_{stamp}.txt").write_text(text, encoding="utf-8")
        (dest / "sleep_body_latest.txt").write_text(text, encoding="utf-8")
        (dest / f"sleep_body_{day}.txt").write_text(text, encoding="utf-8")
    except OSError:
        logger.warning("healthkit_ingest could not persist sleep bundle for replay")


def parse_sleep_bundle_text(text: str) -> Optional[dict[str, Any]]:
    """Parse PHA_SLEEP_V1 marker text from the File-body sleep shortcut."""
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not raw.lstrip().startswith("PHA_SLEEP_V1"):
        return None
    user_id = "default"
    match_user = re.search(r"^user_id=(.+)$", raw, flags=re.M)
    if match_user:
        user_id = match_user.group(1).strip() or "default"
    try:
        after_values = raw.split("---VALUES---", 1)[1]
        values, rest = after_values.split("---STARTS---", 1)
        starts, after_starts = rest.split("---ENDS---", 1)
    except (IndexError, ValueError) as extra:
        raise ValueError("sleep_stage_list_mismatch") from extra
    ends = after_starts
    sources = ""
    devices = ""
    if "---SOURCES---" in ends:
        ends, after_sources = ends.split("---SOURCES---", 1)
        if "---DEVICES---" in after_sources:
            sources, devices = after_sources.split("---DEVICES---", 1)
        else:
            sources = after_sources
    elif "---DEVICES---" in ends:
        ends, devices = ends.split("---DEVICES---", 1)
    _persist_sleep_bundle_for_replay(raw)
    out = {
        "user_id": user_id,
        "sleep_values": values.strip(),
        "sleep_starts": starts.strip(),
        "sleep_ends": ends.strip(),
    }
    if sources.strip():
        out["sleep_sources"] = sources.strip()
    if devices.strip():
        out["sleep_devices"] = devices.strip()
    return out


def _loads_ingest_json(raw: bytes) -> Any:
    """Parse JSON; Shortcuts may inject raw newlines into the value string."""
    text = raw.decode("utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    collapsed = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
    try:
        return json.loads(collapsed)
    except json.JSONDecodeError as extra:
        if re.search(r'"value"\s*:\s*,', collapsed):
            raise ValueError("empty_value") from extra
        raise ValueError("unreadable_json") from extra


def parse_ingest_payload(
    raw: bytes,
) -> tuple[str, Optional[str], list[dict[str, Any]], Optional[dict[str, Any]]]:
    """Decode Shortcuts / JSON body into (user_id, token, sample dicts, sleep lists)."""
    if not raw or not raw.strip():
        raise ValueError("empty_body")
    text = raw.decode("utf-8-sig", errors="replace")
    bundle = parse_sleep_bundle_text(text)
    if bundle is not None:
        payload = bundle
    else:
        try:
            payload = _loads_ingest_json(raw)
        except UnicodeDecodeError as extra:
            raise ValueError("unreadable_json") from extra
    if isinstance(payload, list):
        payload = {"user_id": "default", "samples": payload}
    if not isinstance(payload, dict):
        raise ValueError("unreadable_json")
    user_id = str(payload.get("user_id") or "default")
    token = payload.get("token")
    token_s = str(token) if token is not None else None
    samples = payload.get("samples")
    if samples is None and all(k in payload for k in ("metric_type", "timestamp", "value")):
        samples = [payload]
    has_sleep_lists = any(
        key in payload for key in ("sleep_values", "sleep_starts", "sleep_ends")
    )
    sleep_lists: Optional[dict[str, Any]] = None
    if has_sleep_lists:
        sleep_lists = {
            "sleep_values": payload.get("sleep_values"),
            "sleep_starts": payload.get("sleep_starts"),
            "sleep_ends": payload.get("sleep_ends"),
            "sleep_sources": payload.get("sleep_sources"),
            "sleep_devices": payload.get("sleep_devices"),
        }
    if samples is None and has_sleep_lists:
        samples = []
    if not isinstance(samples, list):
        raise ValueError("empty_samples")
    out: list[dict[str, Any]] = []
    for item in samples:
        if not isinstance(item, dict):
            raise ValueError("unreadable_json")
        out.append(item)
    return user_id, token_s, out, sleep_lists


@router.get("/ingest/healthkit")
async def get_ingest_healthkit() -> dict[str, Any]:
    """Browser GET is not ingest. Keep fail-closed; do not accept or invent samples."""
    return {
        "ok": False,
        "error": "use_post",
        "hint": "此地址只接受 iPhone 捷径的 POST，不能在浏览器打开。请打开 http://WenhuideMacBook-Air.local:8788/ 看 PHA 界面。",
        "last": "/ingest/healthkit/last?user_id=default",
    }


@router.get("/ingest/healthkit/last")
async def get_ingest_healthkit_last(
    user_id: str = "default",
    x_pha_ingest_token: Optional[str] = Header(default=None),
    token: Optional[str] = None,
) -> dict[str, Any]:
    """FR-1.7: last HealthKit ingest success/failure receipt (no raw bodies)."""
    from pha.healthkit_ingest_receipt import load_healthkit_ingest_last

    require_ingest_token(x_pha_ingest_token, token)
    uid = (user_id or "default").strip() or "default"
    return load_healthkit_ingest_last(uid)


@router.post("/ingest/healthkit")
async def post_ingest_healthkit(
    request: Request,
    x_pha_ingest_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    from pha.healthkit_ingest_receipt import record_healthkit_ingest_receipt

    raw = await request.body()
    try:
        user_id, body_token, samples, sleep_lists = parse_ingest_payload(raw)
    except ValueError as extra:
        logger.warning(
            "healthkit_ingest reject content_type=%s err=%s preview=%r",
            request.headers.get("content-type", ""),
            extra,
            _preview_body(raw),
        )
        try:
            require_ingest_token(x_pha_ingest_token, None)
            uid_guess = "default"
            text = raw.decode("utf-8-sig", errors="replace")
            match_user = re.search(r"^user_id=(.+)$", text, flags=re.M)
            if match_user:
                uid_guess = match_user.group(1).strip() or "default"
            elif text.lstrip().startswith("{"):
                try:
                    uid_guess = str(json.loads(text).get("user_id") or "default")
                except Exception:
                    pass
            kind = "sleep" if "PHA_SLEEP_V1" in text or "sleep_" in text else "quantity"
            record_healthkit_ingest_receipt(
                uid_guess, ok=False, kind=kind, error=str(extra)
            )
        except HTTPException:
            pass
        raise HTTPException(status_code=400, detail={"error": str(extra)}) from extra
    require_ingest_token(x_pha_ingest_token, body_token)
    uid = (user_id or "default").strip() or "default"
    try:
        if sleep_lists is not None:
            text = raw.decode("utf-8-sig", errors="replace")
            if text.lstrip().startswith("PHA_SLEEP_V1"):
                logger.info(
                    "healthkit_ingest sleep_bundle_text %s",
                    _preview_body(raw, limit=100_000),
                )
            result = ingest_sleep_bundle(user_id, sleep_lists)
            kind = "sleep"
            metrics = ["sleep"]
        elif samples:
            result = ingest_healthkit_samples(user_id, samples)
            kind = "quantity"
            metrics = sorted(
                {
                    str(item.get("metric_type") or "").strip()
                    for item in samples
                    if str(item.get("metric_type") or "").strip()
                }
            )
        else:
            raise ValueError("empty_samples")
    except ValueError as extra:
        logger.warning(
            "healthkit_ingest fail-closed error=%s samples=%r body=%r",
            extra,
            samples[:2],
            _preview_body(raw),
        )
        record_healthkit_ingest_receipt(
            uid,
            ok=False,
            kind="sleep" if sleep_lists is not None else "quantity",
            error=str(extra),
        )
        raise HTTPException(
            status_code=400,
            detail={"error": str(extra), "got": samples[:1]},
        ) from extra
    days = result.audit.get("wake_day") if result.audit else None
    record_healthkit_ingest_receipt(
        uid,
        ok=True,
        kind=kind,
        inserted=result.inserted,
        ignored=result.ignored,
        dropped=result.dropped,
        days_rebuilt=[days] if days else [],
        audit=result.audit,
        metrics=metrics,
    )
    body: dict[str, Any] = {
        "ok": True,
        "user_id": uid,
        "source": INGEST_SOURCE,
        "inserted": result.inserted,
        "ignored": result.ignored,
        "dropped": result.dropped,
        "days_rebuilt": result.days_rebuilt,
        "timestamp_defaulted": result.timestamp_defaulted,
    }
    if result.audit:
        body["audit"] = result.audit
    return body
