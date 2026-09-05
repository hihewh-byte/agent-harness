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
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

from pha.date_parser import safe_parse_datetime
from pha.sqlite_storage import (
    METRIC_ACTIVE_ENERGY,
    METRIC_HRV,
    METRIC_RHR,
    METRIC_SLEEP,
    METRIC_STEPS,
    WearableDataBatchWriter,
    delete_stale_healthkit_metric_on_day,
    rebuild_wearable_daily_for_days,
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
    "hrv": METRIC_HRV,
    "rhr": METRIC_RHR,
    "steps": METRIC_STEPS,
    "sleep_hours": METRIC_SLEEP,
    "sleep": METRIC_SLEEP,
    "active_energy": METRIC_ACTIVE_ENERGY,
}

# Shortcuts / HealthKit type identifiers (lowercased, no punctuation).
_ALIASES: dict[str, str] = {
    "hkquantitytypeidentifierheartratevariabilitysdnn": METRIC_HRV,
    "heartratevariabilitysdnn": METRIC_HRV,
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


# Daily-total metrics: one HealthKit row per calendar day (re-sync replaces).
_DAILY_KEY_METRICS = {METRIC_STEPS}


def make_sample_id(user_id: str, metric_type: str, ts: datetime) -> str:
    if metric_type in _DAILY_KEY_METRICS:
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
        if metric in _DAILY_KEY_METRICS:
            ts = datetime.combine(ts.date(), datetime.min.time())
        sid = make_sample_id(uid, metric, ts)
        prepared.append((metric, ts, value, sid))

    if not prepared and dropped == 0:
        raise ValueError("empty_samples")

    for metric, ts, _value, sid in prepared:
        if metric in _DAILY_KEY_METRICS:
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
    return text[:limit]


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


def parse_ingest_payload(raw: bytes) -> tuple[str, Optional[str], list[dict[str, Any]]]:
    """Decode Shortcuts / JSON body into (user_id, token, sample dicts)."""
    if not raw or not raw.strip():
        raise ValueError("empty_body")
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
    if not isinstance(samples, list):
        raise ValueError("empty_samples")
    out: list[dict[str, Any]] = []
    for item in samples:
        if not isinstance(item, dict):
            raise ValueError("unreadable_json")
        out.append(item)
    return user_id, token_s, out


@router.get("/ingest/healthkit")
async def get_ingest_healthkit() -> dict[str, Any]:
    """Browser GET is not ingest. Keep fail-closed; do not accept or invent samples."""
    return {
        "ok": False,
        "error": "use_post",
        "hint": "此地址只接受 iPhone 捷径的 POST，不能在浏览器打开。请打开 http://WenhuideMacBook-Air.local:8788/ 看 PHA 界面。",
    }


@router.post("/ingest/healthkit")
async def post_ingest_healthkit(
    request: Request,
    x_pha_ingest_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    raw = await request.body()
    try:
        user_id, body_token, samples = parse_ingest_payload(raw)
    except ValueError as extra:
        logger.warning(
            "healthkit_ingest reject content_type=%s err=%s preview=%r",
            request.headers.get("content-type", ""),
            extra,
            _preview_body(raw),
        )
        raise HTTPException(status_code=400, detail={"error": str(extra)}) from extra
    require_ingest_token(x_pha_ingest_token, body_token)
    try:
        result = ingest_healthkit_samples(user_id, samples)
    except ValueError as extra:
        logger.warning(
            "healthkit_ingest fail-closed error=%s samples=%r body=%r",
            extra,
            samples[:2],
            _preview_body(raw),
        )
        raise HTTPException(
            status_code=400,
            detail={"error": str(extra), "got": samples[:1]},
        ) from extra
    return {
        "ok": True,
        "user_id": (user_id or "default").strip() or "default",
        "source": INGEST_SOURCE,
        "inserted": result.inserted,
        "ignored": result.ignored,
        "dropped": result.dropped,
        "days_rebuilt": result.days_rebuilt,
        "timestamp_defaulted": result.timestamp_defaulted,
    }
